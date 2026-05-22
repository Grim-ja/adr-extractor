# git-adr

Walks a git repository from the initial commit and accumulates Architecture Decision Records (ADR)
by reflecting on each commit's diff with an LLM.

## How it works

For each commit, the tool extracts the diff, filters noise (lock files, binaries, generated files),
and asks an LLM to reflect on the architectural intent behind the changes — not to summarize what
changed, but to surface the constraints, tradeoffs, and principles the code commits future
contributors to. Results are accumulated in `decisions.json`.

On subsequent runs, `--resume` picks up from the last processed commit, so incremental updates
as new commits land are supported out of the box.

## File structure

```
adr/
  git-adr.py              - main script
  anthropic-llm.py        - Anthropic API wrapper (stdin → stdout)
  decisions.sh            - query tool for decisions.json
  prompts/
    global-rules.md       - shared extraction rules (composed into every target prompt)
    implementation.md     - implementation target: architecture, layers, tech stack
    design.md             - design target: UI/UX, design system, interaction patterns
    planning.md           - planning target: business rules, domain model, policies
    drift-scan.md         - boundary drift detection prompt
```

## Usage

### Anthropic API

```bash
export ANTHROPIC_API_KEY=your_key_here
python3 git-adr.py \
  --repo /path/to/repo \
  --target implementation \
  --output ./adr-output/ \
  --llm-cmd "python3 /path/to/anthropic-llm.py" \
  --skip-repo-scan \
  --save-every 5
```

### OpenAI-compatible API

```bash
python3 git-adr.py \
  --repo /path/to/repo \
  --target implementation \
  --output ./adr-output/ \
  --api-base https://api.openai.com/v1 \
  --api-key $OPENAI_API_KEY \
  --model gpt-4o
```

### Custom LLM CLI

Any CLI that reads a prompt from stdin and writes the response to stdout:

```bash
python3 git-adr.py \
  --repo /path/to/repo \
  --target implementation \
  --output ./adr-output/ \
  --llm-cmd "my-llm --model claude"
```

### Export to CLAUDE.md (Claude Code integration)

After running git-adr, inject the ADR summary into your repo's `CLAUDE.md` so
Claude Code automatically loads decision history at session start:

```bash
python3 git-adr.py \
  --export-claude-md \
  --output ./adr-output/ \
  --repo /path/to/repo
```

This upserts a `## Architecture Decisions` section with `<!-- adr:start --> / <!-- adr:end -->`
boundary markers. Re-running is safe — only the section between the markers is replaced;
existing content in `CLAUDE.md` is preserved.

The section contains `active` decisions from `decisions.json` serialized as a JSON block,
sorted by `documentDate` descending. Total output is capped at 8 KB.

> **Note (v1 limitation):** `--export-claude-md` writes a single section regardless of which
> `--target` produced the `decisions.json`. If you run multiple targets into separate output
> directories, export each one separately — the last write wins. Per-target marker scoping
> is planned for v2.

### Resume after interruption

```bash
python3 git-adr.py \
  --repo /path/to/repo \
  --target implementation \
  --output ./adr-output/ \
  --llm-cmd "python3 anthropic-llm.py" \
  --resume
```

### Dry-run (no LLM calls)

```bash
python3 git-adr.py \
  --repo /path/to/repo \
  --target implementation \
  --output ./test-adr/ \
  --api-base https://api.openai.com/v1 \
  --api-key dummy \
  --dry-run --limit 10 --verbose
```

## Targets

| Target | Focus | Typical use |
|--------|-------|-------------|
| `implementation` | Architecture, layers, tech stack, cross-cutting patterns | Most repositories |
| `design` | UI/UX decisions, design system, interaction patterns | Design system / component repos |
| `planning` | Business rules, domain model, permissions, policies | Product-centric analysis |

Multiple targets can be run against the same repo into separate output directories:

