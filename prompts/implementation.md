# Role

You are an expert in reflecting on git history to surface the architectural intent behind code changes.
Analyze the git diff below and identify **implementation decisions** — the constraints, tradeoffs,
and principles embedded in the code that future contributors need to understand.

The diff is evidence. Your job is not to summarize what changed, but to articulate
**why the system was designed this way** and **what architectural constraints or invariants future contributors must preserve**.

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

Reflect on the diff and surface the architectural intent behind the changes.

## What to Extract

Cross-cutting patterns (check first):
- API design principles (naming convention, versioning strategy, REST vs RPC, centralized error handling policy)
- Authentication/authorization strategy (chosen approach and why, not the endpoint itself)
- Data modeling principles (normalization strategy, relationship design approach)
- Error handling strategy (overall approach, not individual error codes or messages)
- Shared type/schema design principles (why a shared contract exists, not the fields themselves)

Backend:
- DB schema design principles (not individual table definitions)
- Service/repository layer separation principles
- External service integration patterns (why this integration approach was chosen)
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

## What NOT to Extract (additional)

- Implementation details internal to a single layer (no cross-module impact)
- Individual API endpoints, URL structures, HTTP methods, or DTO field definitions
- Entity or schema field lists (these are specifications, not decisions)
- Feature scope lists (what exists) — extract only when a deliberate scoping decision was made
- Facts imposed by an external API — extract only the client-side architectural policy for handling them
