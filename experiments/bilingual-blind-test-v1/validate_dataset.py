import argparse
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from pydantic import ValidationError
from app.schemas.chat_intent import ChatIntent
from app.services.filter_merger import merge_filters

EXPECTED_FIELDS = {
    "intent",
    "action",
    "category",
    "color",
    "min_price",
    "max_price",
    "clear_filters",
}


def main():
    parser = argparse.ArgumentParser(
        description="Validate the bilingual blind-test dataset."
    )
    parser.add_argument(
        "path",
        nargs="?",
        default=(
            "experiments/bilingual-blind-test-v1/"
            "cases/blind_test_v1.jsonl"
        ),
    )
    parser.add_argument("--check-quota", action="store_true")
    args = parser.parse_args()

    path = Path(args.path)
    if not path.is_absolute():
        path = ROOT / path

    if not path.exists():
        print(f"Dataset not created yet: {path}")
        return

    errors = []
    records = []

    with path.open(encoding="utf-8") as file:
        for line_no, line in enumerate(file, start=1):
            if not line.strip():
                continue
            try:
                case = json.loads(line)
            except json.JSONDecodeError as exc:
                errors.append(f"Line {line_no}: invalid JSON: {exc}")
                continue

            if not isinstance(case, dict):
                errors.append(f"Line {line_no}: record must be an object")
                continue

            records.append((line_no, case))

    ids = []
    languages = Counter()
    groups = Counter()
    messages = set()

    for line_no, case in records:
        case_id = case.get("id", f"line-{line_no}")
        required = {
            "id",
            "language",
            "group",
            "message",
            "history",
            "previous_filters",
            "expected",
        }

        missing = required - case.keys()
        if missing:
            errors.append(f"{case_id}: missing fields {sorted(missing)}")
            continue

        ids.append(case["id"])
        language = case["language"]
        group = case["group"]

        if language not in {"zh", "en"}:
            errors.append(f"{case_id}: language must be zh or en")
        else:
            languages[language] += 1

        if not isinstance(case["message"], str) or not case["message"].strip():
            errors.append(f"{case_id}: message must be non-empty")

        if not isinstance(case["history"], list):
            errors.append(f"{case_id}: history must be a list")

        previous = case["previous_filters"]
        expected = case["expected"]

        if not isinstance(previous, dict):
            errors.append(f"{case_id}: previous_filters must be an object")
            continue

        if not isinstance(expected, dict):
            errors.append(f"{case_id}: expected must be an object")
            continue

        missing_expected = EXPECTED_FIELDS - expected.keys()
        extra_expected = expected.keys() - EXPECTED_FIELDS

        if missing_expected or extra_expected:
            errors.append(
                f"{case_id}: expected fields mismatch; "
                f"missing={sorted(missing_expected)}, "
                f"extra={sorted(extra_expected)}"
            )
            continue

        try:
            intent = ChatIntent.model_validate(expected)
        except ValidationError as exc:
            errors.append(f"{case_id}: schema validation failed: {exc}")
            continue

        if intent.action == "modify_filters" and intent.intent == "product_search":
            groups[(language, group)] += 1

        inactive_clears = [
            field for field in intent.clear_filters
            if previous.get(field) is None
        ]
        if inactive_clears:
            errors.append(
                f"{case_id}: clearing inactive filters {inactive_clears}"
            )

        try:
            merge_filters(previous, intent)
        except (ValueError, TypeError) as exc:
            errors.append(f"{case_id}: filter merge failed: {exc}")

        message_key = (language, case["message"].strip().casefold())
        if message_key in messages:
            errors.append(f"{case_id}: duplicate message within {language}")
        messages.add(message_key)

    duplicate_ids = [
        value
        for value, count in Counter(ids).items()
        if count > 1
    ]
    if duplicate_ids:
        errors.append(f"Duplicate IDs: {sorted(duplicate_ids)}")

    if args.check_quota:
        expected_group_counts = {
            "general": 15,
            "new_search": 20,
            "modify_filters": 20,
            "clear_filters": 15,
            "colloquial_ambiguous": 15,
            "conflict_boundary": 15,
        }

        for lang in ("zh", "en"):
            if languages[lang] != 100:
                errors.append(
                    f"{lang}: expected 100 cases, got {languages[lang]}"
                )

        for lang in ("zh", "en"):
            for group, expected_count in expected_group_counts.items():
                actual_count = sum(
                    1 for _, case in records
                    if case.get("language") == lang
                    and case.get("group") == group
                )
                if actual_count != expected_count:
                    errors.append(
                        f"{lang}/{group}: expected {expected_count}, "
                        f"got {actual_count}"
                    )

    print(f"Dataset: {path}")
    print(f"Parsed records: {len(records)}")
    print(f"Language counts: {dict(languages)}")

    if errors:
        print(f"\nFAILED: {len(errors)} issue(s)")
        for error in errors:
            print("-", error)
        raise SystemExit(1)

    print("\nPASSED: JSON, schema, and merge checks succeeded")


if __name__ == "__main__":
    main()
