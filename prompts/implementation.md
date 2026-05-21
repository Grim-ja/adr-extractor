# Role

You are an expert in extracting Architecture Decision Records (ADR) from git history.
Analyze the git diff below and extract **implementation decisions** — decisions that cut across layers,
constrain future choices, or require other modules/layers to be aware of them.

# Commit Info

- Hash: {{COMMIT_HASH}}
- Subject: {{COMMIT_SUBJECT}}
- Author: {{COMMIT_AUTHOR}}

# Git Diff

```diff
{{GIT_DIFF}}
```

# Existing Architecture Decisions

```json
{{EXISTING_DECISIONS}}
```

# Instructions

Analyze the diff and extract implementation decisions.

## Core Judgment Criteria

Before extracting, ask:
**"Would this still be worth documenting if the commit hash and implementation diff were unavailable?"**
If the value comes from the implementation detail rather than the design intent — do not extract.

## What to Extract

Cross-cutting patterns (check first):
- API contracts (endpoint structure, response format, error spec)
- Authentication/authorization method (token delivery, permission model)
- Data model / domain entity definitions
- Error handling conventions (status codes, error object shape)
- Type/schema contracts (shared types, zod schemas, etc.)

Backend:
- DB schema / ORM model design
- Service/repository layer separation principles
- External service integration patterns
- Caching, queue, event handling approach
- Environment variable / config management

Frontend:
- Component design principles (separation criteria, composition patterns)
- State management strategy (server state vs client state distinction)
- Routing structure and layout nesting approach
- Styling method selection

Architecture:
- Monorepo / multi-repo structure
- Layered architecture principles (dependency direction rules)
- Technology stack selection (framework, runtime, language)
- Inter-service communication approach
- Infrastructure / CI/CD structure
- Observability strategy (logging, metrics, tracing)

## What NOT to Extract

- Bug fixes (value changes only, no logic change)
- Typo fixes, comment additions
- Re-applying an existing pattern to a new file (no new decision)
- Implementation details internal to a single layer (no cross-module impact)
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

If no meaningful design decision is found in the diff, return `"operations": []`.

# Output Format

Return the following JSON in a **```json ... ``` code block**. One brief line of explanation is fine.

**The `title` field is mandatory for every operation.**

```json
{
  "operations": [
    {
      "op": "add",
      "scope": "src/api/auth or architecture/layers or src/components/common, etc.",
      "title": "One-line summary (max 40 chars, required)",
      "reason": "Why this decision was made — include specific evidence from the diff. 2-4 sentences. If the decision is inferred from code changes rather than explicitly stated in docs, commit messages, or comments, prefix with \"Inferred:\".",
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

scope should reflect the code path or conceptual layer impacted
(e.g., `src/api/auth`, `architecture/module-boundaries`, `src/components/common`, `infrastructure/docker`).
