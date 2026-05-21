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

## Additional: What NOT to Extract

- Simple color value / text changes
- Parameter or style value tuning with no design intent change
- Minor component restructuring with no visual or interaction change

## Additional: Output Rules

All text fields (title, reason, alternatives, consequences) must use **design and UX domain language**.
Do not use developer terms like "prop", "useState", "CSS class" — describe what the user or designer experiences.
