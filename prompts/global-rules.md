# Core Judgment Criteria

Before reflecting, ask:
**"What constraint, tradeoff, or principle does this code reveal?"**
If the answer is only "something was added or changed" — that is a summary, not a decision. Do not extract.

The diff is evidence of a decision, not the decision itself.
Surface the best current explanation: what structural design direction does this code suggest,
and what is the simplest principle that accounts for the observed structure?

# Describing Decisions: Principle not Fact

Always describe the architectural principle, not the observable fact:

- ✗ "A `responses.rs` module was added containing DTO definitions"
- ✓ "Response types are co-located with their domain module to enforce ownership boundaries"

- ✗ "The project API returns a region-keyed map"
- ✓ "Inferred: The client normalizes region-keyed API envelopes at the infra layer so domain logic receives flat lists"

- ✗ "JWT tokens with 7-day expiry are issued"
- ✓ "User sessions remain active for 7 days — a deliberate tradeoff between convenience and security"

The reason field must answer: **why was the system designed this way**, not **what the diff shows**.

# Inference Discipline

Prefer the simplest explanation that fits the observed evidence.
If a simpler principle accounts for the same structural facts, use that instead of a more elaborate one.

ADRs capture the strongest currently-supported explanation of the system's architectural structure.
New evidence may refine or overturn that explanation.
Do not defend an existing ADR against contradicting evidence; revise it.

# What NOT to Extract

- Bug fixes (value changes only, no logic change)
- Typo fixes, comment additions
- Re-applying an existing pattern to a new file (no new decision)
- Parameter tuning (threshold values, timeouts, retry counts, batch sizes, etc.)
- Logging / debug output additions or removals
- Minor refactors with no behavioral change (renaming, reordering, extracting helpers)
- Small error handling or fallback syntax changes
- Implementation detail changes within an already-documented decision
- Individual API endpoints, URL structures, HTTP methods, or DTO field definitions
- Entity or schema field lists (these are specifications, not decisions)
- Feature scope lists (what exists) — extract only when a deliberate scoping decision was made
- Facts imposed by an external API — extract only the client-side architectural policy for handling them

# Relationship to Existing Decisions

Always check existing decisions first:
- Same principle already exists → **update** (enrich the reason)
- Two similar decisions can be unified → **merge**
- New principle can be inferred from existing ones → **derive**
- An existing decision is no longer valid → **prune**
- Completely new decision only when nothing fits → **add**

Update an existing ADR only when the change alters the architectural decision itself —
its tradeoffs, ownership model, lifecycle, boundary, or data flow.
Do not update an ADR merely because an implementation detail changed within the same decision.
Do not append to history merely because another module, domain, or file repeated an
already-established pattern. Repetition is evidence the current explanation remains sufficient — not a reason to elaborate further.
Append history only when the repetition changes the scope, boundary, tradeoff, or contract
of the decision.

**add is the last resort.** The goal is to maintain dense, composable context by enriching,
merging, and deriving from existing decisions whenever possible — not to accumulate new ones.

# No Significant Changes

If no meaningful decision is found in the diff, return `"operations": []`.

# Output Format

Return the following JSON in a **```json ... ``` code block**. One brief line of explanation is fine.

**The `title` field is mandatory for every operation.**

The `reason` field must describe the architectural principle this code embodies —
what it reveals about how the system is designed to work, and why that choice was made.
If the decision is inferred from code changes rather than explicitly stated in docs, commit messages,
or comments, prefix the `reason` field with `"Inferred:"`.

```json
{
  "operations": [
    {
      "op": "add",
      "scope": "{{SCOPE_EXAMPLE}}",
      "title": "One-line summary (max 40 chars, required)",
      "reason": "The strongest currently-supported explanation of why the system appears to be structured this way, based on the evidence observed so far. 2-4 sentences.",
      "alternatives": ["Alternative that was considered"],
      "consequences": ["Trade-offs of this decision"],
      "refs": [],
      "related_files": ["File paths relevant to this decision from the diff"]
    },
    {
      "op": "update",
      "id": "d-001",
      "reason": "The principle this enriches or corrects — what new insight the diff reveals about the existing decision",
      "related_files": ["relevant files"]
    }
  ]
}
```

{{SCOPE_DESCRIPTION}}
