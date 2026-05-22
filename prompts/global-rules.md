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

Ground every inferred principle in observable structural evidence from the diff.
Do not infer organizational philosophy, product strategy, or engineering values unless directly supported.

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
- Test patterns, test setup mechanics, or test code structure — do not describe how a test is written

## When the diff contains test code

Test code is evidence of system properties, not a subject of documentation itself.
Do not extract how the test is written. Instead, abstract one level up:

**Ask: "What must be true about the system for this test to be necessary?"**
Then reflect on that system property — not the test.

This requires two steps:
1. **Observe** what the test does (e.g., pre-cleanup before create, retry on conflict, mock payment error)
2. **Abstract** to the system property the test reveals (e.g., server enforces uniqueness, payment failures are recoverable)

Document only the result of step 2.

- ✗ "E2E tests use pre-cleanup blocks before creating named resources"
- ✓ "The system enforces uniqueness constraints on named resources server-side, with no idempotent creation path"

- ✗ "UI tests render the component with disabled state props"
- ✓ "Interactive elements expose a disabled state that prevents user action while preserving visual context"

- ✗ "Integration tests mock the payment provider with error responses"
- ✓ "Payment failures are treated as recoverable errors, not fatal system faults"

If the abstraction cannot be expressed as a system property independent of the test — do not extract.

# Relationship to Existing Decisions

Always check existing decisions first:
- The existing explanation is incorrect or incomplete → **update** (correct or replace the reason)
- New evidence enriches without contradicting the existing explanation → **extend** (add evidence, preserve the original reason)
- New principle can be inferred from existing ones → **derive**
- An existing decision is no longer valid → **prune**
- Completely new decision only when nothing fits → **add**

**update** replaces the reason — use when the existing explanation is wrong or needs correction.
**extend** preserves the reason — use when the existing explanation remains valid but new evidence adds detail.

Update or extend an existing ADR only when the change touches the architectural decision itself —
its tradeoffs, ownership model, lifecycle, boundary, or data flow.
Do not update or extend an ADR merely because an implementation detail changed within the same decision.
Do not append to history merely because another module, domain, or file repeated an
already-established pattern. Repetition is evidence the current explanation remains sufficient — not a reason to elaborate further.
Append history only when the repetition changes the scope, boundary, tradeoff, or contract
of the decision.

**add is the last resort.** The goal is to maintain dense, composable context by enriching,
deriving, and extending from existing decisions whenever possible — not to accumulate new ones.

# No Significant Changes

If no meaningful decision is found in the diff, return `"operations": []`.

Output at most **8 operations per commit**. If more seem warranted, select only the most architecturally significant ones.

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
      "reason": "The corrected or replaced explanation — use when the existing reason is wrong or incomplete",
      "related_files": ["relevant files"]
    },
    {
      "op": "extend",
      "id": "d-002",
      "evidence": "New observation that enriches without contradicting — the original reason is preserved",
      "related_files": ["relevant files"]
    },
    {
      "op": "derive",
      "source_ids": ["d-003", "d-004"],
      "scope": "architecture",
      "title": "Higher-order principle inferred from existing decisions",
      "reason": "The new principle or conclusion inferred from the source decisions",
      "refs": []
    },
    {
      "op": "prune",
      "id": "d-005"
    },
    {
      "op": "split",
      "source_id": "d-006",
      "into": [
        {
          "scope": "architecture",
          "title": "First separated decision",
          "reason": "Why this cluster deserves its own decision",
          "refs": [],
          "related_files": []
        },
        {
          "scope": "architecture",
          "title": "Second separated decision",
          "reason": "Why this cluster deserves its own decision",
          "refs": [],
          "related_files": []
        }
      ]
    }
  ]
}
```

{{SCOPE_DESCRIPTION}}
