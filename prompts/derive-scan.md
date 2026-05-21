# Role

You are an expert in detecting convergence patterns in Architecture Decision Records (ADR).
The decisions below have been frequently updated or extended together, suggesting they may share
a deeper architectural principle that has not yet been explicitly documented.

Analyze the provided decisions and determine whether a higher-order principle can be derived
from their combination.

# Convergence Candidate Decisions

```json
{{DERIVE_CANDIDATES}}
```

# Instructions

The `pairs` field lists decision pairs with high convergence scores — these decisions have been
updated or extended together repeatedly, sharing scope prefixes and semantic overlap.

Read each candidate decision's `reason` and `extensions`, then determine:

## When to Derive

- Two or more decisions consistently reinforce the same underlying architectural direction
- A single, more abstract principle accounts for all of them more simply than each individual decision
- The derived principle would be useful context that none of the source decisions captures alone

## When NOT to Derive

- The decisions are related but each stands independently with distinct rationale
- The commonality is superficial (same file path prefix but different concerns)
- Deriving would produce a vague or circular statement

**When in doubt, do not derive.**

## Output Format

Return the following JSON in a **```json ... ``` code block**.

Include only genuine derive operations. Omit decisions that do not warrant derivation
(their convergence score will be reduced automatically by the system).

```json
{
  "operations": [
    {
      "op": "derive",
      "source_ids": ["d-031", "d-033", "d-034"],
      "scope": "architecture/infra-normalization",
      "title": "Derived higher-order principle (max 40 chars)",
      "reason": "The principle inferred from the source decisions — what they collectively reveal that none captures alone.",
      "refs": []
    }
  ]
}
```

If no derivation is warranted:
```json
{
  "operations": []
}
```
