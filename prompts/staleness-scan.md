# Role

You are performing maintenance on an Architecture Decision Records (ADR) collection.
The decisions below have been flagged for review because structural signals suggest
their current explanation may no longer be the strongest supported one.

Your task: determine whether each decision should be kept, corrected, or retired.

# Review Candidates

```json
{{STALENESS_CANDIDATES}}
```

The `change_summaries` field shows commit subjects that touched each decision's related files
after the decision was last updated. This is context for your judgment — not evidence of obsolescence.

# Instructions

For each candidate decision, review:
1. The current `reason` — does it still represent the strongest currently-supported explanation?
2. The `change_summaries` — do the changes suggest the architectural direction has shifted?
3. The staleness signals that triggered this review (S1: source of derive/split, S2: related files deleted, S3: overlapping new ADR added, S4: related files changed repeatedly without update)

## Decision criteria

**keep** — The current explanation remains valid. The changes do not contradict or supersede it.

**update** — The explanation is directionally correct but needs correction.
Use update only to correct the current reason, title, or consequences.
Do not elaborate with new examples. Do not extend the scope.

**prune** — The decision no longer applies. The architectural pattern it described has been
replaced, removed, or fully absorbed into other decisions.

**When in doubt, keep.**

## Critical constraints

This scan is for maintenance, not discovery.
Do not create new ADRs.
Do not add new observations.
Do not use extend.
Choose keep, update, or prune only.

## Output Format

Return the following JSON in a **```json ... ``` code block**.

Omit decisions you choose to keep — they are handled automatically.
Include update and prune operations, and for kept decisions include a `keep` operation
with a `new_score` — your assessment of how stale this decision actually is
(0.0 = fully valid and current; {{THRESHOLD}} or above = will trigger re-examination).

```json
{
  "operations": [
    {
      "op": "update",
      "id": "d-003",
      "reason": "Corrected explanation — what changed and why the previous reason was incomplete or wrong",
      "related_files": ["relevant files if changed"]
    },
    {
      "op": "prune",
      "id": "d-007"
    },
    {
      "op": "keep",
      "id": "d-005",
      "new_score": 0.5
    }
  ]
}
```

If all candidates should be kept:
```json
{
  "operations": [
    {"op": "keep", "id": "d-003", "new_score": 0.8},
    {"op": "keep", "id": "d-007", "new_score": 0.2}
  ]
}
```
