#!/bin/bash
# decisions.sh — decisions.json hierarchy reader
#
# ── 모드별 추천 조회 전략 ──
# PLAN:  --canonical 전체 + 관련 범위 --evidence + 필요시 --history
# IMPL:  --file <대상파일> → 매칭된 decision의 canonical + evidence
# SPEC:  --canonical 전체
# EVAL:  기본 생략. public contract/architecture drift 의심 시 --file
# FIX-UNIT: 기본 생략. public contract 의심 시만 --file
#
# Usage:
#   ./scripts/decisions.sh --canonical
#   ./scripts/decisions.sh --id d-014 --history
#   ./scripts/decisions.sh --id d-014 --history --full
#   ./scripts/decisions.sh --id d-014 --evidence
#   ./scripts/decisions.sh --file src/services/review/jira-intake.service.ts
#   ./scripts/decisions.sh --scope architecture

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export DECISIONS_FILE="${DECISIONS_FILE:-$SCRIPT_DIR/../tasks/decisions.json}"

python3 - "$@" <<'PYEOF'
import json
import os
import re
import sys


def first_sentence(text):
    if not text:
        return ""
    m = re.search(r'\.\s+[A-Z`]', text)
    if m:
        return text[:m.start() + 1].strip()
    return text.strip()


def second_sentence(text):
    if not text:
        return ""
    m = re.search(r'\.\s+[A-Z`]', text)
    if not m:
        return ""
    remainder = text[m.start() + 1:].lstrip()
    m2 = re.search(r'\.\s+[A-Z`]', remainder)
    if m2:
        return remainder[:m2.start() + 1].strip()
    return remainder.strip()


def make_summary(d):
    reason = d.get("reason", "")
    s1 = first_sentence(reason)
    # If first sentence looks like a merge note, use second sentence
    if re.match(r'd-0\d+', s1) or "are exact duplicates" in s1:
        s2 = second_sentence(reason)
        if s2:
            return s2
        return d.get("title", "")
    return s1 if s1 else d.get("title", "")


def canonical_entry(d, match_type=None):
    entry = {
        "id": d.get("id"),
        "status": d.get("status"),
        "title": d.get("title"),
        "scope": d.get("scope"),
        "summary": make_summary(d),
        "derived_from": [],
    }
    df = d.get("derived_from")
    if isinstance(df, list):
        entry["derived_from"] = df
    elif df is not None:
        entry["derived_from"] = [df]
    mf = d.get("merged_from")
    if mf:
        entry["merged_from"] = mf
    sf = d.get("split_from")
    if sf:
        entry["split_from"] = sf
    hist = d.get("history", [])
    if isinstance(hist, list) and len(hist) > 0:
        entry["history_count"] = len(hist)
    rf = d.get("related_files", [])
    if isinstance(rf, list) and len(rf) > 0:
        entry["related_files_count"] = len(rf)
    if match_type is not None:
        entry["match_type"] = match_type
    return entry


