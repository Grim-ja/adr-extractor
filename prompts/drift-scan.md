# Role

You are an expert in detecting boundary drift in Architecture Decision Records (ADR).
The decisions below have accumulated a high divergence score, indicating that a single decision
may now contain content that belongs to two or more distinct concerns.

Analyze each decision's history and determine whether a split is warranted.

# Drift Candidate Decisions

```json
{{DRIFT_CANDIDATES}}
```

# Instructions

Read through each decision's `history` entries in order and determine:

## When to Split

- History entries clearly address two or more distinct concerns
- Each cluster would stand independently with its own scope and rationale
- The current title/scope no longer represents some history entries accurately

## When NOT to Split

- History entries are deepening or enriching the same concern
- Changes exist but remain within the bounds of one coherent decision
- Splitting would fragment context rather than clarify it

**When in doubt, do not split.**

## Output Format

Return the following JSON in a **```json ... ``` code block**.

Include only decisions that require a split. For decisions that do not need splitting,
include a `keep` operation with a `new_score` — your assessment of how much divergence
actually exists (0.0 = no divergence at all; {{THRESHOLD}} or above = will trigger re-examination).

```json
{
  "operations": [
    {
      "op": "split",
      "source_id": "d-007",
      "into": [
        {
          "scope": "scope representing the first cluster",
          "title": "Title for the first cluster (max 40 chars)",
          "reason": "Core rationale of this cluster",
          "alternatives": [],
          "consequences": [],
          "refs": [],
          "related_files": ["files relevant to this cluster"]
        },
        {
          "scope": "scope representing the second cluster",
          "title": "Title for the second cluster (max 40 chars)",
          "reason": "Core rationale of this cluster",
          "alternatives": [],
          "consequences": [],
          "refs": [],
          "related_files": ["files relevant to this cluster"]
        }
      ]
    },
    {
      "op": "keep",
      "id": "d-008",
      "new_score": 0.4
    }
  ]
}
```

If no decisions require splitting (all should be kept):
```json
{
  "operations": [
    {"op": "keep", "id": "d-007", "new_score": 0.5},
    {"op": "keep", "id": "d-008", "new_score": 0.2}
  ]
}
```
