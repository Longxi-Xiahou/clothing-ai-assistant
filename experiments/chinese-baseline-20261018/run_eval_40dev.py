import asyncio
import json
from decimal import Decimal
from pathlib import Path

import httpx

from app.core.config import settings
from app.schemas.chat_intent import ChatIntent
from app.services.intent_classifier import INTENT_SYSTEM_PROMPT, _parse_json_object

ROOT = Path(__file__).resolve().parents[2]
EXP = ROOT / "experiments" / "chinese-baseline-20261018"
CASES_FILE = EXP / "cases_v3.jsonl"
CANDIDATE_PROMPT = (
    ROOT / "experiments" / "prompt-v4-20261018" / "prompt_v4_1.txt"
)

FIELDS = [
    "intent", "action", "category", "color",
    "min_price", "max_price", "clear_filters",
]

def normalize(value, field):
    if field in {"min_price", "max_price"}:
        return None if value is None else Decimal(str(value)).normalize()
    if field == "clear_filters":
        return sorted(value or [])
    return value

async def predict(client, prompt, case):
    payload = {
        "model": settings.LLM_MODEL,
        "messages": [
            {"role": "system", "content": prompt},
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "previous_filters": case.get("previous_filters", {}),
                        "conversation_history": case.get("history", [])[-4:],
                        "current_customer_message": case["message"],
                    },
                    ensure_ascii=False,
                    default=str,
                ),
            },
        ],
        "max_tokens": 256,
        "chat_template_kwargs": {"enable_thinking": False},
        "temperature": 0,
    }

    response = await client.post(
        f"{settings.LLM_BASE_URL.rstrip('/')}/chat/completions",
        json=payload,
    )
    response.raise_for_status()
    data = response.json()
    choice = data["choices"][0]

    if choice.get("finish_reason") == "length":
        raise ValueError("Model output was truncated")

    parsed = _parse_json_object(choice["message"]["content"])
    return ChatIntent.model_validate(parsed).model_dump(mode="json")

async def evaluate_case(client, prompt, case):
    try:
        actual = await predict(client, prompt, case)
        expected = case["expected"]
        errors = {
            field: {
                "expected": expected.get(field),
                "actual": actual.get(field),
            }
            for field in FIELDS
            if normalize(expected.get(field), field)
            != normalize(actual.get(field), field)
        }
        return {
            "id": case["id"],
            "message": case["message"],
            "expected": expected,
            "actual": actual,
            "exact_match": not errors,
            "field_errors": errors,
            "error": None,
        }
    except Exception as exc:
        return {
            "id": case["id"],
            "message": case["message"],
            "expected": case["expected"],
            "actual": None,
            "exact_match": False,
            "field_errors": {},
            "error": f"{type(exc).__name__}: {exc}",
        }

async def main():
    cases = [
        json.loads(line)
        for line in CASES_FILE.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if len(cases) != 40:
        raise SystemExit(f"Expected 40 dev cases, found {len(cases)}")

    prompts = {
        "v3": INTENT_SYSTEM_PROMPT,
        "v4_1": CANDIDATE_PROMPT.read_text(encoding="utf-8").strip(),
        "v4_2": (
            ROOT / "experiments" / "prompt-v4-20261018" / "prompt_v4_2.txt"
        ).read_text(encoding="utf-8").strip(),
        "v4_3": (
            ROOT / "experiments" / "prompt-v4-20261018" / "prompt_v4_3.txt"
        ).read_text(encoding="utf-8").strip(),
    }

    timeout = httpx.Timeout(settings.LLM_TIMEOUT_SECONDS)
    async with httpx.AsyncClient(timeout=timeout) as client:
        for version, prompt in prompts.items():
            results = []
            print(f"\n========== {version.upper()} ==========")

            for index, case in enumerate(cases, start=1):
                result = await evaluate_case(client, prompt, case)
                results.append(result)
                status = "PASS" if result["exact_match"] else "FAIL"
                print(f'[{index}/{len(cases)}] {status} {case["id"]}')

                if result["field_errors"]:
                    print("  Field errors:", json.dumps(
                        result["field_errors"], ensure_ascii=False
                    ))
                if result["error"]:
                    print("  Runtime error:", result["error"])

            output = EXP / f"results_{version}_40dev.jsonl"
            output.write_text(
                "".join(
                    json.dumps(result, ensure_ascii=False) + "\n"
                    for result in results
                ),
                encoding="utf-8",
            )

            exact = sum(r["exact_match"] for r in results)
            print(f"\nExact match: {exact}/{len(results)} = {exact / len(results):.1%}")

            valid = [r for r in results if r["actual"] is not None]
            print(f"Valid predictions: {len(valid)}/{len(results)}")

            for field in FIELDS:
                correct = sum(
                    normalize(r["expected"].get(field), field)
                    == normalize(r["actual"].get(field), field)
                    for r in valid
                )
                if valid:
                    print(f"{field}: {correct}/{len(valid)} = {correct / len(valid):.1%}")

            print("Saved:", output)

if __name__ == "__main__":
    asyncio.run(main())
