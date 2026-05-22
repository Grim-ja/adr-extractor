"""Tests for core pipeline logic: apply_operations, accumulate_*, extract_json, filters."""

import json
import sys
from pathlib import Path

import pytest

# Import the module under test directly
sys.path.insert(0, str(Path(__file__).parent))
import importlib.util
spec = importlib.util.spec_from_file_location("git_adr", Path(__file__).parent / "git-adr.py")
git_adr = importlib.util.module_from_spec(spec)
spec.loader.exec_module(git_adr)

apply_operations = git_adr.apply_operations
accumulate_divergence = git_adr.accumulate_divergence
accumulate_convergence = git_adr.accumulate_convergence
extract_json = git_adr.extract_json
should_include_file = git_adr.should_include_file
matches_any = git_adr.matches_any
truncate_diff = git_adr.truncate_diff
get_canonical_summary = git_adr.get_canonical_summary
accumulate_staleness = git_adr.accumulate_staleness


TODAY = "2026-05-22"
COMMIT_DATE = "2026-05-22"


def make_decision(
    id_,
    status="active",
    scope="src/",
    title="Test decision",
    reason="The system needs this approach for reliability. Secondary sentence.",
    related_files=None,
    divergence_score=0.0,
    staleness_score=0.0,
    last_active_commit="",
    related_churn_count=0,
    document_date="2026-01-01",
):
    return {
        "id": id_,
        "status": status,
        "documentDate": document_date,
        "commitDate": COMMIT_DATE,
        "scope": scope,
        "title": title,
        "reason": reason,
        "alternatives": [],
        "consequences": [],
        "refs": [],
        "related_files": related_files or [],
        "derived_from": None,
        "history": [],
        "extensions": [],
        "divergence_score": divergence_score,
        "staleness_score": staleness_score,
        "last_active_commit": last_active_commit,
        "last_active_date": document_date,
        "last_reviewed_commit": None,
        "last_reviewed_processed_count": -1,
        "related_churn_count": related_churn_count,
    }


def make_data(*decisions, scores=None):
    return {"decisions": list(decisions), "convergence_scores": scores or {}}


# ─── apply_operations: "add" ──────────────────────────────────────────────────

def test_add_creates_new_decision():
    data = make_data()
    ops = [{"op": "add", "scope": "src/api", "title": "REST API structure",
             "reason": "Uniform API layer reduces coupling.", "alternatives": [], "consequences": [],
             "refs": [], "related_files": ["src/api/routes.py"]}]
    result = apply_operations(data, ops, TODAY, COMMIT_DATE)
    decisions = result["decisions"]
    assert len(decisions) == 1
    assert decisions[0]["id"] == "d-001"
    assert decisions[0]["status"] == "active"
    assert decisions[0]["title"] == "REST API structure"


def test_add_increments_id_from_existing():
    data = make_data(make_decision("d-003"))
    ops = [{"op": "add", "scope": "src/", "title": "New one", "reason": "Reason.",
             "alternatives": [], "consequences": [], "refs": [], "related_files": []}]
    result = apply_operations(data, ops, TODAY, COMMIT_DATE)
    assert result["decisions"][-1]["id"] == "d-004"


# ─── apply_operations: "update" ───────────────────────────────────────────────

def test_update_modifies_existing():
    d = make_decision("d-001", reason="Old reason.")
    data = make_data(d)
    ops = [{"op": "update", "id": "d-001", "scope": "", "reason": "New reason.",
             "related_files": ["src/new.py"], "title": "", "refs": []}]
    result = apply_operations(data, ops, TODAY, COMMIT_DATE)
    updated = result["decisions"][0]
    assert updated["reason"] == "New reason."
    assert "src/new.py" in updated["related_files"]


def test_update_saves_history_entry():
    d = make_decision("d-001", reason="Original.")
    data = make_data(d)
    ops = [{"op": "update", "id": "d-001", "scope": "", "reason": "Updated.",
             "related_files": [], "title": "", "refs": None}]
    result = apply_operations(data, ops, TODAY, COMMIT_DATE)
    history = result["decisions"][0]["history"]
    assert len(history) == 1
    assert history[0]["reason"] == "Original."
    assert history[0]["action"] == "updated"


def test_update_missing_id_is_noop():
    d = make_decision("d-001")
    data = make_data(d)
    ops = [{"op": "update", "id": "d-999", "scope": "", "reason": "X",
             "related_files": [], "title": "", "refs": None}]
    result = apply_operations(data, ops, TODAY, COMMIT_DATE)
    assert result["decisions"][0]["reason"] == d["reason"]  # unchanged


# ─── apply_operations: "extend" ───────────────────────────────────────────────

