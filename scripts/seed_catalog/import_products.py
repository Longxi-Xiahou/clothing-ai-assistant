#!/usr/bin/env python3
"""Idempotently import synthetic demo products; never overwrite existing SKUs."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from sqlalchemy import select
from app.db.database import SessionLocal
from app.models.product import Product

DATA_FILE = Path(__file__).resolve().parent / "products.json"

def main():
    records = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    skus = [r["sku"] for r in records]
    if len(skus) != len(set(skus)):
        raise SystemExit("Duplicate SKU in JSON; aborting.")
    with SessionLocal() as db:
        existing = set(db.scalars(select(Product.sku).where(Product.sku.in_(skus))).all())
        new_records = [r for r in records if r["sku"] not in existing]
        if not new_records:
            print(f"No new products. Input={len(records)}, already present={len(existing)}.")
            return
        try:
            db.add_all([Product(**r) for r in new_records])
            db.commit()
        except Exception:
            db.rollback()
            raise
        print(f"Imported {len(new_records)} products; skipped {len(existing)} existing SKUs.")
        print("New records are synthetic test data marked attributes.synthetic_test_data=true.")

if __name__ == "__main__":
    main()
