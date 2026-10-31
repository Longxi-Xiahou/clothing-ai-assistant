from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # Register all ORM models with Base.metadata
from app.api.chat import classify_intent, generate_reply
from app.db.database import Base
from app.db.dependencies import get_db
from app.main import app
from app.models.conversation import Conversation
from app.models.message import Message
from app.repositories.mysql.products import MySQLProductRepository
from app.schemas.chat_intent import ChatIntent


@pytest.fixture
def client():
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    TestingSessionLocal = sessionmaker(
        bind=engine,
        autoflush=False,
        expire_on_commit=False,
    )

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.pop(get_db, None)
        Base.metadata.drop_all(engine)
        engine.dispose()


def make_product():
    return SimpleNamespace(
        id=1,
        sku="TSHIRT-001",
        name="Basic Cotton T-Shirt",
        category="T-Shirts",
        brand="Demo Brand",
        price=Decimal("24.99"),
        currency="USD",
        stock=50,
        attributes={"color": "black", "sizes": ["S", "M", "L"]},
        description="Everyday cotton T-shirt",
    )


def test_general_chat_skips_product_search(client, monkeypatch):
    classifier = AsyncMock(
        return_value=ChatIntent(intent="general", action="general")
    )
    reply_generator = AsyncMock(
        return_value="Here is some fashion advice."
    )
    repository_class = MagicMock()

    monkeypatch.setattr("app.api.chat.classify_intent", classifier)
    monkeypatch.setattr("app.api.chat.generate_reply", reply_generator)
    monkeypatch.setattr(
        "app.api.chat.MySQLProductRepository", repository_class
    )

    response = client.post(
        "/chat",
        json={"message": "Give me some fashion advice."},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["reply"] == "Here is some fashion advice."
    assert body["model"] == "Qwen3-14B"
    assert len(body["conversation_id"]) == 36

    classifier.assert_awaited_once_with(
        "Give me some fashion advice.",
        previous_filters={},
        history=[],
    )
    reply_generator.assert_awaited_once_with(
        "Give me some fashion advice.",
        product_context=None,
        history=[],
    )
    repository_class.assert_not_called()


def test_product_search_passes_merged_filters_to_repository(
    client, monkeypatch
):
    classifier = AsyncMock(
        return_value=ChatIntent(
            intent="product_search",
            action="new_search",
            category="T-Shirts",
            color="black",
            min_price=Decimal("10"),
            max_price=Decimal("30"),
        )
    )
    reply_generator = AsyncMock(return_value="Found a matching shirt.")

    repository = MagicMock()
    repository.search.return_value = [make_product()]
    repository_class = MagicMock(return_value=repository)

    monkeypatch.setattr("app.api.chat.classify_intent", classifier)
    monkeypatch.setattr("app.api.chat.generate_reply", reply_generator)
    monkeypatch.setattr(
        "app.api.chat.MySQLProductRepository", repository_class
    )

    response = client.post(
        "/chat",
        json={"message": "Find black T-shirts between $10 and $30."},
    )

    assert response.status_code == 200
    repository_class.assert_called_once()
    repository.search.assert_called_once_with(
        category="T-Shirts",
        color="black",
        min_price=Decimal("10"),
        max_price=Decimal("30"),
        active_only=True,
        in_stock_only=True,
        limit=10,
    )


def test_database_product_context_is_sent_to_llm(
    client, monkeypatch
):
    classifier = AsyncMock(
        return_value=ChatIntent(
            intent="product_search",
            action="new_search",
            category="T-Shirts",
            color="black",
        )
    )
    reply_generator = AsyncMock(return_value="Found a black T-shirt.")

    repository = MagicMock()
    repository.search.return_value = [make_product()]

    monkeypatch.setattr("app.api.chat.classify_intent", classifier)
    monkeypatch.setattr("app.api.chat.generate_reply", reply_generator)
    monkeypatch.setattr(
        "app.api.chat.MySQLProductRepository",
        MagicMock(return_value=repository),
    )

    response = client.post(
        "/chat",
        json={"message": "Find black T-shirts."},
    )

    assert response.status_code == 200
    reply_generator.assert_awaited_once()
    args, kwargs = reply_generator.await_args

    assert args == ("Find black T-shirts.",)
    assert kwargs["history"] == []
    assert "Basic Cotton T-Shirt" in kwargs["product_context"]
    assert "24.99 USD" in kwargs["product_context"]
    assert "Stock: 50" in kwargs["product_context"]


def test_no_matching_products_send_no_match_context(
    client, monkeypatch
):
    classifier = AsyncMock(
        return_value=ChatIntent(
            intent="product_search",
            action="new_search",
            category="Leather Jackets",
            color="purple",
            max_price=Decimal("20000"),
        )
    )
    reply_generator = AsyncMock(
        return_value="No matching products were found."
    )

    repository = MagicMock()
    repository.search.return_value = []

    monkeypatch.setattr("app.api.chat.classify_intent", classifier)
    monkeypatch.setattr("app.api.chat.generate_reply", reply_generator)
    monkeypatch.setattr(
        "app.api.chat.MySQLProductRepository",
        MagicMock(return_value=repository),
    )

    response = client.post(
        "/chat",
        json={"message": "Find purple leather jackets under $20,000."},
    )

    assert response.status_code == 200
    _, kwargs = reply_generator.await_args
    assert "No matching products" in kwargs["product_context"]
    assert "Do not recommend or invent" in kwargs["product_context"]


def test_classifier_http_error_is_propagated(client, monkeypatch):
    classifier = AsyncMock(
        side_effect=HTTPException(
            status_code=502,
            detail="The model returned an invalid intent classification.",
        )
    )
    reply_generator = AsyncMock()

    monkeypatch.setattr("app.api.chat.classify_intent", classifier)
    monkeypatch.setattr("app.api.chat.generate_reply", reply_generator)

    response = client.post(
        "/chat",
        json={"message": "Find black T-shirts."},
    )

    assert response.status_code == 502
    assert response.json()["detail"] == (
        "The model returned an invalid intent classification."
    )
    reply_generator.assert_not_awaited()


def test_empty_message_is_rejected_by_request_schema(client):
    response = client.post("/chat", json={"message": ""})
    assert response.status_code == 422


def test_messages_and_filters_are_persisted(client, monkeypatch):
    classifier = AsyncMock(
        return_value=ChatIntent(
            intent="product_search",
            action="new_search",
            category="T-Shirts",
            color="black",
            max_price=Decimal("30"),
        )
    )
    reply_generator = AsyncMock(return_value="Here is a black T-shirt.")

    repository = MagicMock()
    repository.search.return_value = [make_product()]

    monkeypatch.setattr("app.api.chat.classify_intent", classifier)
    monkeypatch.setattr("app.api.chat.generate_reply", reply_generator)
    monkeypatch.setattr(
        "app.api.chat.MySQLProductRepository",
        MagicMock(return_value=repository),
    )

    response = client.post(
        "/chat",
        json={"message": "Find black T-shirts under $30."},
    )

    assert response.status_code == 200
    conversation_id = response.json()["conversation_id"]

    # Inspect persisted state through the same test database dependency.
    override = app.dependency_overrides[get_db]
    generator = override()
    db = next(generator)
    try:
        conversation = db.scalar(
            select(Conversation).where(
                Conversation.public_id == conversation_id
            )
        )
        assert conversation is not None
        assert conversation.filters == {
            "category": "T-Shirts",
            "color": "black",
            "min_price": None,
            "max_price": "30",
        }

        messages = list(
            db.scalars(
                select(Message)
                .where(Message.conversation_id == conversation.id)
                .order_by(Message.id)
            ).all()
        )
        assert [item.role for item in messages] == ["user", "assistant"]
        assert messages[0].content == "Find black T-shirts under $30."
        assert messages[1].content == "Here is a black T-shirt."
    finally:
        generator.close()


def test_clarification_skips_search_and_preserves_filters(client, monkeypatch):
    classifier = AsyncMock(
        return_value=ChatIntent(
            intent="product_search",
            action="new_search",
            category="Hoodies",
            needs_clarification=True,
            clarification_reason="conflicting_price_constraints",
        )
    )
    reply_generator = AsyncMock()
    repository_class = MagicMock()

    monkeypatch.setattr("app.api.chat.classify_intent", classifier)
    monkeypatch.setattr("app.api.chat.generate_reply", reply_generator)
    monkeypatch.setattr(
        "app.api.chat.MySQLProductRepository",
        repository_class,
    )

    # First create a conversation with existing filters.
    initial_classifier = AsyncMock(
        return_value=ChatIntent(
            intent="product_search",
            action="new_search",
            category="Hoodies",
            min_price=Decimal("20"),
            max_price=Decimal("80"),
        )
    )
    initial_reply = AsyncMock(return_value="Here are some hoodies.")
    repository = MagicMock()
    repository.search.return_value = [make_product()]

    monkeypatch.setattr("app.api.chat.classify_intent", initial_classifier)
    monkeypatch.setattr("app.api.chat.generate_reply", initial_reply)

    first_response = client.post(
        "/chat",
        json={"message": "Find hoodies between $20 and $80."},
    )
    assert first_response.status_code == 200
    conversation_id = first_response.json()["conversation_id"]

    # Ignore calls made by the initial request; assert only on the follow-up.
    repository_class.reset_mock()
    reply_generator.reset_mock()

    # Now request clarification in the same conversation.
    monkeypatch.setattr("app.api.chat.classify_intent", classifier)
    monkeypatch.setattr("app.api.chat.generate_reply", reply_generator)

    second_response = client.post(
        "/chat",
        json={
            "message": "Find hoodies with conflicting prices.",
            "conversation_id": conversation_id,
        },
    )

    assert second_response.status_code == 200
    body = second_response.json()
    assert body["needs_clarification"] is True
    assert body["clarification_reason"] == "conflicting_price_constraints"
    assert body["reply"]

    classifier.assert_awaited_once()
    reply_generator.assert_not_awaited()
    repository_class.assert_not_called()

    # Confirm that the saved filters were not changed.
    override = app.dependency_overrides[get_db]
    generator = override()
    db = next(generator)
    try:
        conversation = db.scalar(
            select(Conversation).where(
                Conversation.public_id == conversation_id
            )
        )
        assert conversation is not None
        assert conversation.filters == {
            "category": "Hoodies",
            "color": None,
            "min_price": "20",
            "max_price": "80",
        }
    finally:
        generator.close()


def test_conflicting_merged_filters_return_clarification(client, monkeypatch):
    classifier = AsyncMock(
        return_value=ChatIntent(
            intent="product_search",
            action="modify_filters",
            min_price=Decimal("100"),
        )
    )
    reply_generator = AsyncMock()
    repository_class = MagicMock()

    monkeypatch.setattr("app.api.chat.classify_intent", classifier)
    monkeypatch.setattr("app.api.chat.generate_reply", reply_generator)
    monkeypatch.setattr(
        "app.api.chat.MySQLProductRepository",
        repository_class,
    )

    # Establish a previous maximum price of $80.
    initial_classifier = AsyncMock(
        return_value=ChatIntent(
            intent="product_search",
            action="new_search",
            category="Hoodies",
            min_price=Decimal("20"),
            max_price=Decimal("80"),
        )
    )
    initial_reply = AsyncMock(return_value="Here are some hoodies.")
    repository = MagicMock()
    repository.search.return_value = [make_product()]

    monkeypatch.setattr("app.api.chat.classify_intent", initial_classifier)
    monkeypatch.setattr("app.api.chat.generate_reply", initial_reply)

    first_response = client.post(
        "/chat",
        json={"message": "Find hoodies between $20 and $80."},
    )
    assert first_response.status_code == 200
    conversation_id = first_response.json()["conversation_id"]

    # Ignore calls made by the initial request; assert only on the follow-up.
    repository_class.reset_mock()
    reply_generator.reset_mock()

    # Raise the minimum above the saved maximum.
    monkeypatch.setattr("app.api.chat.classify_intent", classifier)
    monkeypatch.setattr("app.api.chat.generate_reply", reply_generator)

    second_response = client.post(
        "/chat",
        json={
            "message": "Raise the minimum price to $100.",
            "conversation_id": conversation_id,
        },
    )

    assert second_response.status_code == 200
    body = second_response.json()
    assert body["needs_clarification"] is True
    assert body["clarification_reason"] == "conflicting_price_constraints"
    reply_generator.assert_not_awaited()
    repository_class.assert_not_called()

    override = app.dependency_overrides[get_db]
    generator = override()
    db = next(generator)
    try:
        conversation = db.scalar(
            select(Conversation).where(
                Conversation.public_id == conversation_id
            )
        )
        assert conversation is not None
        assert conversation.filters == {
            "category": "Hoodies",
            "color": None,
            "min_price": "20",
            "max_price": "80",
        }
    finally:
        generator.close()


def test_general_chat_preserves_existing_filters(client, monkeypatch):
    # First turn: establish saved product filters.
    initial_classifier = AsyncMock(
        return_value=ChatIntent(
            intent="product_search",
            action="new_search",
            category="T-Shirts",
            color="black",
            max_price=Decimal("30"),
        )
    )
    initial_reply = AsyncMock(return_value="Here is a black T-shirt.")

    repository = MagicMock()
    repository.search.return_value = [make_product()]
    repository_class = MagicMock(return_value=repository)

    monkeypatch.setattr(
        "app.api.chat.classify_intent", initial_classifier
    )
    monkeypatch.setattr(
        "app.api.chat.generate_reply", initial_reply
    )
    monkeypatch.setattr(
        "app.api.chat.MySQLProductRepository", repository_class
    )

    first_response = client.post(
        "/chat",
        json={"message": "Find black T-shirts under $30."},
    )

    assert first_response.status_code == 200
    conversation_id = first_response.json()["conversation_id"]

    # Second turn: ordinary chat in the same conversation.
    general_classifier = AsyncMock(
        return_value=ChatIntent(
            intent="general",
            action="general",
        )
    )
    general_reply = AsyncMock(
        return_value="White sneakers would pair well with black jeans."
    )

    monkeypatch.setattr(
        "app.api.chat.classify_intent", general_classifier
    )
    monkeypatch.setattr(
        "app.api.chat.generate_reply", general_reply
    )

    # Ignore calls from the initial product search.
    repository_class.reset_mock()

    second_response = client.post(
        "/chat",
        json={
            "message": "What shoes would go with them?",
            "conversation_id": conversation_id,
        },
    )

    assert second_response.status_code == 200
    assert second_response.json()["reply"] == (
        "White sneakers would pair well with black jeans."
    )

    general_classifier.assert_awaited_once()
    assert general_classifier.await_args.kwargs["previous_filters"] == {
        "category": "T-Shirts",
        "color": "black",
        "min_price": None,
        "max_price": "30",
    }
    repository_class.assert_not_called()

    # Verify the persisted filters after the general chat turn.
    override = app.dependency_overrides[get_db]
    generator = override()
    db = next(generator)
    try:
        conversation = db.scalar(
            select(Conversation).where(
                Conversation.public_id == conversation_id
            )
        )
        assert conversation is not None
        assert conversation.filters == {
            "category": "T-Shirts",
            "color": "black",
            "min_price": None,
            "max_price": "30",
        }
    finally:
        generator.close()

def test_general_chat_preserves_existing_filters(client, monkeypatch):
    # First turn: establish saved product filters.
    initial_classifier = AsyncMock(
        return_value=ChatIntent(
            intent="product_search",
            action="new_search",
            category="T-Shirts",
            color="black",
            max_price=Decimal("30"),
        )
    )
    initial_reply = AsyncMock(return_value="Here is a black T-shirt.")

    repository = MagicMock()
    repository.search.return_value = [make_product()]
    repository_class = MagicMock(return_value=repository)

    monkeypatch.setattr(
        "app.api.chat.classify_intent", initial_classifier
    )
    monkeypatch.setattr(
        "app.api.chat.generate_reply", initial_reply
    )
    monkeypatch.setattr(
        "app.api.chat.MySQLProductRepository", repository_class
    )

    first_response = client.post(
        "/chat",
        json={"message": "Find black T-shirts under $30."},
    )

    assert first_response.status_code == 200
    conversation_id = first_response.json()["conversation_id"]

    # Second turn: ordinary chat in the same conversation.
    general_classifier = AsyncMock(
        return_value=ChatIntent(
            intent="general",
            action="general",
        )
    )
    general_reply = AsyncMock(
        return_value="White sneakers would pair well with black jeans."
    )

    monkeypatch.setattr(
        "app.api.chat.classify_intent", general_classifier
    )
    monkeypatch.setattr(
        "app.api.chat.generate_reply", general_reply
    )

    # Ignore calls from the initial product search.
    repository_class.reset_mock()

    second_response = client.post(
        "/chat",
        json={
            "message": "What shoes would go with them?",
            "conversation_id": conversation_id,
        },
    )

    assert second_response.status_code == 200
    assert second_response.json()["reply"] == (
        "White sneakers would pair well with black jeans."
    )

    general_classifier.assert_awaited_once()
    assert general_classifier.await_args.kwargs["previous_filters"] == {
        "category": "T-Shirts",
        "color": "black",
        "min_price": None,
        "max_price": "30",
    }
    repository_class.assert_not_called()

    # Verify the persisted filters after the general chat turn.
    override = app.dependency_overrides[get_db]
    generator = override()
    db = next(generator)
    try:
        conversation = db.scalar(
            select(Conversation).where(
                Conversation.public_id == conversation_id
            )
        )
        assert conversation is not None
        assert conversation.filters == {
            "category": "T-Shirts",
            "color": "black",
            "min_price": None,
            "max_price": "30",
        }
    finally:
        generator.close()


def test_general_chat_preserves_existing_filters(client, monkeypatch):
    # First turn: establish saved product filters.
    initial_classifier = AsyncMock(
        return_value=ChatIntent(
            intent="product_search",
            action="new_search",
            category="T-Shirts",
            color="black",
            max_price=Decimal("30"),
        )
    )
    initial_reply = AsyncMock(return_value="Here is a black T-shirt.")

    repository = MagicMock()
    repository.search.return_value = [make_product()]
    repository_class = MagicMock(return_value=repository)

    monkeypatch.setattr(
        "app.api.chat.classify_intent", initial_classifier
    )
    monkeypatch.setattr(
        "app.api.chat.generate_reply", initial_reply
    )
    monkeypatch.setattr(
        "app.api.chat.MySQLProductRepository", repository_class
    )

    first_response = client.post(
        "/chat",
        json={"message": "Find black T-shirts under $30."},
    )

    assert first_response.status_code == 200
    conversation_id = first_response.json()["conversation_id"]

    # Second turn: ordinary chat in the same conversation.
    general_classifier = AsyncMock(
        return_value=ChatIntent(
            intent="general",
            action="general",
        )
    )
    general_reply = AsyncMock(
        return_value="White sneakers would pair well with black jeans."
    )

    monkeypatch.setattr(
        "app.api.chat.classify_intent", general_classifier
    )
    monkeypatch.setattr(
        "app.api.chat.generate_reply", general_reply
    )

    # Ignore calls from the initial product search.
    repository_class.reset_mock()

    second_response = client.post(
        "/chat",
        json={
            "message": "What shoes would go with them?",
            "conversation_id": conversation_id,
        },
    )

    assert second_response.status_code == 200
    assert second_response.json()["reply"] == (
        "White sneakers would pair well with black jeans."
    )

    general_classifier.assert_awaited_once()
    assert general_classifier.await_args.kwargs["previous_filters"] == {
        "category": "T-Shirts",
        "color": "black",
        "min_price": None,
        "max_price": "30",
    }
    repository_class.assert_not_called()

    # Verify the persisted filters after the general chat turn.
    override = app.dependency_overrides[get_db]
    generator = override()
    db = next(generator)
    try:
        conversation = db.scalar(
            select(Conversation).where(
                Conversation.public_id == conversation_id
            )
        )
        assert conversation is not None
        assert conversation.filters == {
            "category": "T-Shirts",
            "color": "black",
            "min_price": None,
            "max_price": "30",
        }
    finally:
        generator.close()

def test_general_chat_preserves_existing_filters(client, monkeypatch):
    # First turn: establish saved product filters.
    initial_classifier = AsyncMock(
        return_value=ChatIntent(
            intent="product_search",
            action="new_search",
            category="T-Shirts",
            color="black",
            max_price=Decimal("30"),
        )
    )
    initial_reply = AsyncMock(return_value="Here is a black T-shirt.")

    repository = MagicMock()
    repository.search.return_value = [make_product()]
    repository_class = MagicMock(return_value=repository)

    monkeypatch.setattr(
        "app.api.chat.classify_intent", initial_classifier
    )
    monkeypatch.setattr(
        "app.api.chat.generate_reply", initial_reply
    )
    monkeypatch.setattr(
        "app.api.chat.MySQLProductRepository", repository_class
    )

    first_response = client.post(
        "/chat",
        json={"message": "Find black T-shirts under $30."},
    )

    assert first_response.status_code == 200
    conversation_id = first_response.json()["conversation_id"]

    # Second turn: ordinary chat in the same conversation.
    general_classifier = AsyncMock(
        return_value=ChatIntent(
            intent="general",
            action="general",
        )
    )
    general_reply = AsyncMock(
        return_value="White sneakers would pair well with black jeans."
    )

    monkeypatch.setattr(
        "app.api.chat.classify_intent", general_classifier
    )
    monkeypatch.setattr(
        "app.api.chat.generate_reply", general_reply
    )

    # Ignore calls from the initial product search.
    repository_class.reset_mock()

    second_response = client.post(
        "/chat",
        json={
            "message": "What shoes would go with them?",
            "conversation_id": conversation_id,
        },
    )

    assert second_response.status_code == 200
    assert second_response.json()["reply"] == (
        "White sneakers would pair well with black jeans."
    )

    general_classifier.assert_awaited_once()
    assert general_classifier.await_args.kwargs["previous_filters"] == {
        "category": "T-Shirts",
        "color": "black",
        "min_price": None,
        "max_price": "30",
    }
    repository_class.assert_not_called()

    # Verify the persisted filters after the general chat turn.
    override = app.dependency_overrides[get_db]
    generator = override()
    db = next(generator)
    try:
        conversation = db.scalar(
            select(Conversation).where(
                Conversation.public_id == conversation_id
            )
        )
        assert conversation is not None
        assert conversation.filters == {
            "category": "T-Shirts",
            "color": "black",
            "min_price": None,
            "max_price": "30",
        }
    finally:
        generator.close()


def test_general_chat_preserves_existing_filters(client, monkeypatch):
    # First turn: establish saved product filters.
    initial_classifier = AsyncMock(
        return_value=ChatIntent(
            intent="product_search",
            action="new_search",
            category="T-Shirts",
            color="black",
            max_price=Decimal("30"),
        )
    )
    initial_reply = AsyncMock(return_value="Here is a black T-shirt.")

    repository = MagicMock()
    repository.search.return_value = [make_product()]
    repository_class = MagicMock(return_value=repository)

    monkeypatch.setattr(
        "app.api.chat.classify_intent", initial_classifier
    )
    monkeypatch.setattr(
        "app.api.chat.generate_reply", initial_reply
    )
    monkeypatch.setattr(
        "app.api.chat.MySQLProductRepository", repository_class
    )

    first_response = client.post(
        "/chat",
        json={"message": "Find black T-shirts under $30."},
    )

    assert first_response.status_code == 200
    conversation_id = first_response.json()["conversation_id"]

    # Second turn: ordinary chat in the same conversation.
    general_classifier = AsyncMock(
        return_value=ChatIntent(
            intent="general",
            action="general",
        )
    )
    general_reply = AsyncMock(
        return_value="White sneakers would pair well with black jeans."
    )

    monkeypatch.setattr(
        "app.api.chat.classify_intent", general_classifier
    )
    monkeypatch.setattr(
        "app.api.chat.generate_reply", general_reply
    )

    # Ignore calls from the initial product search.
    repository_class.reset_mock()

    second_response = client.post(
        "/chat",
        json={
            "message": "What shoes would go with them?",
            "conversation_id": conversation_id,
        },
    )

    assert second_response.status_code == 200
    assert second_response.json()["reply"] == (
        "White sneakers would pair well with black jeans."
    )

    general_classifier.assert_awaited_once()
    assert general_classifier.await_args.kwargs["previous_filters"] == {
        "category": "T-Shirts",
        "color": "black",
        "min_price": None,
        "max_price": "30",
    }
    repository_class.assert_not_called()

    # Verify the persisted filters after the general chat turn.
    override = app.dependency_overrides[get_db]
    generator = override()
    db = next(generator)
    try:
        conversation = db.scalar(
            select(Conversation).where(
                Conversation.public_id == conversation_id
            )
        )
        assert conversation is not None
        assert conversation.filters == {
            "category": "T-Shirts",
            "color": "black",
            "min_price": None,
            "max_price": "30",
        }
    finally:
        generator.close()
