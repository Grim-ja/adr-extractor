"""Tests for --export-claude-md feature: CLAUDE.md upsert logic."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

GIT_ADR = Path(__file__).parent / "git-adr.py"


def make_decisions(active_count=2, superseded_count=1, base_date="2026-05-"):
    decisions = []
    for i in range(1, active_count + 1):
        decisions.append({
            "id": f"d-{i:03d}",
            "status": "active",
            "documentDate": f"{base_date}{i:02d}",
            "title": f"Decision {i}",
            "scope": f"src/module{i}",
            "reason": f"Reason for decision {i}. This is a second sentence that should be excluded.",
            "extensions": [],
        })
    for j in range(1, superseded_count + 1):
        decisions.append({
            "id": f"d-s{j:03d}",
            "status": "superseded",
            "documentDate": f"{base_date}20",
            "title": f"Superseded {j}",
            "scope": "src/old",
            "reason": "Old reason.",
            "extensions": [],
        })
    return {"decisions": decisions}


def run_export(output_dir: Path, repo_dir: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(GIT_ADR), "--export-claude-md",
         "--output", str(output_dir), "--repo", str(repo_dir)],
        capture_output=True, text=True,
    )


@pytest.fixture
def output_dir(tmp_path):
    d = tmp_path / "output"
    d.mkdir()
    (d / "decisions.json").write_text(
        json.dumps(make_decisions(), ensure_ascii=False)
    )
    return d


@pytest.fixture
def repo_dir(tmp_path):
    return tmp_path / "repo"


# ─── T6-1: 신규 파일 생성 ───────────────────────────────────────────────────

def test_new_file_created(output_dir, repo_dir):
    repo_dir.mkdir()
    result = run_export(output_dir, repo_dir)

    assert result.returncode == 0
    claude_md = repo_dir / "CLAUDE.md"
    assert claude_md.exists()
    content = claude_md.read_text()
    assert "## Architecture Decisions" in content
    assert "<!-- adr:start -->" in content
    assert "<!-- adr:end -->" in content
    assert "d-001" in content
    assert "d-002" in content
    assert "d-s001" not in content  # superseded 제외


# ─── T6-2: idempotent ────────────────────────────────────────────────────────

def test_idempotent(output_dir, repo_dir):
    repo_dir.mkdir()
    run_export(output_dir, repo_dir)
    first = (repo_dir / "CLAUDE.md").read_text()

    run_export(output_dir, repo_dir)
    second = (repo_dir / "CLAUDE.md").read_text()

    assert first == second
    assert first.count("<!-- adr:start -->") == 1
    assert first.count("<!-- adr:end -->") == 1


# ─── T6-3: 기존 마커 사이 내용 교체 ──────────────────────────────────────────

def test_markers_present_replaced(output_dir, repo_dir):
    repo_dir.mkdir()
    existing = (
        "# My Project\n\n"
        "## Architecture Decisions\n"
        "<!-- adr:start -->\n"
        "old content\n"
        "<!-- adr:end -->\n\n"
        "## Other Section\n"
        "Keep this.\n"
    )
    (repo_dir / "CLAUDE.md").write_text(existing)

    run_export(output_dir, repo_dir)
    content = (repo_dir / "CLAUDE.md").read_text()

    assert "old content" not in content
    assert "d-001" in content
    assert "Keep this." in content  # 기존 사용자 섹션 보존
    assert content.count("<!-- adr:start -->") == 1
    assert content.count("<!-- adr:end -->") == 1


# ─── T6-4: 헤더 있음, 마커 없음 ──────────────────────────────────────────────

def test_header_no_markers_wrapped(output_dir, repo_dir):
    repo_dir.mkdir()
    existing = (
        "# My Project\n\n"
        "## Architecture Decisions\n"
        "Some old manual content here.\n\n"
        "## Usage\n"
        "Keep this section.\n"
    )
    (repo_dir / "CLAUDE.md").write_text(existing)

    run_export(output_dir, repo_dir)
    content = (repo_dir / "CLAUDE.md").read_text()

    assert "Some old manual content here." not in content
    assert "<!-- adr:start -->" in content
    assert "d-001" in content
    assert "Keep this section." in content
    assert content.count("## Architecture Decisions") == 1


# ─── T6-5: 헤더도 마커도 없음 → 파일 끝에 추가 ──────────────────────────────

def test_no_header_appended(output_dir, repo_dir):
    repo_dir.mkdir()
    existing = "# My Project\n\nExisting content.\n"
    (repo_dir / "CLAUDE.md").write_text(existing)

    run_export(output_dir, repo_dir)
    content = (repo_dir / "CLAUDE.md").read_text()

    assert content.startswith("# My Project")
    assert "Existing content." in content
    assert "## Architecture Decisions" in content
    assert "<!-- adr:start -->" in content


# ─── T6-6: decisions.json 없음 → 오류 ──────────────────────────────────────

def test_missing_decisions_json_exits(tmp_path, repo_dir):
    empty_output = tmp_path / "empty_output"
    empty_output.mkdir()
    repo_dir.mkdir()

    result = run_export(empty_output, repo_dir)

    assert result.returncode == 1
    assert "decisions.json" in result.stderr


# ─── T6-7: active 0개 → 플레이스홀더 ──────────────────────────────────────

def test_zero_active_decisions(tmp_path, repo_dir):
    repo_dir.mkdir()
    output_dir = tmp_path / "out"
    output_dir.mkdir()
    (output_dir / "decisions.json").write_text(
        json.dumps({"decisions": [
            {"id": "d-001", "status": "superseded", "documentDate": "2026-01-01",
             "title": "Old", "scope": "src/", "reason": "Reason.", "extensions": []}
        ]})
    )

    result = run_export(output_dir, repo_dir)
    assert result.returncode == 0
    content = (repo_dir / "CLAUDE.md").read_text()
    assert "No active decisions yet." in content


# ─── T6-8: 8KB 절삭 및 우선순위 정렬 ────────────────────────────────────────

def test_8kb_truncation_priority(tmp_path, repo_dir):
    repo_dir.mkdir()
    output_dir = tmp_path / "out"
    output_dir.mkdir()

    # 200개 결정 생성 — 각각 긴 summary로 8KB 초과를 유발
    decisions = []
    for i in range(200):
        decisions.append({
            "id": f"d-{i:03d}",
            "status": "active",
            "documentDate": f"2026-{(i % 12) + 1:02d}-{(i % 28) + 1:02d}",
            "title": f"Decision {i} — " + "x" * 80,
            "scope": "src/",
            "reason": "A" * 300 + ". Next sentence.",
            "extensions": [],
        })
    (output_dir / "decisions.json").write_text(json.dumps({"decisions": decisions}))

    result = run_export(output_dir, repo_dir)
    assert result.returncode == 0

    content = (repo_dir / "CLAUDE.md").read_text()
    assert "<!-- adr:start -->" in content
    assert len(content.encode("utf-8")) <= 8 * 1024 + 200  # 헤더/마커 오버헤드 허용

    # 가장 최신 날짜(2026-12-28)의 결정이 우선 포함되어야 함
    # get_canonical_summary()는 documentDate를 출력하지 않으므로 id로 확인
    assert "d-167" in content  # 2026-12-28, 해당 날짜 최대 id
    assert "d-083" in content  # 2026-12-28, 해당 날짜 두 번째 id
