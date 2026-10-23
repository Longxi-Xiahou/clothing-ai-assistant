import asyncio
import json
import sys
from collections import Counter, defaultdict
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from app.services.intent_classifier import classify_intent

EXP = ROOT / "experiments" / "bilingual-blind-test-v1"
CASES = EXP / "cases" / "blind_test_v1.jsonl"
REPORTS = EXP / "reports"
RESULTS = REPORTS / "results_v1.jsonl"
SUMMARY = REPORTS / "evaluation_summary_v1.json"

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


def load_cases():
    with CASES.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


async def evaluate_one(case):
    result = {
        "id": case["id"],
        "language": case["language"],
        "group": case["group"],
        "message": case["message"],
        "expected": case["expected"],
        "actual": None,
        "exact_match": False,
        "field_errors": {},
        "error": None,
    }

    try:
        prediction = await classify_intent(
            message=case["message"],
            previous_filters=case.get("previous_filters") or {},
            history=case.get("history") or [],
        )
        actual = prediction.model_dump(mode="json")
        result["actual"] = actual

        errors = {}
        for field in FIELDS:
            expected_value = normalize(case["expected"].get(field), field)
            actual_value = normalize(actual.get(field), field)

            if expected_value != actual_value:
                errors[field] = {
                    "expected": case["expected"].get(field),
                    "actual": actual.get(field),
                }

        result["field_errors"] = errors
        result["exact_match"] = not errors

    except Exception as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"

    return result


def rate(correct, total):
    return round(correct / total, 4) if total else None


def summarize(results):
    summary = {
        "dataset": str(CASES.relative_to(ROOT)),
        "total": len(results),
        "exact_match": {},
        "field_accuracy": {},
        "by_language": {},
        "by_group": {},
        "runtime_errors": sum(r["error"] is not None for r in results),
    }

    total = len(results)
    exact = sum(r["exact_match"] for r in results)
    summary["exact_match"] = {
        "correct": exact,
        "total": total,
        "accuracy": rate(exact, total),
    }

    for field in FIELDS:
        correct = sum(
            r["actual"] is not None
            and normalize(r["expected"].get(field), field)
            == normalize(r["actual"].get(field), field)
            for r in results
        )
        summary["field_accuracy"][field] = {
            "correct": correct,
            "total": total,
            "accuracy": rate(correct, total),
        }

    for dimension in ("language", "group"):
        buckets = defaultdict(list)
        for r in results:
            buckets[r[dimension]].append(r)

        key = "by_language" if dimension == "language" else "by_group"
        for name, subset in sorted(buckets.items()):
            correct = sum(r["exact_match"] for r in subset)
            summary[key][name] = {
                "correct": correct,
                "total": len(subset),
                "accuracy": rate(correct, len(subset)),
                "runtime_errors": sum(r["error"] is not None for r in subset),
            }

    return summary


async def main():
    REPORTS.mkdir(parents=True, exist_ok=True)
    cases = load_cases()

    if not cases:
        raise SystemExit(f"No cases found: {CASES}")

    print(f"Dataset: {CASES}")
    print(f"Cases: {len(cases)}")
    print("Starting sequential evaluation; this may take a while.")

    results = []
    for i, case in enumerate(cases, start=1):
        result = await evaluate_one(case)
        results.append(result)

        status = "PASS" if result["exact_match"] else "FAIL"
        print(f"[{i:03d}/{len(cases)}] {status} {case['id']}")

        if result["field_errors"]:
            print("  Field errors:", json.dumps(
                result["field_errors"], ensure_ascii=False
            ))
        if result["error"]:
            print("  Runtime error:", result["error"])

    with RESULTS.open("w", encoding="utf-8") as f:
        for result in results:
            f.write(json.dumps(result, ensure_ascii=False) + "\n")

    summary = summarize(results)
    SUMMARY.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print("\n===== OVERALL EXACT MATCH =====")
    print(json.dumps(summary["exact_match"], indent=2))
    print("\n===== FIELD ACCURACY =====")
    print(json.dumps(summary["field_accuracy"], indent=2))
    print("\n===== BY LANGUAGE =====")
    print(json.dumps(summary["by_language"], indent=2))
    print("\n===== BY GROUP =====")
    print(json.dumps(summary["by_group"], indent=2))
    print("\nRuntime errors:", summary["runtime_errors"])
    print("Results:", RESULTS)
    print("Summary:", SUMMARY)


if __name__ == "__main__":
    asyncio.run(main())
