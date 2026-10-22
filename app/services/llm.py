import httpx
from fastapi import HTTPException

from app.core.config import settings


SYSTEM_PROMPT = (
    "You are a helpful clothing and fashion assistant. "
    "Give practical, concise, user-facing advice. "
    "Do not reveal internal reasoning. "
    "Never invent product names, inventory, prices, or availability. "
    "When product context is provided, recommend only products in that context. "
    "If no suitable products are provided, clearly say that no matching products "
    "were found in the current catalog."
)


async def generate_reply(
    message: str,
    product_context: str | None = None,
    history: list[dict[str, str]] | None = None,
) -> str:
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    # Include recent conversation history, excluding the current message.
    for item in history or []:
        role = item.get("role")
        content = item.get("content")

        if role in ("user", "assistant") and isinstance(content, str):
            if content.strip():
                messages.append({"role": role, "content": content})

    user_content = message

    if product_context:
        user_content = (
            f"Customer request:\n{message}\n\n"
            f"Available products retrieved from the database:\n"
            f"{product_context}\n\n"
            "Use the database products as the source of truth for product details."
        )

    messages.append({"role": "user", "content": user_content})

    url = f"{settings.LLM_BASE_URL.rstrip('/')}/chat/completions"
    payload = {
        "model": settings.LLM_MODEL,
        "messages": messages,
        "max_tokens": 512,
        "temperature": 0.7,
    }

    try:
        async with httpx.AsyncClient(
            timeout=settings.LLM_TIMEOUT_SECONDS
        ) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()

    except httpx.TimeoutException:
        raise HTTPException(
            status_code=504,
            detail="The language model request timed out.",
        )
    except httpx.HTTPStatusError:
        raise HTTPException(
            status_code=502,
            detail="The language model service returned an error.",
        )
    except httpx.RequestError:
        raise HTTPException(
            status_code=503,
            detail="The language model service is unavailable.",
        )
    except ValueError:
        raise HTTPException(
            status_code=502,
            detail="The language model returned an invalid response.",
        )

    try:
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        raise HTTPException(
            status_code=502,
            detail="The language model response has an unexpected format.",
        )

    if not isinstance(content, str) or not content.strip():
        raise HTTPException(
            status_code=502,
            detail="The language model returned an empty response.",
        )

    if "</think>" in content:
        content = content.rsplit("</think>", 1)[-1].strip()

    if not content:
        raise HTTPException(
            status_code=502,
            detail="The language model did not return a final answer.",
        )

    return content
