# Prompt-v3 Challenge Dataset Specification

## Purpose
Evaluate the frozen prompt-v3 on unseen intent-classification cases.
Do not tune the prompt on this dataset.

## JSONL schema
Each line is one JSON object with:
- id: unique string, CH001 through CH100
- group: scenario group
- message: current user message
- previous_filters: prior category, color, min_price, max_price
- history: prior dialogue messages
- expected: complete ChatIntent output

## Expected output fields
- intent: general | product_search
- action: new_search | modify_filters | general
- category: string or null
- color: string or null
- min_price: number or null
- max_price: number or null
- clear_filters: array containing unique values from
  category, color, min_price, max_price

## Scenario allocation
- general: 15
- new_search: 20
- modify_filters: 20
- clear_filters: 15
- colloquial_ambiguous: 15
- conflict_boundary: 15
Total: 100

## Annotation rules
- Keep every turn from the same dialogue in one group_id-equivalent grouping.
- Group is the scenario label, not the model's action.
- expected describes the classifier output, not merged filters.
- For modify_filters, unspecified filters should normally remain null in
  expected so the merger preserves previous values.
- For new_search, unspecified filters should normally remain null and the
  merger resets previous filters.
- For general, use intent=general, action=general, null filter values,
  and an empty clear_filters list.
- Never set and clear the same field in one expected output.
- Keep price bounds valid and non-negative.
- Product availability in the current database must not determine the
  classification label.
- Manually review every expected label before freezing the dataset.

## Evaluation protocol
- Freeze challenge_cases.jsonl and record its SHA-256 before inference.
- Run the frozen prompt-v3 without edits.
- Do not tune the prompt using challenge results.
- If prompt changes are made based on these results, this dataset becomes
  development data; a new untouched final test set will be required.
