# Synthetic clothing catalog

Contains 59 synthetic demo products, intended for development/testing, not real inventory.

- `products.json`: product records with canonical English filter values and Chinese display text in `attributes.name_zh` and `attributes.description_zh`.
- `import_products.py`: idempotent importer; skips existing SKUs and does not overwrite existing records.

Copy this folder to `<project>/scripts/seed_catalog/`, back up the DB, inspect the JSON, then run:
`.venv/bin/python scripts/seed_catalog/import_products.py`

Verify counts afterward. Each added record is marked `attributes.synthetic_test_data=true`.
