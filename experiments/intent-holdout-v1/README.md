# Intent Classifier Independent Holdout v1

## Purpose

Evaluate the frozen Qwen3-14B intent classifier on new bilingual cases
that were not used to develop or revise the prompt.

The existing 200-case bilingual-blind-test-v1 dataset is a development
set, not an independent holdout.

## Planned size

- Chinese: 100 cases
- English: 100 cases
- Total: 200 cases

## Planned groups per language

- general_and_product_search: 15
- new_search_and_modify_filters: 25
- clear_filters: 15
- context_and_multi_turn: 20
- colloquial_and_ambiguous: 15
- boundary_and_conflict: 10

## Annotation rules

1. Label the current customer message using the supplied previous_filters
   and conversation history.
2. The expected output describes the current message's intent and filter
   changes, not the fully merged final filter state.
3. For modify_filters, unchanged fields must be null.
4. For a changed field, return the new value and do not clear that field.
5. For an explicitly removed field, set its value to null and include
   its name in clear_filters.
6. For new_search, extract only criteria stated in the current message;
   clear_filters must be empty.
7. For general intent, action must be general, filter fields must be null,
   and clear_filters must be empty.
8. Do not infer unspecified categories, colors, or prices.
9. Resolve ambiguous labels using the full conversation context.
10. Contradictory price constraints must be annotated according to an
    explicit policy agreed before model evaluation. Do not silently
    invent a resolution.
11. Cases must be newly authored rather than created by simple substitution
    of colors, categories, or prices in the development cases.
12. Review expected labels before running the frozen model.

## Evaluation safeguards

- Do not modify the frozen prompt based on holdout results.
- Record prompt and source hashes before evaluation.
- Keep model outputs and reports in reports/.
- If holdout cases are used to revise the prompt, reclassify them as
  development data and create a new holdout for future claims.

## Status

Preparation only. Cases have not yet been authored, reviewed, or evaluated.
