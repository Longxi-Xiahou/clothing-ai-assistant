import asyncio
import json
import sys
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from app.schemas.chat_intent import ChatIntent
from app.services.intent_classifier import classify_intent

EXPERIMENT_DIR = Path(__file__).resolve().parent
CASES_FILE = EXPERIMENT_DIR / "cases.jsonl"
RESULTS_FILE = EXPERIMENT_DIR / "results.jsonl"

FIELDS = [
    "intent",
    "action",
    "category",
    "color",
    "min_price",
    "max_price",
    "clear_filters",
]


def normalize(value, field=None):
    if field in {"min_price", "max_price"}:
        if value is None:
            return None
        return Decimal(str(value)).normalize()

    if isinstance(value, Decimal):
        return str(value.normalize())
    if isinstance(value, list):
        return [normalize(item) for item in value]
    return value


def load_cases():
    with CASES_FILE.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


async def evaluate_case(case):
    try:
        prediction = await classify_intent(
            message=case["message"],
            previous_filters=case.get("previous_filters", {}),
            history=case.get("history", []),
        )
        actual = prediction.model_dump(mode="json")
        errors = {
            field: {
                "expected": str(normalize(case["expected"].get(field), field)),
                "actual": str(normalize(actual.get(field), field)),
            }
            for field in FIELDS
            if normalize(case["expected"].get(field), field)
            != normalize(actual.get(field), field)
        }
        return {
            "id": case["id"],
            "message": case["message"],
            "expected": case["expected"],
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
    cases = load_cases()
    if not cases:
        raise SystemExit("No evaluation cases found.")

    results = []
    for index, case in enumerate(cases, start=1):
        result = await evaluate_case(case)
        results.append(result)
        status = "PASS" if result["exact_match"] else "FAIL"
        print(f'[{index}/{len(cases)}] {status} {case["id"]}: {case["message"]}')
        if result["field_errors"]:
            print("  Field errors:", json.dumps(
                result["field_errors"], ensure_ascii=False
            ))
        if result["error"]:
            print("  Runtime error:", result["error"])

    with RESULTS_FILE.open("w", encoding="utf-8") as f:
        for result in results:
            f.write(json.dumps(result, ensure_ascii=False) + "\n")

    print("\n=== Baseline summary ===")
    exact = sum(result["exact_match"] for result in results)
    print(f"Exact match: {exact}/{len(results)} = {exact / len(results):.1%}")

    for field in FIELDS:
        eligible = [r for r in results if r["actual"] is not None]
        correct = sum(
            normalize(r["expected"].get(field), field)
            == normalize(r["actual"].get(field), field)
            for r in eligible
        )
        if eligible:
            print(
                f"{field}: {correct}/{len(eligible)} "
                f"= {correct / len(eligible):.1%}"
            )

    print(f"\nResults saved to: {RESULTS_FILE}")


if __name__ == "__main__":
    asyncio.run(main())