def load_decisions():
    decisions_file = os.environ.get("DECISIONS_FILE", "tasks/decisions.json")
    try:
        with open(decisions_file, encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"Error: {decisions_file} not found", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Error: invalid JSON in {decisions_file}: {e}", file=sys.stderr)
        sys.exit(1)
    return data.get("decisions", [])


def build_alias_index(decisions):
    """Build reverse index: old_id -> current_id for merged_from entries."""
    index = {}
    for d in decisions:
        mf = d.get("merged_from")
        if mf:
            for old_id in mf:
                index[old_id] = d.get("id")
    return index


def resolve_id(target_id, alias_index):
    """Returns (resolved_id, alias_message_or_None)."""
    if target_id in alias_index:
        new_id = alias_index[target_id]
        return new_id, f"(alias: {target_id} → {new_id}, merged)"
    return target_id, None


def parse_args(argv):
    mode = None
    target_id = None
    files = []
    scope = None
    full_history = False

    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg == "--canonical":
            mode = "canonical"
        elif arg == "--history":
            if mode not in ("evidence",):
                mode = "history"
        elif arg == "--full":
            full_history = True
        elif arg == "--evidence":
            mode = "evidence"
        elif arg == "--id":
            i += 1
            if i >= len(argv):
                print("Error: --id requires a value", file=sys.stderr)
                sys.exit(1)
            target_id = argv[i]
        elif arg == "--file":
            i += 1
            if i >= len(argv):
                print("Error: --file requires a value", file=sys.stderr)
                sys.exit(1)
            files.append(argv[i])
            if mode not in ("canonical", "history", "evidence", "scope"):
                mode = "file"
        elif arg == "--scope":
            i += 1
            if i >= len(argv):
                print("Error: --scope requires a value", file=sys.stderr)
                sys.exit(1)
            scope = argv[i]
            mode = "scope"
        i += 1

    return mode, target_id, files, scope, full_history


def file_matches(file_arg, d):
    """
    Returns match_type: 'direct', 'scoped', or None.
    - direct: file_arg is in related_files (exact or prefix)
    - scoped: decision's scope is a prefix of file_arg
    """
    rf = d.get("related_files", [])
    # direct match: file_arg equals a related_file, OR file_arg is a directory
    # prefix of a related_file, OR the other way (related_file is a prefix of file_arg)
    for rf_path in rf:
        if file_arg == rf_path:
            return "direct"
        # directory prefix: --file src/services/review/ matches src/services/review/foo.ts
        if file_arg.endswith("/") and rf_path.startswith(file_arg):
            return "direct"
        # partial path containment (legacy behaviour)
        if file_arg in rf_path or rf_path in file_arg:
            return "direct"

    # scoped match: scope is a path prefix of file_arg
    scope = d.get("scope", "")
    if scope and file_arg.startswith(scope):
        return "scoped"

    return None


def main():
    argv = sys.argv[1:]

    if not argv:
        print(
            "Usage: decisions.sh [--canonical | --id <id> [--history [--full]] | "
            "--id <id> --evidence | --file <path> [--file <path> ...] | --scope <scope>]",
            file=sys.stderr,
        )
        sys.exit(1)

    mode, target_id, files, scope, full_history = parse_args(argv)

    decisions = load_decisions()
    alias_index = build_alias_index(decisions)
    id_map = {d["id"]: d for d in decisions}

    if mode == "canonical":
        result = [canonical_entry(d) for d in decisions]
        print(json.dumps(result, ensure_ascii=False, indent=2))

    elif mode == "history":
        if not target_id:
            print("Error: --id required for --history", file=sys.stderr)
            sys.exit(1)
        resolved_id, alias_msg = resolve_id(target_id, alias_index)
        if alias_msg:
            print(alias_msg, file=sys.stderr)
        d = id_map.get(resolved_id)
        if not d:
            print(f"Error: decision {resolved_id} not found", file=sys.stderr)
            sys.exit(1)
        history = d.get("history", [])
        if full_history:
            print(json.dumps(history, ensure_ascii=False, indent=2))
        else:
            # 2-tier summary: date + type + reason truncated to 80 chars
            summary = []
            for h in history:
                reason_preview = (h.get("reason", "") or "")[:80]
                if len(h.get("reason", "")) > 80:
                    reason_preview += "..."
                summary.append({
                    "date": h.get("date"),
                    "action": h.get("action"),
                    "reason_preview": reason_preview,
                })
            print(json.dumps(summary, ensure_ascii=False, indent=2))

    elif mode == "evidence":
        if not target_id:
            print("Error: --id required for --evidence", file=sys.stderr)
            sys.exit(1)
        resolved_id, alias_msg = resolve_id(target_id, alias_index)
        if alias_msg:
            print(alias_msg, file=sys.stderr)
        d = id_map.get(resolved_id)
        if not d:
            print(f"Error: decision {resolved_id} not found", file=sys.stderr)
            sys.exit(1)
        all_files = d.get("related_files", [])
        # representative_files: non-spec files first, max 4
        non_spec = [f for f in all_files if not f.endswith(".spec.ts") and not f.endswith(".spec.js")]
        spec_files = [f for f in all_files if f not in non_spec]
        representative = (non_spec + spec_files)[:4]
        rest = [f for f in all_files if f not in representative]
        result = {
            "id": d.get("id"),
            "summary": make_summary(d),
            "representative_files": representative,
            "all_related_files": rest,
            "refs": d.get("refs", []),
            "full_reason": d.get("reason", ""),
            "alternatives": d.get("alternatives", []),
            "consequences": d.get("consequences", []),
        }
        print(json.dumps(result, ensure_ascii=False, indent=2))

    elif mode == "file":
        # Build direct + scoped matches first
        matched = {}  # id -> (decision, match_type)
        for d in decisions:
            did = d.get("id")
            if did in matched:
                continue
            for file_arg in files:
                mt = file_matches(file_arg, d)
                if mt:
                    matched[did] = (d, mt)
                    break

        # Derived: for each direct/scoped match, find decisions that reference them
        # via derived_from or merged_from
        primary_ids = set(matched.keys())
        for d in decisions:
            did = d.get("id")
            if did in matched:
                continue
            df = d.get("derived_from") or []
            if isinstance(df, str):
                df = [df]
            mf = d.get("merged_from") or []
            refs = set(df) | set(mf)
            if refs & primary_ids:
                matched[did] = (d, "derived")

        # Output in original decisions order
        result = []
        for d in decisions:
            did = d.get("id")
            if did in matched:
                _, mt = matched[did]
                result.append(canonical_entry(d, match_type=mt))
        print(json.dumps(result, ensure_ascii=False, indent=2))

    elif mode == "scope":
        matched = [
            canonical_entry(d)
            for d in decisions
            if scope in d.get("scope", "")
        ]
        print(json.dumps(matched, ensure_ascii=False, indent=2))

    else:
        print(
            "Usage: decisions.sh [--canonical | --id <id> [--history [--full]] | "
            "--id <id> --evidence | --file <path> [--file <path> ...] | --scope <scope>]",
            file=sys.stderr,
        )
        sys.exit(1)


main()
PYEOF