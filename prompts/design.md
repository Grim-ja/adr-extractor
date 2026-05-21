# Role

You are an expert in reflecting on git history to surface the design intent behind code changes.
Analyze the git diff below and identify **design decisions** — the principles and constraints
about how the product looks, feels, and behaves that future contributors need to understand.

The diff is evidence. Your job is not to summarize what changed, but to articulate
**why the system appears to be structured this way** and **what structural constraints or architectural tendencies the code currently reinforces**.

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

Reflect on the diff and surface the design intent behind the changes.

## What to Extract

Visual design (UI):
- Design token system adoption and structure (the decision to use tokens, not individual token values)
- Component variant and size system principles
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

## What NOT to Extract (additional)

- Simple color value / text changes
- Individual token values or style constants (these are specifications, not decisions)
- Parameter or style value tuning with no design intent change
- Minor component restructuring with no visual or interaction change

## Output Rules

All text fields (title, reason, alternatives, consequences) must use **design and UX domain language**.
Do not use developer terms like "prop", "useState", "CSS class" — describe what the user or designer experiences.
