# Global Rules

## Core Judgment Criteria

Before extracting, ask:
**"Would this still be worth documenting if the commit hash and implementation diff were unavailable?"**
If the value comes from the implementation detail rather than the design intent — do not extract.

## What NOT to Extract

- Bug fixes (value changes only, no logic change)
- Typo fixes, comment additions
- Re-applying an existing pattern to a new file (no new decision)
- Parameter tuning (threshold values, timeouts, retry counts, batch sizes, etc.)
- Logging / debug output additions or removals
- Minor refactors with no behavioral change (renaming, reordering, extracting helpers)
- Small error handling or fallback syntax changes
- Implementation detail changes within an already-documented decision

## Relationship to Existing Decisions

Always check existing decisions first:
- Same principle already exists → **update** (enrich the reason)
- Two similar decisions can be unified → **merge**
- New principle can be inferred from existing ones → **derive**
- An existing decision is no longer valid → **prune**
- Completely new decision only when nothing fits → **add**

Update an existing ADR only when the change alters the architectural decision itself —
its tradeoffs, ownership model, lifecycle, boundary, or data flow.
Do not update an ADR merely because an implementation detail changed within the same decision.

**add is the last resort.** The goal is to maintain dense, composable context by enriching,
merging, and deriving from existing decisions whenever possible — not to accumulate new ones.

## No Significant Changes

If no meaningful decision is found in the diff, return `"operations": []`.

# Output Format

Return the following JSON in a **```json ... ``` code block**. One brief line of explanation is fine.

**The `title` field is mandatory for every operation.**

If the decision is inferred from code changes rather than explicitly stated in docs, commit messages,
or comments, prefix the `reason` field with `"Inferred:"`.

```json
{
  "operations": [
    {
      "op": "add",
      "scope": "{{SCOPE_EXAMPLE}}",
      "title": "One-line summary (max 40 chars, required)",
      "reason": "Why this decision was made — include specific evidence from the diff. 2-4 sentences.",
      "alternatives": ["Alternative that was considered"],
      "consequences": ["Trade-offs of this decision"],
      "refs": [],
      "related_files": ["File paths relevant to this decision from the diff"]
    },
    {
      "op": "update",
      "id": "d-001",
      "reason": "What enriches or corrects the existing reason — include new evidence",
      "related_files": ["relevant files"]
    }
  ]
}
```

{{SCOPE_DESCRIPTION}}
