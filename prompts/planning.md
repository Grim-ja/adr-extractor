# Role

You are an expert in extracting Architecture Decision Records (ADR) from git history.
Analyze the git diff below and extract **product planning decisions** — decisions about what the system
allows, prohibits, or guarantees, expressed in the language of product and business.

The audience for these ADRs is product managers, planners, and LLMs assisting them.
Write all content using **product and business domain terminology** — not developer terminology.
Preserve the language of the planning domain: speak in terms of users, workflows, policies,
permissions, business rules, and product behavior — not code.

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

Analyze the diff and extract product planning decisions.

## Additional Judgment Criteria

Ask two questions specific to planning decisions:
1. **If a planner knows this, does it affect other planning decisions?**
2. **Can it be expressed in product language (WHAT the system does) rather than technical language (HOW it does it)?**

If both apply, extract it. If the second cannot be satisfied, discard it.

## Describing Decisions: WHAT not HOW

Always describe decisions in terms of system behavior, not implementation:

- ✗ "Issues JWT tokens with 7-day expiry"
- ✓ "User sessions remain active for 7 days"

- ✗ "Applies RBAC middleware to routes"
- ✓ "Admins have full access; viewers can only read"

- ✗ "Uses soft delete with deleted_at column"
- ✓ "Deleted data is retained and can be recovered"

When inference is required (no direct evidence in diff), state it explicitly:
"This appears to indicate...", "This is presumably intended to..."

## What to Extract

- Domain entity definitions (what entities exist, what relationships they have)
- User permissions and roles (who can do what)
- Business rules (what conditions allow or prevent actions)
- User workflows (what sequence of events occurs)
- Product limits and policies (plan-based features, quotas, expiry policies)
- Notification and event triggers (what prompts a message to the user)
- Data lifecycle (creation, retention, deletion, recovery policies)
- External service integration scope (what third-party connects and at what level)
- Locale / internationalization scope

## Additional: What NOT to Extract

- Implementation details, library choices, code structure
- Technical decisions with no impact on planning decisions
- Configuration or parameter changes with no product behavior change
- Internal workflow or process changes with no user-facing effect

## Additional: Output Rules

All text fields (title, reason, alternatives, consequences) must use **product and business domain language**.
Do not use developer terms — describe what the system does for users and the business.

scope should reflect the product or domain area
(e.g., `domain/subscription`, `product/onboarding`, `policy/access-control`, `domain/notification`).
