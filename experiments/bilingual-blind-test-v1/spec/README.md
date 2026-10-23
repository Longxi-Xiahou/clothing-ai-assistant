# Bilingual Blind Test v1

## Purpose

Evaluate the Clothing AI Assistant's intent classification and filter extraction
on Chinese and English inputs using a held-out test set.

This dataset is intended for final evaluation, not prompt tuning.

## Dataset size

- Chinese: 100 cases
- English: 100 cases
- Total: 200 cases

Cases should be naturally phrased and must not be simple translations or
near-duplicates of existing development cases.

## Coverage per language

- General clothing knowledge and advice: 15
- New product search: 20
- Modify existing filters: 20
- Clear filters: 15
- Colloquial, elliptical, and ambiguous requests: 15
- Conflict and boundary cases: 15

Total per language: 100 cases.

## Case schema

Each JSONL record must contain:

- id: unique case identifier
- language: zh or en
- group: one of the six coverage groups above
- message: current user message
- history: prior conversation messages
- previous_filters: existing filter state
- expected: expected ChatIntent fields

Expected fields:

- intent
- action
- category
- color
- min_price
- max_price
- clear_filters

## Validation rules

- IDs must be unique.
- Each language must contain exactly 100 cases.
- Group counts must match the planned allocation.
- Every JSONL line must parse as a JSON object.
- Expected values must satisfy the production ChatIntent schema.
- min_price must not exceed max_price when both are set.
- A field must not be assigned a new value and cleared in the same response.
- Clear operations must refer to active filters when the case is intended
  to remove an existing filter.
- General requests must not contain product-search actions or filter updates.

## Evaluation

Report results separately for Chinese and English, as well as overall:

- Exact match across all expected fields
- Schema-valid prediction rate
- Accuracy for intent and action
- Accuracy for category, color, min_price, max_price, and clear_filters
- Results by coverage group

Use identical evaluation cases and inference settings when comparing models
or prompt versions.

## Blind-test protection

- Do not use this test set for prompt tuning or training.
- Keep case authoring and answer-key review separate from iterative development.
- Do not revise the prompt repeatedly based on blind-test failures and then
  report the same test result as an unbiased final score.
- Record dataset version, model version, prompt version, and inference settings.

## Data provenance

Record the source and authoring method for every case.
Do not copy existing development cases or use simple translations as substitutes
for independent test examples.
