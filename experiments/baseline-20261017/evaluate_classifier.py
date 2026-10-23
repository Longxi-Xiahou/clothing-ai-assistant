import asyncio
import json
import sys
from collections import defaultdict
from pathlib import Path

from fastapi import HTTPException
from pydantic import ValidationError

from app.services.intent_classifier import classify_intent

ROOT = Path(__file__).resolve().parent
CASES = ROOT / "classifier_cases.jsonl"
RESULTS = ROOT / "classifier_results.jsonl"
FILTERS = ("category", "color", "min_price", "max_price", "clear_filters")


def norm(value):
    if isinstance(value, list):
        return sorted(value)
    if value is None:
        return None
    return str(value).lower() if isinstance(value, str) else str(value)


async def main():
    cases = [json.loads(line) for line in CASES.read_text().splitlines() if line.strip()]
    counts = defaultdict(lambda: [0, 0])
    rows = []

    for case in cases:
        expected = case["expected"]
        row = {
            "id": case["id"],
            "group": case["group"],
            "message": case["message"],
            "expected": expected,
        }
        try:
            result = await classify_intent(
                message=case["message"],
                previous_filters=case.get("previous_filters", {}),
                history=case.get("history", []),
            )
            actual = result.model_dump(mode="json")
            row["actual"] = actual
            row["valid_schema"] = True
            for field in ("intent", "action", *FILTERS):
                if field in expected:
                    ok = norm(actual.get(field)) == norm(expected[field])
                    counts[field][1] += 1
                    counts[field][0] += int(ok)
            row["correct"] = all(
                norm(actual.get(k)) == norm(v) for k, v in expected.items()
            )
            row["error"] = None
        except Exception as exc:
            row["actual"] = None
            row["valid_schema"] = False
            row["correct"] = False
            row["error"] = {
                "type": type(exc).__name__,
                "detail": str(exc)[:500],
            }

        rows.append(row)
        status = "PASS" if row["correct"] else "FAIL"
        print(f'{status} {case["id"]} [{case["group"]}] {case["message"]}')
        if row["error"]:
            print("   ERROR:", row["error"]["type"], row["error"]["detail"])

    RESULTS.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))
    print("\n===== BASELINE SUMMARY =====")
    print(f"Cases: {len(cases)}")
    print(f"Exact expected-field match: {sum(r['correct'] for r in rows)}/{len(rows)} "
          f"({100 * sum(r['correct'] for r in rows) / max(len(rows), 1):.1f}%)")
    print(f"Valid schema / successful calls: {sum(r['valid_schema'] for r in rows)}/{len(rows)}")
    for field, (correct, total) in sorted(counts.items()):
        print(f"{field}: {correct}/{total} ({100 * correct / total:.1f}%)")
    print(f"Detailed results: {RESULTS}")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit(130)
