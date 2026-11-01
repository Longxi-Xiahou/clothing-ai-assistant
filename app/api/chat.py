import uuid
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db.dependencies import get_db
from app.models.conversation import Conversation
from app.models.message import Message
from app.models.user import User
from app.repositories.mysql.products import MySQLProductRepository
from app.services.filter_merger import merge_filters
from app.services.intent_classifier import classify_intent
from app.services.llm import generate_reply


router = APIRouter(prefix="/chat", tags=["Chat"])


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    conversation_id: str | None = Field(default=None, min_length=36, max_length=36)


class ChatResponse(BaseModel):
    reply: str
    model: str
    conversation_id: str
    needs_clarification: bool = False
    clarification_reason: str | None = None


def _build_product_context(products: list) -> str:
    if not products:
        return (
            "No matching products were found in the current catalog. "
            "Do not recommend or invent specific products, prices, or stock."
        )

    lines = []
    for product in products:
        lines.append(
            f"- ID: {product.id}; "
            f"SKU: {product.sku}; "
            f"Name: {product.name}; "
            f"Category: {product.category or 'Not specified'}; "
            f"Brand: {product.brand or 'Not specified'}; "
            f"Price: {product.price} {product.currency}; "
            f"Stock: {product.stock}; "
            f"Attributes: {product.attributes}; "
            f"Description: {product.description or 'Not provided'}"
        )

    return "\n".join(lines)


def _json_safe_filters(filters: dict[str, Any]) -> dict[str, Any]:
    """Convert Decimal values into JSON-compatible strings."""
    result = {}
    for key, value in filters.items():
        result[key] = str(value) if isinstance(value, Decimal) else value
    return result


def _get_history(db: Session, conversation_id: int) -> list[dict[str, str]]:
    """Load the most recent ten messages in chronological order."""
    statement = (
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.id.desc())
        .limit(10)
    )
    records = list(db.scalars(statement).all())
    records.reverse()

    return [
        {"role": record.role, "content": record.content}
        for record in records
        if record.role in ("user", "assistant")
    ]


def _get_or_create_conversation(
    db: Session,
    public_id: str | None,
    first_message: str,
) -> Conversation:
    if public_id is not None:
        conversation = db.scalar(
            select(Conversation).where(Conversation.public_id == public_id)
        )
        if conversation is None:
            raise HTTPException(
                status_code=404,
                detail="Conversation not found.",
            )
        return conversation

    # Give each new conversation its own guest user.
    guest = User(
        external_id=f"guest:{uuid.uuid4()}",
        display_name="Guest",
    )
    db.add(guest)
    db.flush()

    conversation = Conversation(
        user_id=guest.id,
        title=first_message[:255],
        filters={},
    )
    db.add(conversation)
    db.flush()

    return conversation


@router.post("", response_model=ChatResponse)
async def chat(
    payload: ChatRequest,
    db: Session = Depends(get_db),
) -> ChatResponse:
    try:
        conversation = _get_or_create_conversation(
            db,
            payload.conversation_id,
            payload.message,
        )

        history = _get_history(db, conversation.id)
        previous_filters = conversation.filters or {}

        intent = await classify_intent(
            payload.message,
            previous_filters=previous_filters,
            history=history,
        )

        if intent.needs_clarification:
            reply = (
                "你的价格条件存在冲突。你希望设置的最低价和最高价分别是多少？"
                if any("\u4e00" <= char <= "\u9fff" for char in payload.message)
                else "Your price constraints conflict. What minimum and maximum price would you like?"
            )

            # Preserve existing filters while clarification is pending.
            db.add(
                Message(
                    conversation_id=conversation.id,
                    role="user",
                    content=payload.message,
                    extra_data={},
                )
            )
            db.add(
                Message(
                    conversation_id=conversation.id,
                    role="assistant",
                    content=reply,
                    model_name="Qwen3-14B",
                    extra_data={"needs_clarification": True},
                )
            )
            db.commit()

            return ChatResponse(
                reply=reply,
                model="Qwen3-14B",
                conversation_id=conversation.public_id,
                needs_clarification=True,
                clarification_reason=intent.clarification_reason,
            )

        try:
            filters = merge_filters(previous_filters, intent)
        except ValueError:
            reply = (
                "这次价格调整与之前的价格条件冲突。请确认你希望的最低价和最高价。"
                if any("\u4e00" <= char <= "\u9fff" for char in payload.message)
                else "This price change conflicts with your existing filters. What minimum and maximum price would you like?"
            )

            db.add(
                Message(
                    conversation_id=conversation.id,
                    role="user",
                    content=payload.message,
                    extra_data={},
                )
            )
            db.add(
                Message(
                    conversation_id=conversation.id,
                    role="assistant",
                    content=reply,
                    model_name="Qwen3-14B",
                    extra_data={"needs_clarification": True},
                )
            )
            db.commit()

            return ChatResponse(
                reply=reply,
                model="Qwen3-14B",
                conversation_id=conversation.public_id,
                needs_clarification=True,
                clarification_reason="conflicting_price_constraints",
            )

        product_context = None

        if intent.intent == "product_search":
            repository = MySQLProductRepository(db)
            products = repository.search(
                category=filters["category"],
                color=filters["color"],
                min_price=(
                    Decimal(str(filters["min_price"]))
                    if filters["min_price"] is not None
                    else None
                ),
                max_price=(
                    Decimal(str(filters["max_price"]))
                    if filters["max_price"] is not None
                    else None
                ),
                active_only=True,
                in_stock_only=True,
                limit=10,
            )
            product_context = _build_product_context(products)

        reply = await generate_reply(
            payload.message,
            product_context=product_context,
            history=history,
        )

        conversation.filters = _json_safe_filters(filters)

        db.add(
            Message(
                conversation_id=conversation.id,
                role="user",
                content=payload.message,
                extra_data={},
            )
        )
        db.add(
            Message(
                conversation_id=conversation.id,
                role="assistant",
                content=reply,
                model_name="Qwen3-14B",
                extra_data={},
            )
        )

        db.commit()

        return ChatResponse(
            reply=reply,
            model="Qwen3-14B",
            conversation_id=conversation.public_id,
            needs_clarification=False,
            clarification_reason=None,
        )

    except HTTPException:
        db.rollback()
        raise
    except (SQLAlchemyError, ValueError):
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="The conversation could not be saved or processed.",
        )
    except Exception:
        db.rollback()
        raise
