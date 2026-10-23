import asyncio
import json
from collections import Counter
from datetime import datetime
from pathlib import Path

import httpx

from app.core.config import settings
from app.schemas.chat_intent import ChatIntent
from app.services.intent_classifier import _parse_json_object

ROOT = Path(__file__).resolve().parents[2]
EXP = ROOT / "experiments" / "chinese-baseline-20261018"

WANTED_IDS = {
    "ZH001", "ZH017", "ZH018", "ZH019",
    "ZH021", "ZH022", "ZH028",
}
REPEATS = 5


def load_prompt(version):
    path = ROOT / "experiments" / "prompt-v4-20261018" / f"prompt_{version}.txt"
    return path.read_text(encoding="utf-8").strip()


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

    raw = choice["message"]["content"]
    parsed = _parse_json_object(raw)
    validated = ChatIntent.model_validate(parsed).model_dump(mode="json")

    return {"actual": validated, "raw": raw, "error": None}


async def main():
    cases = [
        json.loads(line)
        for line in (EXP / "cases_v3.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    cases = [case for case in cases if case["id"] in WANTED_IDS]

    if len(cases) != len(WANTED_IDS):
        raise SystemExit(f"Expected 7 cases, found {len(cases)}")

    prompts = {
        "v4_1": load_prompt("v4_1"),
        "v4_2": load_prompt("v4_2"),
    }

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    output = EXP / f"stability_7cases_{stamp}.jsonl"
    records = []

    timeout = httpx.Timeout(settings.LLM_TIMEOUT_SECONDS)
    async with httpx.AsyncClient(timeout=timeout) as client:
        for version, prompt in prompts.items():
            print(f"\n========== {version.upper()} ==========")

            for case in cases:
                signatures = []

                for repeat in range(1, REPEATS + 1):
                    try:
                        result = await predict(client, prompt, case)
                        record = {
                            "version": version,
                            "id": case["id"],
                            "repeat": repeat,
                            "actual": result["actual"],
                            "raw": result["raw"],
                            "error": None,
                        }
                        signature = json.dumps(
                            result["actual"], ensure_ascii=False, sort_keys=True
                        )
                    except Exception as exc:
                        record = {
                            "version": version,
                            "id": case["id"],
                            "repeat": repeat,
                            "actual": None,
                            "raw": None,
                            "error": f"{type(exc).__name__}: {exc}",
                        }
                        signature = f"ERROR: {record['error']}"

                    records.append(record)
                    signatures.append(signature)
                    print(
                        f"{case['id']} run {repeat}/{REPEATS}: "
                        f"{'OK' if record['error'] is None else 'ERROR'}"
                    )

                counts = Counter(signatures)
                print(
                    f"  Distinct outputs: {len(counts)}/{REPEATS}; "
                    f"most common output: {max(counts.values())}/{REPEATS}"
                )

    output.write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in records),
        encoding="utf-8",
    )

    print(f"\nSaved raw results: {output}")
    print(f"Total calls: {len(records)}")

    print("\n========== SUMMARY ==========")
    for version in prompts:
        print(f"\n{version}:")
        for case in cases:
            subset = [
                r for r in records
                if r["version"] == version and r["id"] == case["id"]
            ]
            signatures = [
                json.dumps(r["actual"], ensure_ascii=False, sort_keys=True)
                if r["actual"] is not None
                else f"ERROR: {r['error']}"
                for r in subset
            ]
            counts = Counter(signatures)
            print(
                f"  {case['id']}: "
                f"{len(counts)} distinct output(s), "
                f"most common {max(counts.values())}/{REPEATS}"
            )


if __name__ == "__main__":
    asyncio.run(main())
