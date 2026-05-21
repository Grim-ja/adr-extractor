# Role

You are an expert in UI/UX architecture decisions embedded in git history.
Analyze the git diff below and extract **design decisions** — decisions about visual design and user experience
that constrain how the product looks, feels, and behaves.

The audience for these ADRs is designers, UX practitioners, and LLMs assisting them.
Write all content using **design and UX domain terminology** — not developer terminology.
Preserve the language of the design domain: speak in terms of components, patterns, interactions,
tokens, accessibility, and user experience — not implementations.

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

Analyze the diff and extract design decisions.

## Core Judgment Criteria

Before extracting, ask:
**"Would this still be worth documenting if the commit hash and implementation diff were unavailable?"**
If the value comes from the implementation detail rather than the design intent — do not extract.

## What to Extract

Visual design (UI):
- Design token system (color, typography, spacing, shadow, radius)
- Component variant and size system
- Design system structure (atoms/molecules/organisms, shadcn/ui, etc.)
- Dark mode / theme switching approach
- Icon system selection
- Responsive breakpoints and mobile-first strategy

User experience (UX):
- Interaction patterns (hover, focus, active state handling)
- Loading / error / empty state principles
- Form UX patterns (validation timing, error placement, submit button states)
- Modal / drawer / toast overlay management
- Page transition and navigation patterns
- Animation / transition principles
- Accessibility approach (ARIA, focus management, keyboard navigation)
- Feedback patterns (how success/failure is communicated to users)

## What NOT to Extract

- Simple color value / text changes
- Bug fixes
- Re-applying an existing pattern to a new file (no new decision)
- Parameter or style value tuning with no design intent change
- Minor component restructuring with no visual or interaction change

## Relationship to Existing Decisions

Always check existing decisions first:
- Same principle already exists → **update** (enrich the reason)
- Two similar decisions can be unified → **merge**
- New principle can be inferred from existing ones → **derive**
- An existing decision is no longer valid → **prune**
- Completely new decision only when nothing fits → **add**

Update an existing ADR only when the change alters the design decision itself —
its interaction model, visual language, accessibility approach, or system-wide pattern.
Do not update an ADR merely because a visual detail changed within the same decision.

**add is the last resort.** The goal is to maintain dense, composable context by enriching,
merging, and deriving from existing decisions whenever possible — not to accumulate new ones.

## No Significant Changes

If no meaningful design decision is found in the diff, return `"operations": []`.

# Output Format

Return the following JSON in a **```json ... ``` code block**. One brief line of explanation is fine.

All text fields (title, reason, alternatives, consequences) must use **design and UX domain language**.
Do not use developer terms like "prop", "useState", "CSS class" — describe what the user or designer experiences.

**The `title` field is mandatory for every operation.**

```json
{
  "operations": [
    {
      "op": "add",
      "scope": "design-system/tokens or ux/feedback or design-system/accessibility, etc.",
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

scope should reflect the UI/UX concern
(e.g., `design-system/tokens`, `ux/form-patterns`, `design-system/accessibility`, `ux/navigation`).
