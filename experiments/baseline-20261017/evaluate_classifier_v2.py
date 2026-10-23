import asyncio
import json
import sys
from collections import defaultdict
from pathlib import Path

import httpx
from fastapi import HTTPException

from app.services.intent_classifier import classify_intent

ROOT = Path(__file__).resolve().parent
CASES = ROOT / "classifier_cases.jsonl"
RESULTS = ROOT / "classifier_results-v2.jsonl"
FIELDS = ("intent", "action", "category", "color",
          "min_price", "max_price", "clear_filters")


def norm(value):
    if isinstance(value, list):
        return sorted(str(v).lower() for v in value)
    if value is None:
        return None
    if isinstance(value, str):
        return value.lower()
    return str(value)


def classify_error(exc):
    if isinstance(exc, HTTPException):
        detail = str(exc.detail).lower()
        if exc.status_code == 504:
            return "timeout_error"
        if exc.status_code == 503:
            return "transport_error"
        if "invalid json data" in detail:
            return "response_json_error"
        if "invalid intent classification" in detail:
            # The classifier currently maps parse and schema failures
            # to the same HTTP detail, so do not guess which occurred.
            return "invalid_model_output"
        if exc.status_code == 502:
            return "upstream_http_error"
        return "http_error"
    if isinstance(exc, httpx.TimeoutException):
        return "timeout_error"
    if isinstance(exc, httpx.RequestError):
        return "transport_error"
    return "unexpected_error"


async def main():
    cases = [
        json.loads(line)
        for line in CASES.read_text().splitlines()
        if line.strip()
    ]
    rows = []
    field_counts = defaultdict(lambda: [0, 0])
    errors = defaultdict(int)
    successful_calls = 0
    exact_matches = 0

    for case in cases:
        expected = case["expected"]
        row = {
            "id": case["id"],
            "group": case["group"],
            "message": case["message"],
            "expected": expected,
            "call_success": False,
            "schema_valid": None,
            "error_type": None,
            "exact_match": False,
            "actual": None,
        }

        try:
            result = await classify_intent(
                message=case["message"],
                previous_filters=case.get("previous_filters", {}),
                history=case.get("history", []),
            )
            actual = result.model_dump(mode="json")
            row["actual"] = actual
            row["call_success"] = True
            row["schema_valid"] = True
            successful_calls += 1

            row["exact_match"] = all(
                norm(actual.get(key)) == norm(value)
                for key, value in expected.items()
            )
            exact_matches += int(row["exact_match"])

            for field in FIELDS:
                if field in expected:
                    field_counts[field][1] += 1
                    field_counts[field][0] += int(
                        norm(actual.get(field)) == norm(expected[field])
                    )

        except Exception as exc:
            row["error_type"] = classify_error(exc)
            row["error"] = {
                "type": type(exc).__name__,
                "detail": str(
                    exc.detail if isinstance(exc, HTTPException) else exc
                )[:500],
            }
            errors[row["error_type"]] += 1

        rows.append(row)
        status = "PASS" if row["exact_match"] else "FAIL"
        print(
            f'{status} {row["id"]} '
            f'call_success={row["call_success"]} '
            f'error={row["error_type"]}'
        )

    RESULTS.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows)
    )

    total = len(cases)
    print("\n===== EVALUATION SUMMARY V2 =====")
    print(f"Total cases: {total}")
    print(f"Successful calls: {successful_calls}/{total}")
    print(f"Schema-valid results: {successful_calls}/{total}")
    print(f"Exact matches: {exact_matches}/{total}")
    print(f"Exact match rate: {100 * exact_matches / max(total, 1):.1f}%")
    print(f"Errors: {dict(errors)}")
    print("\nField accuracy (successful calls only):")
    for field, (correct, count) in sorted(field_counts.items()):
        print(
            f"{field}: {correct}/{count} "
            f"({100 * correct / max(count, 1):.1f}%)"
        )
    print(f"\nResults saved to: {RESULTS}")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit(130)