def test_extend_appends_extension():
    d = make_decision("d-001")
    data = make_data(d)
    ops = [{"op": "extend", "id": "d-001", "scope": "", "evidence": "New evidence found.",
             "related_files": ["src/extra.py"]}]
    result = apply_operations(data, ops, TODAY, COMMIT_DATE)
    decision = result["decisions"][0]
    assert len(decision["extensions"]) == 1
    assert decision["extensions"][0]["evidence"] == "New evidence found."


def test_extend_unions_related_files():
    d = make_decision("d-001", related_files=["src/a.py"])
    data = make_data(d)
    ops = [{"op": "extend", "id": "d-001", "scope": "", "evidence": "Ev.",
             "related_files": ["src/b.py"]}]
    result = apply_operations(data, ops, TODAY, COMMIT_DATE)
    related = set(result["decisions"][0]["related_files"])
    assert "src/a.py" in related
    assert "src/b.py" in related


# ─── apply_operations: "prune" ────────────────────────────────────────────────

def test_prune_marks_superseded():
    d = make_decision("d-001")
    data = make_data(d)
    ops = [{"op": "prune", "id": "d-001", "scope": ""}]
    result = apply_operations(data, ops, TODAY, COMMIT_DATE)
    assert result["decisions"][0]["status"] == "superseded"


def test_prune_saves_history():
    d = make_decision("d-001", reason="Reason.")
    data = make_data(d)
    ops = [{"op": "prune", "id": "d-001", "scope": ""}]
    result = apply_operations(data, ops, TODAY, COMMIT_DATE)
    history = result["decisions"][0]["history"]
    assert any(h["action"] == "pruned" for h in history)


# ─── apply_operations: "derive" ───────────────────────────────────────────────

def test_derive_creates_with_source_ids():
    d1 = make_decision("d-001")
    d2 = make_decision("d-002")
    data = make_data(d1, d2)
    ops = [{"op": "derive", "scope": "src/shared", "title": "Shared pattern",
             "reason": "Common approach.", "alternatives": [], "consequences": [],
             "refs": [], "related_files": [], "source_ids": ["d-001", "d-002"]}]
    result = apply_operations(data, ops, TODAY, COMMIT_DATE)
    derived = result["decisions"][-1]
    assert derived["derived_from"] == ["d-001", "d-002"]
    assert derived["status"] == "active"


# ─── apply_operations: "split" ────────────────────────────────────────────────

def test_split_supersedes_source_and_creates_parts():
    d = make_decision("d-001", divergence_score=3.5)
    data = make_data(d)
    ops = [{
        "op": "split",
        "source_id": "d-001",
        "into": [
            {"scope": "src/api", "title": "Part A", "reason": "A.", "alternatives": [],
             "consequences": [], "refs": [], "related_files": []},
            {"scope": "src/db", "title": "Part B", "reason": "B.", "alternatives": [],
             "consequences": [], "refs": [], "related_files": []},
        ]
    }]
    result = apply_operations(data, ops, TODAY, COMMIT_DATE)
    decisions = result["decisions"]
    source = next(d for d in decisions if d["id"] == "d-001")
    assert source["status"] == "superseded"
    assert source["divergence_score"] == 0.0
    parts = [d for d in decisions if d["id"] != "d-001"]
    assert len(parts) == 2
    assert all(p["status"] == "active" for p in parts)


# ─── D1 REGRESSION: convergence_scores 보존 ──────────────────────────────────

def test_apply_operations_preserves_convergence_scores():
    """D1 버그 회귀 방지 — apply_operations()가 convergence_scores를 소멸시키면 안 됨."""
    d = make_decision("d-001")
    initial_scores = {"d-001:d-002": 1.8, "d-002:d-003": 0.5}
    data = make_data(d, scores=initial_scores)
    ops = [{"op": "update", "id": "d-001", "scope": "", "reason": "Updated.",
             "related_files": [], "title": "", "refs": None}]
    result = apply_operations(data, ops, TODAY, COMMIT_DATE)
    assert result.get("convergence_scores") == initial_scores, (
        "apply_operations()가 convergence_scores를 소멸시킴 (D1 버그 재발)"
    )


def test_apply_operations_preserves_arbitrary_top_level_fields():
    d = make_decision("d-001")
    data = make_data(d)
    data["extra_field"] = "preserved"
    ops = [{"op": "add", "scope": "src/", "title": "X", "reason": "Y.",
             "alternatives": [], "consequences": [], "refs": [], "related_files": []}]
    result = apply_operations(data, ops, TODAY, COMMIT_DATE)
    assert result.get("extra_field") == "preserved"


# ─── accumulate_divergence ────────────────────────────────────────────────────

