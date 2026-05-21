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

## Additional: What NOT to Extract

- Implementation details internal to a single layer (no cross-module impact)
