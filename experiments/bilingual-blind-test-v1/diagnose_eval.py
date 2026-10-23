import asyncio
import json
import sys
from pathlib import Path
from collections import Counter
from decimal import Decimal

import httpx

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from app.core.config import settings
from app.schemas.chat_intent import ChatIntent
from app.services.intent_classifier import (
    INTENT_SYSTEM_PROMPT,
    _parse_json_object,
)

EXP = ROOT / "experiments" / "bilingual-blind-test-v1"
CASES = EXP / "cases" / "blind_test_v1.jsonl"
REPORTS = EXP / "reports"
OUT = REPORTS / "diagnostics_v1.jsonl"

FIELDS = [
    "intent", "action", "category", "color",
    "min_price", "max_price", "clear_filters",
]


def norm(v, field):
    if field in ("min_price", "max_price"):
        return None if v is None else Decimal(str(v)).normalize()
    if field == "clear_filters":
        return sorted(v or [])
    return v


async def diagnose(client, case):
    result = {
        "id": case["id"],
        "language": case["language"],
        "group": case["group"],
        "message": case["message"],
        "expected": case["expected"],
        "raw_content": None,
        "parsed_json": None,
        "validated": False,
        "actual": None,
        "field_errors": {},
        "diagnostic_error": None,
        "http_status": None,
        "finish_reason": None,
    }

    payload = {
        "model": settings.LLM_MODEL,
        "messages": [
            {"role": "system", "content": INTENT_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "previous_filters": case.get("previous_filters") or {},
                        "conversation_history": (case.get("history") or [])[-4:],
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

    try:
        response = await client.post(
            f"{settings.LLM_BASE_URL.rstrip('/')}/chat/completions",
            json=payload,
        )
        result["http_status"] = response.status_code
        response.raise_for_status()
        data = response.json()

        choice = data["choices"][0]
        result["finish_reason"] = choice.get("finish_reason")
        content = choice["message"]["content"]
        result["raw_content"] = content

        if not isinstance(content, str) or not content.strip():
            raise ValueError("Empty model response")

        parsed = _parse_json_object(content)
        result["parsed_json"] = parsed

        prediction = ChatIntent.model_validate(parsed)
        actual = prediction.model_dump(mode="json")
        result["actual"] = actual
        result["validated"] = True

        errors = {}
        for field in FIELDS:
            expected = norm(case["expected"].get(field), field)
            observed = norm(actual.get(field), field)
            if expected != observed:
                errors[field] = {
                    "expected": case["expected"].get(field),
                    "actual": actual.get(field),
                }
        result["field_errors"] = errors

    except Exception as exc:
        result["diagnostic_error"] = f"{type(exc).__name__}: {exc}"

    return result


async def main():
    REPORTS.mkdir(parents=True, exist_ok=True)
    cases = [
        json.loads(line)
        for line in CASES.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    timeout = httpx.Timeout(settings.LLM_TIMEOUT_SECONDS)
    results = []

    async with httpx.AsyncClient(timeout=timeout) as client:
        for i, case in enumerate(cases, 1):
            result = await diagnose(client, case)
            results.append(result)

            if not result["validated"]:
                print(
                    f'[{i:03}/{len(cases)}] INVALID {case["id"]}: '
                    f'{result["diagnostic_error"]}'
                )
                print("Raw:", repr(result["raw_content"]))
            elif result["field_errors"]:
                print(
                    f'[{i:03}/{len(cases)}] MISMATCH {case["id"]}: '
                    f'{json.dumps(result["field_errors"], ensure_ascii=False)}'
                )
            else:
                print(f'[{i:03}/{len(cases)}] PASS {case["id"]}')

    with OUT.open("w", encoding="utf-8") as f:
        for result in results:
            f.write(json.dumps(result, ensure_ascii=False) + "\n")

    invalid = [r for r in results if not r["validated"]]
    errors = Counter(
        (r["diagnostic_error"] or "").split(":", 1)[0]
        for r in invalid
    )
    field_errors = Counter(
        field
        for r in results
        for field in r["field_errors"]
    )

    print("\n===== DIAGNOSTIC SUMMARY =====")
    print("Cases:", len(results))
    print("Schema-valid outputs:", len(results) - len(invalid))
    print("Invalid outputs:", len(invalid))
    print("Invalid error types:", dict(errors))
    print("Field mismatch counts:", dict(field_errors))
    print("Saved:", OUT)


if __name__ == "__main__":
    asyncio.run(main())