def test_seam_divergence_new_top_level_dir():
    d = make_decision("d-001", related_files=["src/auth/login.py"])
    delta = accumulate_divergence(d, ["infra/docker/compose.yml"], "Different reason entirely.")
    assert delta > 0.0  # new seam "infra" vs existing "src"


def test_no_seam_divergence_same_dir():
    d = make_decision("d-001", related_files=["src/api/routes.py"])
    delta = accumulate_divergence(d, ["src/api/auth.py"], "Same area reason for auth.")
    # Only reason divergence possible, seam is identical
    assert delta < 1.5  # no seam penalty


def test_reason_divergence_low_overlap():
    d = make_decision("d-001", reason="authentication login session user credentials")
    delta = accumulate_divergence(d, [], "database migration schema columns table index")
    assert delta >= 1.0  # keyword overlap < 0.15 → +1.0


def test_no_divergence_empty_reason():
    d = make_decision("d-001", reason="")
    delta = accumulate_divergence(d, [], "some new reason")
    # overlap=1.0 when current reason is empty — no divergence
    assert delta == 0.0


# ─── accumulate_convergence ───────────────────────────────────────────────────

def test_convergence_pair_created_for_co_modified():
    d1 = make_decision("d-001", scope="src/", reason="auth system design")
    d2 = make_decision("d-002", scope="src/", reason="auth token validation")
    data = make_data(d1, d2, scores={})
    ops = [
        {"op": "update", "id": "d-001"},
        {"op": "update", "id": "d-002"},
    ]
    result = accumulate_convergence(data, ops)
    scores = result["convergence_scores"]
    assert "d-001:d-002" in scores
    assert scores["d-001:d-002"] > 0.0


def test_convergence_single_update_no_pair():
    d1 = make_decision("d-001")
    data = make_data(d1, scores={})
    ops = [{"op": "update", "id": "d-001"}]
    result = accumulate_convergence(data, ops)
    assert result["convergence_scores"] == {}


def test_convergence_scores_accumulate_across_calls():
    """D1 버그 수정 후 accumulate_convergence가 기존 scores 위에 누적하는지 확인."""
    d1 = make_decision("d-001", scope="src/", reason="logging framework choice")
    d2 = make_decision("d-002", scope="src/", reason="logging output format")
    initial_scores = {"d-001:d-002": 1.0}
    data = make_data(d1, d2, scores=initial_scores)
    ops = [{"op": "update", "id": "d-001"}, {"op": "update", "id": "d-002"}]
    result = accumulate_convergence(data, ops)
    # Score should be higher than initial 1.0
    assert result["convergence_scores"]["d-001:d-002"] > 1.0


# ─── extract_json ─────────────────────────────────────────────────────────────

def test_extract_json_from_json_code_block():
    text = '```json\n{"operations": [{"op": "add"}]}\n```'
    result = extract_json(text)
    assert result is not None
    assert result["operations"][0]["op"] == "add"


def test_extract_json_from_bare_code_block():
    text = '```\n{"operations": [{"op": "prune", "id": "d-001"}]}\n```'
    result = extract_json(text)
    assert result is not None
    assert result["operations"][0]["op"] == "prune"


def test_extract_json_greedy_brace_fallback():
    text = 'Here is the result: {"operations": [{"op": "update", "id": "d-002"}]}'
    result = extract_json(text)
    assert result is not None
    assert result["operations"][0]["id"] == "d-002"


def test_extract_json_returns_none_on_no_json():
    text = "No JSON here. Just plain text with no operations."
    result = extract_json(text)
    assert result is None


def test_extract_json_invalid_json_in_block():
    text = "```json\n{broken json here\n```"
    result = extract_json(text)
    assert result is None


# ─── should_include_file / matches_any ───────────────────────────────────────

def test_global_exclude_lock_file():
    ok, reason = should_include_file("package-lock.json", {})
    assert not ok
    assert reason == "global_exclude"


def test_global_exclude_image():
    ok, reason = should_include_file("assets/logo.png", {})
    assert not ok


def test_include_pattern_matches():
    filters = {"include": ["src/**"], "exclude": []}
    ok, _ = should_include_file("src/api/routes.py", filters)
    assert ok


def test_exclude_overrides_include():
    filters = {"include": ["src/**"], "exclude": ["**/*.test.*"]}
    ok, reason = should_include_file("src/api/routes.test.ts", filters)
    assert not ok
    assert reason == "target_exclude"


def test_no_include_filter_allows_all():
    filters = {"include": [], "exclude": []}
    ok, reason = should_include_file("some/random/file.py", filters)
    assert ok


def test_double_star_glob_matches_nested():
    assert matches_any("src/deep/nested/file.py", ["src/**"])


def test_extension_glob():
    assert matches_any("main.go", ["*.go"])


def test_non_matching_pattern():
    assert not matches_any("src/main.py", ["*.go"])