```bash
python3 git-adr.py --repo . --target implementation --output ./adr/impl/ ...
python3 git-adr.py --repo . --target planning --output ./adr/planning/ ...
```

## File-based filtering

On first run without `--skip-repo-scan`, the tool scans the repo structure and asks the LLM
to generate a `.adr-filters.yaml` tailored to the project layout. Subsequent runs reuse this file.

To skip the scan and use built-in defaults:

```bash
python3 git-adr.py ... --skip-repo-scan
```

To provide a custom filter file:

```bash
python3 git-adr.py ... --filters-file ./my-filters.yaml
```

Filter format:

```yaml
implementation:
  include:
    - "src/**"
    - "*.toml"
  exclude:
    - "**/*.sh"
    - "CHANGELOG.md"

design:
  include:
    - "**/components/**"
    - "**/*.css"
  exclude:
    - "**/*.test.*"

planning:
  include:
    - "docs/**"
    - "prisma/**"
  exclude:
    - "**/*.test.*"
```

Files not matched by any include pattern trigger a fallback to the full diff with a warning,
so no commit is silently skipped.

## All options

```
Required:
  --repo PATH             git repository to analyze
  --target TARGET         implementation | design | planning
  --output DIR            directory for decisions.json output

LLM (one required):
  --api-base URL          OpenAI-compatible API base URL
  --llm-cmd CMD           custom LLM CLI (stdin prompt → stdout response)

API options:
  --api-key KEY           API key (or OPENAI_API_KEY env var)
  --model MODEL           model name (default: gpt-4o)

Filter options:
  --skip-repo-scan        skip LLM repo scan; use defaults or existing .adr-filters.yaml
  --filters-file PATH     path to filter file (default: <repo>/.adr-filters.yaml)

Drift detection:
  --drift-threshold N     divergence score threshold to trigger drift scan (default: 2.0)
  --no-drift-scan         disable drift scan

Run control:
  --resume                resume from last processed commit
  --from-commit HASH      start processing after this commit hash
  --limit N               max commits to process (for testing)
  --max-diff N            max diff size in characters (default: 12000)
  --context-lines N       git diff context lines (default: 5)
  --save-every N          save every N commits (default: 1)
  --dry-run               extract diffs without calling LLM
  --verbose, -v           verbose output
```

## Output files

| File | Description |
|------|-------------|
| `decisions.json` | accumulated ADR data |
| `.adr-state.json` | run state: last processed commit hash, processed count |

## decisions.json schema

```json
{
  "decisions": [
    {
      "id": "d-001",
      "status": "active",
      "documentDate": "2026-05-21",
      "commitDate": "2026-03-11",
      "scope": "src/infra",
      "title": "Three-layer CLI architecture (cli/domain/infra)",
      "reason": "...",
      "alternatives": ["..."],
      "consequences": ["..."],
      "refs": [],
      "related_files": ["src/infra/mod.rs"],
      "derived_from": null,
      "divergence_score": 0.0,
      "history": []
    }
  ]
}
```

`status` is one of `active` or `superseded`. Superseded decisions are retained for history
but excluded from the canonical summary passed to the LLM on subsequent runs.

`divergence_score` accumulates when an `update` operation adds content that diverges structurally
from the existing decision (different file seams, low keyword overlap in reason). When it crosses
`--drift-threshold`, a separate drift scan LLM call evaluates whether the decision should be split.

## Querying decisions.json

```bash
# full canonical list
DECISIONS_FILE=./adr-output/decisions.json ./decisions.sh --canonical

# specific decision with evidence
DECISIONS_FILE=./adr-output/decisions.json ./decisions.sh --id d-001 --evidence

# decisions related to a file
DECISIONS_FILE=./adr-output/decisions.json ./decisions.sh --file src/infra/api_client.rs

# decisions by scope
DECISIONS_FILE=./adr-output/decisions.json ./decisions.sh --scope architecture
```