# ─── truncate_diff ────────────────────────────────────────────────────────────

def test_truncate_diff_no_truncation_needed():
    diff = "diff --git a/a.py b/a.py\n+ content\n"
    result = truncate_diff(diff, 10000)
    assert result == diff


def test_truncate_diff_applies_per_file_budget():
    file_a = "diff --git a/a.py b/a.py\n" + "A" * 500
    file_b = "diff --git a/b.py b/b.py\n" + "B" * 500
    diff = file_a + "\n" + file_b
    result = truncate_diff(diff, 400)
    assert len(result) <= 400 + 50  # allow small overhead for truncation markers


def test_truncate_diff_no_files_truncates_raw():
    diff = "plain text " * 200
    result = truncate_diff(diff, 50)
    assert "[truncated]" in result
    assert len(result) <= 50 + len("\n... [truncated]")


# ─── get_canonical_summary ────────────────────────────────────────────────────

def test_canonical_summary_excludes_superseded():
    d_active = make_decision("d-001", status="active", reason="Active decision reason.")
    d_super = make_decision("d-002", status="superseded", reason="Old.")
    data = make_data(d_active, d_super)
    summary = get_canonical_summary(data)
    ids = [e["id"] for e in summary]
    assert "d-001" in ids
    assert "d-002" not in ids


def test_canonical_summary_truncates_reason_at_sentence():
    reason = "First sentence here. Second sentence continues."
    d = make_decision("d-001", reason=reason)
    data = make_data(d)
    summary = get_canonical_summary(data)
    assert summary[0]["summary"] == "First sentence here."


def test_canonical_summary_includes_extensions_count():
    d = make_decision("d-001")
    d["extensions"] = [
        {"documentDate": "2026-02-01", "evidence": "Additional evidence found.", "related_files": []},
        {"documentDate": "2026-03-01", "evidence": "More evidence seen.", "related_files": []},
    ]
    data = make_data(d)
    summary = get_canonical_summary(data)
    assert summary[0]["extensions_count"] == 2


# ─── accumulate_staleness: S1 signal ─────────────────────────────────────────

FAKE_REPO = "/nonexistent/repo"  # git calls fail gracefully → S2/S4 skipped

def test_s1_derive_source_reaches_threshold_immediately():
    """derive 이벤트 1회로 S1 boost가 staleness threshold에 즉시 도달해야 함."""
    src = make_decision("d-001")
    data = make_data(src, scores={})
    ops = [{"op": "derive", "source_ids": ["d-001"], "scope": "architecture",
            "title": "Higher-order principle", "reason": "Synthesized."}]
    result = accumulate_staleness(data, ops, "abc123", FAKE_REPO, 10)
    d001 = next(d for d in result["decisions"] if d["id"] == "d-001")
    assert d001["staleness_score"] >= git_adr.DEFAULT_STALENESS_THRESHOLD


def test_s1_split_source_reaches_threshold_immediately():
    """split 이벤트 1회로 S1 boost가 staleness threshold에 즉시 도달해야 함."""
    src = make_decision("d-001")
    data = make_data(src, scores={})
    ops = [{"op": "split", "source_id": "d-001", "into": []}]
    result = accumulate_staleness(data, ops, "abc123", FAKE_REPO, 10)
    d001 = next(d for d in result["decisions"] if d["id"] == "d-001")
    assert d001["staleness_score"] >= git_adr.DEFAULT_STALENESS_THRESHOLD


def test_s1_does_not_affect_non_source_decisions():
    """S1은 derive/split의 소스가 아닌 decisions에는 영향 없어야 함."""
    src = make_decision("d-001")
    bystander = make_decision("d-002", staleness_score=0.5)
    data = make_data(src, bystander, scores={})
    ops = [{"op": "derive", "source_ids": ["d-001"], "scope": "architecture",
            "title": "Higher-order principle", "reason": "Synthesized."}]
    result = accumulate_staleness(data, ops, "abc123", FAKE_REPO, 10)
    d002 = next(d for d in result["decisions"] if d["id"] == "d-002")
    assert d002["staleness_score"] == 0.5


def test_s1_skips_superseded_source():
    """이미 superseded된 소스 decision에는 S1 boost를 적용하지 않아야 함."""
    src = make_decision("d-001", status="superseded", staleness_score=0.0)
    data = make_data(src, scores={})
    ops = [{"op": "derive", "source_ids": ["d-001"], "scope": "architecture",
            "title": "New principle", "reason": "Derived."}]
    result = accumulate_staleness(data, ops, "abc123", FAKE_REPO, 10)
    d001 = next(d for d in result["decisions"] if d["id"] == "d-001")
    assert d001["staleness_score"] == 0.0
