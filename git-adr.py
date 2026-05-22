#!/usr/bin/env python3
"""
git-adr.py — git 히스토리를 순회하며 ADR(Architecture Decision Records)을 누적 생성

Usage:
  python git-adr.py --repo /path/to/repo --target implementation --output ./adr-output/

  타겟 종류:
    implementation : 백엔드/프론트엔드/아키텍처 통합 구현 결정
    design         : UI/UX 결정 (디자인 시스템, 인터랙션, 접근성 등)
    planning       : 기획/제품 결정 (도메인 모델, 비즈니스 규칙, 권한 등)
"""

import argparse
import fnmatch
import json
import os
import re
import subprocess
import sys
import textwrap
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False

# ─────────────────────────────────────────────
# 상수
# ─────────────────────────────────────────────

PROMPT_DIR = Path(__file__).parent / "prompts"
STATE_FILENAME = ".adr-state.json"
DECISIONS_FILENAME = "decisions.json"
FILTERS_FILENAME = ".adr-filters.yaml"
DEFAULT_MAX_DIFF = 12000
DEFAULT_CONTEXT_LINES = 5
DEFAULT_DRIFT_THRESHOLD = 2.0
DEFAULT_DERIVE_THRESHOLD = 2.5
DEFAULT_STALENESS_THRESHOLD = 3.0
DEFAULT_STALENESS_COOLDOWN = 20  # keep 후 scan 제외 커밋 수

CLAUDE_MD_FILENAME = "CLAUDE.md"
ADR_START_MARKER = "<!-- adr:start -->"
ADR_END_MARKER = "<!-- adr:end -->"
ADR_SECTION_HEADER = "## Architecture Decisions"
ADR_MAX_BYTES = 8 * 1024

# 전역 제외 목록
GLOBAL_EXCLUDE = [
    "*.lock", "*.sum",
    "package-lock.json", "yarn.lock", "pnpm-lock.yaml",
    "Cargo.lock", "Gemfile.lock", "poetry.lock",
    "*.zip", "*.tar", "*.tar.gz", "*.tgz", "*.gz", "*.bz2", "*.xz",
    "*.7z", "*.rar", "*.jar", "*.war", "*.ear",
    "*.png", "*.jpg", "*.jpeg", "*.gif", "*.webp", "*.avif",
    "*.ico", "*.bmp", "*.tiff",
    "*.woff", "*.woff2", "*.ttf", "*.otf", "*.eot",
    "*.pdf", "*.doc", "*.docx", "*.xls", "*.xlsx",
    "*.mp3", "*.mp4", "*.wav", "*.mov", "*.avi",
    "*.pyc", "*.pyo", "*.class", "*.o", "*.so", "*.dll", "*.exe",
    "*.map",
    "*.snap",
    "*.min.js", "*.min.css",
    # AI 에이전트 지시/설정 파일 — 범용 툴 설정, 결정 기록 아님
    "CLAUDE.md", "AGENTS.md",
    ".cursorrules", "COPILOT-INSTRUCTIONS.md", ".github/copilot-instructions.md",
    # 텍스트 상태/메모 파일
    "*.txt",
    # 경로 기반 제외
    ".git/*",
    "node_modules/*",
    "__pycache__/*",
    "dist/*", "build/*", ".next/*", ".nuxt/*",
    "coverage/*", ".cache/*",
    "vendor/*", ".venv/*", "venv/*", "env/*",
]

DEFAULT_TARGET_FILTERS: dict[str, dict] = {
    "implementation": {
        "include": [
            "src/**", "app/**", "lib/**", "pkg/**",
            "server/**", "backend/**", "frontend/**", "web/**",
            "api/**", "services/**", "handlers/**", "controllers/**",
            "*.go", "*.rs", "*.java", "*.kt", "*.py",
            "*.ts", "*.tsx", "*.js", "*.jsx",
            "Dockerfile", "docker-compose*.yml", "docker-compose*.yaml",
            ".github/**", "*.ci.yml", "*.ci.yaml",
            "*.config.ts", "*.config.js", "*.config.mjs",
            "tsconfig*.json", "*.toml", "*.env.example",
            "prisma/**", "migrations/**", "schema.*",
            "docs/**", "*.md",
        ],
        "exclude": [
            "**/*.test.*", "**/*.spec.*", "**/__tests__/**",
            "**/*.stories.*",
            "**/styles/**", "**/tokens/**", "**/themes/**",
            "**/*.css", "**/*.scss", "**/*.sass", "**/*.less",
            "**/*.sh",
            "CHANGELOG.md",
            "TODOS.md",
        ],
    },
    "design": {
        "include": [
            "**/components/**", "**/ui/**",
            "**/styles/**", "**/tokens/**", "**/themes/**",
            "**/design-system/**", "**/design_system/**",
            "**/*.css", "**/*.scss", "**/*.sass", "**/*.less",
            "**/*.stories.*",
            "**/animations/**", "**/motion/**",
            "tailwind.config.*", "postcss.config.*",
            "**/figma/**",
        ],
        "exclude": [
            "**/*.test.*", "**/*.spec.*",
        ],
    },
    "planning": {
        "include": [
            "prisma/**", "**/schema/**", "**/migrations/**",
            "**/domain/**", "**/entities/**", "**/models/**",
            "**/policies/**", "**/permissions/**", "**/roles/**",
            "**/workflows/**", "**/rules/**",
            "docs/**", "spec/**", "specs/**", "*.md",
            "**/constants/**", "**/config/**",
            "**/enums/**", "**/types/**",
            "**/features/**", "**/flags/**",
        ],
        "exclude": [
            "**/*.test.*", "**/*.spec.*",
            "**/*.css", "**/*.scss",
        ],
    },
}


# ─────────────────────────────────────────────
# 패턴 매칭
# ─────────────────────────────────────────────

def matches_any(fpath: str, patterns: list[str]) -> bool:
    for pat in patterns:
        if fnmatch.fnmatch(fpath, pat):
            return True
        if fnmatch.fnmatch(fpath, pat.lstrip("*/")):
            return True
        regex = _glob_to_regex(pat)
        if re.match(regex, fpath):
            return True
    return False


def _glob_to_regex(pat: str) -> str:
    pat = pat.replace(".", r"\.")
    pat = pat.replace("**", "\x00")
    pat = pat.replace("*", "[^/]*")
    pat = pat.replace("\x00", ".*")
    pat = pat.replace("?", "[^/]")
    return f"^{pat}$"


def should_include_file(fpath: str, filters: dict) -> tuple[bool, str]:
    if matches_any(fpath, GLOBAL_EXCLUDE):
        return False, "global_exclude"

    include_pats = filters.get("include", [])
    exclude_pats = filters.get("exclude", [])

    if not include_pats:
        if exclude_pats and matches_any(fpath, exclude_pats):
            return False, "target_exclude"
        return True, "no_include_filter"

    if not matches_any(fpath, include_pats):
        return False, "not_in_include"

    if exclude_pats and matches_any(fpath, exclude_pats):
        return False, "target_exclude"

    return True, "matched"


# ─────────────────────────────────────────────
# 필터 관리
# ─────────────────────────────────────────────

def load_filters(repo: str, target: str, filters_file: Optional[str] = None) -> dict:
    if filters_file:
        path = Path(filters_file)
        if path.exists():
            return _parse_filters_yaml(path, target)
        else:
            print(f"  [경고] --filters-file '{filters_file}' 없음, 기본값 사용", file=sys.stderr)

    repo_filters = Path(repo) / FILTERS_FILENAME
    if repo_filters.exists():
        parsed = _parse_filters_yaml(repo_filters, target)
        if parsed:
            print(f"  [filters] {repo_filters} 로드")
            return parsed

    return DEFAULT_TARGET_FILTERS.get(target, {})


def _parse_filters_yaml(path: Path, target: str) -> dict:
    if not HAS_YAML:
        print("  [경고] PyYAML 미설치. pip install pyyaml 후 yaml 필터 사용 가능.", file=sys.stderr)
        return {}
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not data or not isinstance(data, dict):
        return {}
    return data.get(target, {})


def save_filters_yaml(repo: str, filters: dict) -> Path:
    path = Path(repo) / FILTERS_FILENAME
    if HAS_YAML:
        with open(path, "w", encoding="utf-8") as f:
            yaml.dump(filters, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
    else:
        lines = []
        for tgt, cfg in filters.items():
            lines.append(f"{tgt}:")
            for key in ("include", "exclude"):
                if cfg.get(key):
                    lines.append(f"  {key}:")
                    for pat in cfg[key]:
                        lines.append(f"    - \"{pat}\"")
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


# ─────────────────────────────────────────────
# 레포 구조 스캔 + LLM 필터 생성
# ─────────────────────────────────────────────

def scan_repo_structure(repo: str, max_files: int = 300) -> str:
    raw = git(repo, "ls-files")
    all_files = [f for f in raw.splitlines() if f.strip()]
    filtered = [f for f in all_files if not matches_any(f, GLOBAL_EXCLUDE)]

    sample = filtered[:max_files]
    truncated = len(filtered) > max_files

    dirs: dict[str, int] = {}
    for f in filtered:
        parts = f.split("/")
        if len(parts) > 1:
            top = parts[0]
            dirs[top] = dirs.get(top, 0) + 1

    dir_summary = "\n".join(
        f"  {d}/  ({count}개 파일)" for d, count in sorted(dirs.items(), key=lambda x: -x[1])
    )

    file_list = "\n".join(sample)
    suffix = f"\n... 외 {len(filtered) - max_files}개" if truncated else ""

    return f"""# 레포지터리 구조

## 최상위 디렉터리
{dir_summary}

## 파일 목록 (최대 {max_files}개)
{file_list}{suffix}
"""


def build_filter_scan_prompt(repo_structure: str) -> str:
    return f"""당신은 소프트웨어 레포지터리 구조 분석 전문가입니다.
아래 레포지터리의 파일 구조를 보고, ADR(Architecture Decision Record) 생성을 위한
파일 필터 패턴을 정의해주세요.

{repo_structure}

# 지시사항

세 가지 ADR 타겟에 대해 각각 include/exclude 패턴을 정의하세요:

- **implementation**: 백엔드/프론트엔드/아키텍처 구현 결정 관련 파일
- **design**: UI/UX, 디자인 시스템, 스타일 관련 파일
- **planning**: 도메인 모델, 비즈니스 규칙, 기획 문서 관련 파일

## 패턴 작성 규칙
- glob 패턴 사용 (`**` = 임의 경로, `*` = 임의 파일명)
- include: 이 타겟에서 분석해야 할 파일
- exclude: include에 해당하더라도 제외할 파일
- 이 레포에 실제로 존재하는 경로에 맞게 작성할 것
- 바이너리/압축 파일과 아래 파일들은 이미 전역 제외되므로 작성 불필요:
  - AI 에이전트 지시 파일: CLAUDE.md, AGENTS.md, .cursorrules
  - 텍스트 상태 파일: *.txt
  - 패키지 락 파일, 바이너리, 이미지, 폰트 등
- 이 프로젝트에서만 쓰이는 워크플로우 파일(예: FEEDBACK.md, PROMPT.md, ralph.sh 등)은
  각 타겟의 exclude에 직접 명시할 것

## 타겟별 포함/제외 원칙

- **implementation**:
  - 포함: 소스코드, 설정 파일, 개발 문서(docs/, *.md) — 기술 결정이 담길 수 있음
  - 제외: 셸 스크립트(*.sh) — 스크립팅/운영 목적, 구현 결정 아님
  - 제외: 테스트 파일, 스타일 파일, CHANGELOG.md, TODOS.md

- **design**:
  - 포함: 컴포넌트, 스타일, 디자인 시스템, UI 관련 문서
  - 제외: 테스트 파일

- **planning**:
  - 포함: 도메인 모델, 비즈니스 규칙, 기획 문서, 스키마
  - 제외: 테스트 파일, 스타일 파일

## 출력 형식

반드시 아래 YAML을 ```yaml ... ``` 코드블록으로 반환하세요.

```yaml
implementation:
  include:
    - "src/**"
    - "app/**"
  exclude:
    - "**/*.test.*"
    - "**/*.spec.*"

design:
  include:
    - "**/components/**"
    - "**/*.css"
  exclude:
    - "**/*.test.*"

planning:
  include:
    - "prisma/**"
    - "docs/**"
  exclude:
    - "**/*.test.*"
```
"""


def generate_filters_with_llm(repo: str, llm_caller) -> Optional[dict]:
    print("  레포 구조 스캔 중...")
    structure = scan_repo_structure(repo)

    print("  LLM으로 필터 패턴 생성 중...")
    prompt = build_filter_scan_prompt(structure)

    try:
        response = llm_caller(prompt)
    except Exception as e:
        print(f"  [경고] 필터 생성 LLM 호출 실패: {e}", file=sys.stderr)
        return None

    m = re.search(r'```yaml\s*([\s\S]*?)```', response)
    if not m:
        m = re.search(r'```\s*([\s\S]*?)```', response)
    if not m:
        print("  [경고] LLM 응답에서 YAML 블록을 찾을 수 없음", file=sys.stderr)
        return None

    yaml_text = m.group(1)

    if HAS_YAML:
        try:
            data = yaml.safe_load(yaml_text)
            if isinstance(data, dict):
                return data
        except Exception as e:
            print(f"  [경고] YAML 파싱 실패: {e}", file=sys.stderr)
            return None
    else:
        print("  [경고] PyYAML 미설치. 기본 필터 사용. pip install pyyaml 권장.", file=sys.stderr)
        return None

    return None


# ─────────────────────────────────────────────
# diff 필터링
# ─────────────────────────────────────────────

def apply_target_filter(diff: str, filters: dict, verbose: bool = False) -> tuple[str, bool]:
    file_sections = re.split(r'(?=^diff --git )', diff, flags=re.MULTILINE)
    file_sections = [s for s in file_sections if s.strip()]

    included = []
    excluded_count = 0

    for section in file_sections:
        m = re.search(r'^diff --git a/.+ b/(.+)$', section, re.MULTILINE)
        if not m:
            included.append(section)
            continue

        fpath = m.group(1)
        ok, reason = should_include_file(fpath, filters)

        if ok:
            included.append(section)
            if verbose:
                print(f"    include: {fpath}")
        else:
            excluded_count += 1
            if verbose:
                print(f"    exclude ({reason}): {fpath}")

    if not included and excluded_count > 0:
        print(
            f"  [fallback] 타겟 필터가 모든 파일을 제외함 ({excluded_count}개). "
            "전체 diff로 fallback.",
            file=sys.stderr,
        )
        return diff, True

    return "".join(included), False


# ─────────────────────────────────────────────
# git 유틸
# ─────────────────────────────────────────────

def git(repo: str, *args: str, check=True) -> str:
    result = subprocess.run(
        ["git", "-C", repo] + list(args),
        capture_output=True,
        text=True,
        check=check,
    )
    return result.stdout.strip()


def get_commits(repo: str, from_hash: Optional[str] = None) -> list[dict]:
    fmt = "%H\x1f%s\x1f%ai\x1f%an"
    raw = git(repo, "log", "--reverse", f"--format={fmt}")
    commits = []
    for line in raw.splitlines():
        if not line.strip():
            continue
        parts = line.split("\x1f")
        if len(parts) < 4:
            continue
        commits.append({
            "hash": parts[0],
            "subject": parts[1],
            "date": parts[2],
            "author": parts[3],
        })

    if from_hash:
        for i, c in enumerate(commits):
            if c["hash"] == from_hash:
                return commits[i + 1:]
    return commits


def get_diff(repo: str, commit_hash: str, context_lines: int = DEFAULT_CONTEXT_LINES) -> str:
    parent_check = git(repo, "rev-parse", "--verify", f"{commit_hash}^", check=False)
    if not parent_check:
        empty_tree = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"
        raw_diff = git(repo, "diff", f"--unified={context_lines}", empty_tree, commit_hash)
    else:
        raw_diff = git(repo, "diff", f"--unified={context_lines}", f"{commit_hash}^", commit_hash)

    return _apply_global_exclude(raw_diff)


def _apply_global_exclude(diff: str) -> str:
    lines = diff.splitlines(keepends=True)
    result = []
    skip = False

    for line in lines:
        if line.startswith("diff --git "):
            m = re.search(r' b/(.+)$', line)
            fpath = m.group(1) if m else ""
            skip = matches_any(fpath, GLOBAL_EXCLUDE)

        if not skip:
            result.append(line)

    return "".join(result)


def truncate_diff(diff: str, max_chars: int) -> str:
    if len(diff) <= max_chars:
        return diff

    file_sections = re.split(r'(?=^diff --git )', diff, flags=re.MULTILINE)
    file_sections = [s for s in file_sections if s.strip()]

    if not file_sections:
        return diff[:max_chars] + "\n... [truncated]"

    budget_per_file = max_chars // len(file_sections)
    result_parts = []
    for section in file_sections:
        if len(section) > budget_per_file:
            result_parts.append(section[:budget_per_file] + "\n... [truncated]\n")
        else:
            result_parts.append(section)

    result = "".join(result_parts)
    if len(result) > max_chars:
        result = result[:max_chars] + "\n... [truncated]"
    return result


# ─────────────────────────────────────────────
# Divergence score
# ─────────────────────────────────────────────

def _top_level_seams(files: list[str]) -> set[str]:
    """파일 경로 목록에서 top-level 디렉터리(seam) 추출."""
    seams = set()
    for f in files:
        parts = f.split("/")
        seams.add(parts[0] if len(parts) > 1 else "__root__")
    return seams


def _keyword_overlap(text_a: str, text_b: str) -> float:
    """두 텍스트의 의미 있는 단어 overlap 비율 (0~1). 높을수록 유사."""
    if not text_a or not text_b:
        return 1.0  # 비교 불가 → divergence 없음으로 처리

    stopwords = {
        '이', '가', '을', '를', '의', '에', '서', '과', '와', '은', '는', '도', '로', '하',
        'the', 'a', 'an', 'is', 'are', 'was', 'were', 'to', 'of', 'in', 'for', 'on',
        'with', 'at', 'by', 'from', 'as', 'and', 'or', 'but', 'not', 'this', 'that',
        'it', 'its', 'be', 'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did',
    }

    words_a = set(re.findall(r'[가-힣a-zA-Z]{2,}', text_a.lower())) - stopwords
    words_b = set(re.findall(r'[가-힣a-zA-Z]{2,}', text_b.lower())) - stopwords

    if not words_a or not words_b:
        return 1.0

    return len(words_a & words_b) / len(words_a | words_b)


def accumulate_divergence(decision: dict, new_related_files: list[str], new_reason: str) -> float:
    """
    update 발생 시 divergence score increment를 deterministic하게 계산.

    두 가지 신호:
    1. Seam divergence: 새 related_files가 기존과 다른 top-level 경로를 포함
    2. Reason divergence: 새 reason과 기존 reason의 키워드 overlap이 낮음
    """
    delta = 0.0

    # 1. Seam divergence
    current_seams = _top_level_seams(decision.get("related_files", []))
    new_seams = _top_level_seams(new_related_files) if new_related_files else set()
    if current_seams and new_seams:
        novel_seams = new_seams - current_seams
        delta += len(novel_seams) * 0.8

    # 2. Reason divergence
    current_reason = decision.get("reason", "")
    if current_reason and new_reason:
        overlap = _keyword_overlap(current_reason, new_reason)
        if overlap < 0.15:
            delta += 1.0
        elif overlap < 0.30:
            delta += 0.5

    return delta


# ─────────────────────────────────────────────
# Convergence score (derive 트리거)
# ─────────────────────────────────────────────

def _pair_key(id_a: str, id_b: str) -> str:
    """항상 오름차순으로 정렬한 pair key."""
    a, b = sorted([id_a, id_b])
    return f"{a}:{b}"


def _shared_scope_prefix(scope_a: str, scope_b: str) -> bool:
    """두 scope가 같은 top-level prefix를 공유하는지."""
    top_a = scope_a.split("/")[0] if scope_a else ""
    top_b = scope_b.split("/")[0] if scope_b else ""
    return bool(top_a and top_b and top_a == top_b)


def accumulate_convergence(decisions_data: dict, operations: list) -> dict:
    """
    현재 커밋 operations에서 동시에 update/extend된 decision pair들을 추출하고
    convergence_score를 누적.

    세 가지 신호:
    1. 같은 커밋에서 함께 update/extend — 공통 관심사 신호
    2. scope prefix 공유 — 구조적 인접성
    3. reason keyword overlap — 의미적 유사성
    """
    scores = decisions_data.get("convergence_scores", {})
    arr = decisions_data.get("decisions", [])
    id_map = {d["id"]: d for d in arr if d.get("status") == "active"}

    # 이번 커밋에서 update/extend된 decision ids
    touched_ids = [
        op.get("id") for op in operations
        if op.get("op") in ("update", "extend") and op.get("id") in id_map
    ]

    if len(touched_ids) < 2:
        return decisions_data

    # 같은 커밋에서 함께 건드려진 pair들
    from itertools import combinations
    for id_a, id_b in combinations(touched_ids, 2):
        key = _pair_key(id_a, id_b)
        delta = 0.0

        d_a = id_map[id_a]
        d_b = id_map[id_b]

        # 신호 1: 같은 커밋에서 함께 update/extend
        delta += 1.0

        # 신호 2: scope prefix 공유
        if _shared_scope_prefix(d_a.get("scope", ""), d_b.get("scope", "")):
            delta += 0.8

        # 신호 3: reason keyword overlap
        overlap = _keyword_overlap(d_a.get("reason", ""), d_b.get("reason", ""))
        if overlap > 0.30:
            delta += 1.0
        elif overlap > 0.15:
            delta += 0.5

        scores[key] = round(scores.get(key, 0.0) + delta, 3)

    decisions_data["convergence_scores"] = scores
    return decisions_data




def load_decisions(output_dir: Path) -> dict:
    path = output_dir / DECISIONS_FILENAME
    if path.exists():
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        if "convergence_scores" not in data:
            data["convergence_scores"] = {}
        # staleness 필드 초기화 (기존 decisions 호환)
        for d in data.get("decisions", []):
            d.setdefault("staleness_score", 0.0)
            d.setdefault("last_active_commit", "")
            d.setdefault("last_active_date", d.get("documentDate", ""))
            d.setdefault("last_reviewed_commit", None)
            d.setdefault("last_reviewed_processed_count", -1)
            d.setdefault("related_churn_count", 0)
        return data
    return {"decisions": [], "convergence_scores": {}}


def save_decisions(output_dir: Path, data: dict) -> None:
    path = output_dir / DECISIONS_FILENAME
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"  [saved] {path}")


def fmt_id(n: int) -> str:
    return f"d-{n:03d}"


def find_idx(arr: list, id_: str = "", scope: str = "", pat: str = "") -> int:
    if id_:
        for i, d in enumerate(arr):
            if d.get("id") == id_:
                return i
    elif scope and pat:
        for i, d in enumerate(arr):
            if d.get("scope") == scope and pat in d.get("title", ""):
                return i
    return -1


def _new_decision(counter: int, today: str, commit_date: str, op: dict, extra: Optional[dict] = None) -> dict:
    """새 decision 객체 생성 헬퍼."""
    d = {
        "id": fmt_id(counter),
        "status": "active",
        "documentDate": today,
        "commitDate": commit_date,
        "scope": op.get("scope", ""),
        "title": op.get("title", ""),
        "reason": op.get("reason", ""),
        "alternatives": op.get("alternatives", []),
        "consequences": op.get("consequences", []),
        "refs": op.get("refs", []),
        "related_files": op.get("related_files", []),
        "derived_from": None,
        "history": [],
        "divergence_score": 0.0,
        "staleness_score": 0.0,
        "last_active_commit": "",
        "last_active_date": today,
        "last_reviewed_commit": None,
        "last_reviewed_processed_count": -1,
        "related_churn_count": 0,  # last_active_commit 이후 related_files 변경 커밋 수
    }
    if extra:
        d.update(extra)
    return d


def apply_operations(decisions_data: dict, operations: list, today: str, commit_date: str = "") -> dict:
    arr = decisions_data.get("decisions", [])

    max_num = 0
    for d in arr:
        m = re.match(r'd-(\d+)', d.get("id", ""))
        if m:
            max_num = max(max_num, int(m.group(1)))
    counter = max_num + 1

    for op in operations:
        op_type = op.get("op", "")
        op_id = op.get("id", "")
        op_scope = op.get("scope", "")

        if op_type == "add":
            arr.append(_new_decision(counter, today, commit_date, op))
            counter += 1

        elif op_type == "update":
            idx = find_idx(arr, id_=op_id, scope=op_scope)
            if idx >= 0:
                d = arr[idx]
                new_related = op.get("related_files") or []
                new_reason = op.get("reason", "")

                # divergence score 누적
                delta = accumulate_divergence(d, new_related, new_reason)
                d["divergence_score"] = round(d.get("divergence_score", 0.0) + delta, 3)

                # history에 현재 상태 저장
                d["history"] = d.get("history", []) + [{
                    "documentDate": d.get("documentDate", d.get("date")),
                    "commitDate": d.get("commitDate", ""),
                    "title": d.get("title"),
                    "reason": d.get("reason"),
                    "related_files": d.get("related_files", []),
                    "action": "updated",
                }]
                d["documentDate"] = today
                d["commitDate"] = commit_date
                if new_reason:
                    d["reason"] = new_reason
                if op.get("refs") is not None:
                    d["refs"] = op["refs"]
                if new_related:
                    d["related_files"] = new_related
                if op.get("title"):
                    d["title"] = op["title"]
                if op.get("scope"):
                    d["scope"] = op["scope"]

        elif op_type == "extend":
            # 기존 reason은 보존, extensions 배열에 새 증거 추가
            idx = find_idx(arr, id_=op_id, scope=op_scope)
            if idx >= 0:
                d = arr[idx]
                new_related = op.get("related_files") or []
                new_evidence = op.get("evidence", "")

                # divergence score 누적 (extend도 동일 기준 적용)
                delta = accumulate_divergence(d, new_related, new_evidence)
                d["divergence_score"] = round(d.get("divergence_score", 0.0) + delta, 3)

                # extensions 배열에 추가 (reason은 변경 안 함)
                extension_entry = {
                    "documentDate": today,
                    "commitDate": commit_date,
                    "evidence": new_evidence,
                    "related_files": new_related,
                }
                d["extensions"] = d.get("extensions", []) + [extension_entry]
                d["documentDate"] = today
                d["commitDate"] = commit_date
                # related_files는 union
                existing = set(d.get("related_files", []))
                for f in new_related:
                    existing.add(f)
                d["related_files"] = list(existing)

        elif op_type == "prune":
            idx = find_idx(arr, id_=op_id, scope=op_scope)
            if idx >= 0:
                d = arr[idx]
                d["history"] = d.get("history", []) + [{
                    "documentDate": d.get("documentDate", d.get("date")),
                    "commitDate": d.get("commitDate", ""),
                    "title": d.get("title"),
                    "reason": d.get("reason"),
                    "action": "pruned",
                }]
                d["status"] = "superseded"
                d["documentDate"] = today
                d["commitDate"] = commit_date

        elif op_type == "derive":
            arr.append(_new_decision(counter, today, commit_date, op, {
                "derived_from": op.get("source_ids", []),
            }))
            counter += 1

        elif op_type == "split":
            src_id = op.get("source_id", "")
            parts = op.get("into", [])
            src_found = False
            for d in arr:
                if d.get("id") == src_id:
                    d["history"] = d.get("history", []) + [{
                        "documentDate": d.get("documentDate", d.get("date")),
                        "commitDate": d.get("commitDate", ""),
                        "title": d.get("title"),
                        "reason": d.get("reason"),
                        "action": "split",
                    }]
                    d["status"] = "superseded"
                    d["divergence_score"] = 0.0
                    src_found = True
                    break
            if not src_found and src_id:
                print(f"  [warn] split source_id '{src_id}' not found — parts added without superseding")
            for part in parts:
                arr.append(_new_decision(counter, today, commit_date, part, {
                    "split_from": src_id,
                }))
                counter += 1

    decisions_data["decisions"] = arr
    return decisions_data


# ─────────────────────────────────────────────
# Drift scan
# ─────────────────────────────────────────────

def build_drift_scan_prompt(candidates: list[dict], threshold: float) -> str:
    prompt_path = PROMPT_DIR / "drift-scan.md"
    if not prompt_path.exists():
        raise FileNotFoundError(f"drift-scan.md 없음: {prompt_path}")

    with open(prompt_path, encoding="utf-8") as f:
        template = f.read()

    candidates_json = json.dumps(candidates, ensure_ascii=False, indent=2)
    return template.replace("{{DRIFT_CANDIDATES}}", candidates_json).replace("{{THRESHOLD}}", str(threshold))


def run_drift_scan(
    decisions_data: dict,
    llm_caller,
    threshold: float,
    today: str,
) -> dict:
    """
    divergence_score >= threshold인 decisions를 LLM에 전달해 split 여부 판단.
    - split 발생: 기존 decision superseded, 새 decisions 생성, score 리셋
    - split 불필요: 해당 decisions의 score를 0.3배로 감소 (재검토 유예)
    """
    candidates = [
        d for d in decisions_data.get("decisions", [])
        if d.get("status") == "active" and d.get("divergence_score", 0.0) >= threshold
    ]

    if not candidates:
        return decisions_data

    # history 전체 포함해서 LLM에 전달
    print(f"\n  [drift scan] 후보 {len(candidates)}개 (score >= {threshold})")
    for c in candidates:
        print(f"    {c['id']} | score={c.get('divergence_score', 0):.2f} | {c['title'][:50]}")

    try:
        prompt = build_drift_scan_prompt(candidates, threshold)
    except FileNotFoundError as e:
        print(f"  [drift scan] {e}", file=sys.stderr)
        return decisions_data

    try:
        response = llm_caller(prompt)
    except Exception as e:
        print(f"  [drift scan] LLM 호출 실패: {e}", file=sys.stderr)
        return decisions_data

    parsed = extract_json(response)
    if not parsed or "operations" not in parsed:
        print("  [drift scan] 응답에서 operations JSON을 찾을 수 없음")
        return decisions_data

    # split만 허용, keep은 new_score로 score 업데이트
    split_ops = [op for op in parsed["operations"] if op.get("op") == "split"]
    keep_ops = [op for op in parsed["operations"] if op.get("op") == "keep"]
    split_src_ids = {op.get("source_id") for op in split_ops}

    if split_ops:
        print(f"  [drift scan] split {len(split_ops)}개 적용")
        decisions_data = apply_operations(decisions_data, split_ops, today)
    else:
        print(f"  [drift scan] split 없음")

    # split 안 된 후보들: LLM이 준 new_score로 업데이트, 없으면 0으로 리셋
    keep_score_map = {op.get("id"): op.get("new_score", 0.0) for op in keep_ops}
    for d in decisions_data.get("decisions", []):
        if d.get("id") in {c["id"] for c in candidates} and d.get("id") not in split_src_ids:
            new_score = keep_score_map.get(d.get("id"), 0.0)
            d["divergence_score"] = round(float(new_score), 3)

    return decisions_data


def build_derive_scan_prompt(candidates: dict, threshold: float) -> str:
    prompt_path = PROMPT_DIR / "derive-scan.md"
    if not prompt_path.exists():
        raise FileNotFoundError(f"derive-scan.md 없음: {prompt_path}")

    with open(prompt_path, encoding="utf-8") as f:
        template = f.read()

    candidates_json = json.dumps(candidates, ensure_ascii=False, indent=2)
    return template.replace("{{DERIVE_CANDIDATES}}", candidates_json).replace("{{THRESHOLD}}", str(threshold))


def run_derive_scan(
    decisions_data: dict,
    llm_caller,
    threshold: float,
    today: str,
) -> dict:
    """
    convergence_score >= threshold인 decision pair들을 LLM에 전달해 derive 여부 판단.
    - derive 발생: 새 decision 추가, source decisions는 active 유지, pair score 리셋
    - derive 불필요: 해당 pair score를 0.3배로 감소 (재검토 유예)
    """
    scores = decisions_data.get("convergence_scores", {})
    arr = decisions_data.get("decisions", [])
    id_map = {d["id"]: d for d in arr if d.get("status") == "active"}

    # threshold 초과 pair 추출
    candidate_pairs = [
        (key, score) for key, score in scores.items()
        if score >= threshold
    ]

    if not candidate_pairs:
        return decisions_data

    # pair의 decisions 조합 (둘 다 active인 것만)
    valid_pairs = []
    for key, score in candidate_pairs:
        parts = key.split(":")
        if len(parts) == 2 and parts[0] in id_map and parts[1] in id_map:
            valid_pairs.append((key, score, id_map[parts[0]], id_map[parts[1]]))

    if not valid_pairs:
        return decisions_data

    print(f"\n  [derive scan] 후보 pair {len(valid_pairs)}개 (score >= {threshold})")
    for key, score, d_a, d_b in valid_pairs:
        print(f"    {key} | score={score:.2f} | {d_a['title'][:30]} ↔ {d_b['title'][:30]}")

    # LLM에 넘길 candidates 구성
    seen_ids = set()
    candidates = []
    for _, _, d_a, d_b in valid_pairs:
        for d in (d_a, d_b):
            if d["id"] not in seen_ids:
                candidates.append(d)
                seen_ids.add(d["id"])

    # pair 정보도 같이 넘김
    pair_info = [{"pair": key, "score": score} for key, score, _, _ in valid_pairs]

    try:
        prompt = build_derive_scan_prompt({"decisions": candidates, "pairs": pair_info}, threshold)
    except FileNotFoundError as e:
        print(f"  [derive scan] {e}", file=sys.stderr)
        return decisions_data

    try:
        response = llm_caller(prompt)
    except Exception as e:
        print(f"  [derive scan] LLM 호출 실패: {e}", file=sys.stderr)
        return decisions_data

    parsed = extract_json(response)
    if not parsed or "operations" not in parsed:
        print("  [derive scan] 응답에서 operations JSON을 찾을 수 없음")
        return decisions_data

    # derive만 허용, keep은 new_score로 pair score 업데이트
    derive_ops = [op for op in parsed["operations"] if op.get("op") == "derive"]
    keep_ops = [op for op in parsed["operations"] if op.get("op") == "keep"]
    derived_source_sets = [set(op.get("source_ids", [])) for op in derive_ops]

    if derive_ops:
        print(f"  [derive scan] derive {len(derive_ops)}개 적용")
        decisions_data = apply_operations(decisions_data, derive_ops, today)
    else:
        print(f"  [derive scan] derive 없음")

    # pair score: derive된 것은 0, keep은 LLM이 준 new_score로, 응답 없으면 0
    keep_score_map = {op.get("pair"): op.get("new_score", 0.0) for op in keep_ops}
    for key, score, _, _ in valid_pairs:
        was_derived = any(
            all(pid in sset for pid in key.split(":"))
            for sset in derived_source_sets
        )
        if was_derived:
            scores[key] = 0.0
        else:
            scores[key] = round(float(keep_score_map.get(key, 0.0)), 3)

    decisions_data["convergence_scores"] = scores
    return decisions_data


# ─────────────────────────────────────────────
# Staleness score (GC 트리거)
# ─────────────────────────────────────────────

def _get_changed_files(repo: str, commit_hash: str) -> set[str]:
    """커밋에서 변경된 파일 목록 반환."""
    try:
        parent_check = git(repo, "rev-parse", "--verify", f"{commit_hash}^", check=False)
        if not parent_check:
            raw = git(repo, "diff", "--name-only", "4b825dc642cb6eb9a060e54bf8d69288fbee4904", commit_hash)
        else:
            raw = git(repo, "diff", "--name-only", f"{commit_hash}^", commit_hash)
        return set(f.strip() for f in raw.splitlines() if f.strip())
    except Exception:
        return set()


def _get_deleted_renamed_files(repo: str, commit_hash: str) -> set[str]:
    """커밋에서 삭제/rename된 파일 목록 반환."""
    try:
        parent_check = git(repo, "rev-parse", "--verify", f"{commit_hash}^", check=False)
        if not parent_check:
            return set()
        raw = git(repo, "diff", "--diff-filter=DR", "--name-only", f"{commit_hash}^", commit_hash)
        return set(f.strip() for f in raw.splitlines() if f.strip())
    except Exception:
        return set()


def _title_keyword_overlap(title_a: str, title_b: str) -> bool:
    """두 title의 의미 있는 키워드가 겹치는지 확인."""
    stopwords = {'the', 'a', 'an', 'is', 'are', 'as', 'at', 'by', 'for',
                 'in', 'of', 'on', 'to', 'and', 'or', 'via', 'per'}
    words_a = set(re.findall(r'[a-zA-Z가-힣]{2,}', title_a.lower())) - stopwords
    words_b = set(re.findall(r'[a-zA-Z가-힣]{2,}', title_b.lower())) - stopwords
    if not words_a or not words_b:
        return False
    return len(words_a & words_b) >= 2


def accumulate_staleness(
    decisions_data: dict,
    operations: list,
    commit_hash: str,
    repo: str,
    processed_count: int,
    cooldown: int = DEFAULT_STALENESS_COOLDOWN,
) -> dict:
    """
    S1~S4 신호를 계산해서 staleness_score 누적.
    add/update/extend 발생한 decision은 last_active_commit 갱신 + related_churn_count 리셋.

    S1. derive/split의 source_ids에 포함된 decision  +2.0
    S2. related_files 중 deleted/renamed 파일 존재    +1.5 per file
    S3. same scope + title keyword or related_files overlap인 새 ADR 추가됨  +0.8
    S4. last_active_commit 이후 related_files 변경 커밋 수가 10 증가할 때마다  +0.5
    """
    arr = decisions_data.get("decisions", [])

    # 이번 커밋에서 활동한 decision ids (last_active_commit 갱신 대상)
    active_ids = set()
    for op in operations:
        if op.get("op") in ("add", "update", "extend") and op.get("id"):
            active_ids.add(op.get("id"))
        # add는 새로 생성된 decision — id를 모르므로 apply_operations 후에 처리

    # last_active_commit 갱신 + related_churn_count 리셋
    for d in arr:
        if d.get("id") in active_ids:
            d["last_active_commit"] = commit_hash
            d["last_active_date"] = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            d["related_churn_count"] = 0
            d["staleness_score"] = max(0.0, d.get("staleness_score", 0.0) * 0.5)

    # add로 생성된 새 decisions도 last_active_commit 갱신
    add_ops = [op for op in operations if op.get("op") == "add"]
    if add_ops:
        # 가장 최근에 추가된 decisions (id 최댓값들)
        max_num = 0
        for d in arr:
            m = re.match(r'd-(\d+)', d.get("id", ""))
            if m:
                max_num = max(max_num, int(m.group(1)))
        for i, _ in enumerate(add_ops):
            target_num = max_num - len(add_ops) + 1 + i
            target_id = fmt_id(target_num)
            for d in arr:
                if d.get("id") == target_id and not d.get("last_active_commit"):
                    d["last_active_commit"] = commit_hash
                    d["last_active_date"] = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # S1: derive/split source decisions boost
    for op in operations:
        if op.get("op") == "derive":
            for src_id in op.get("source_ids", []):
                for d in arr:
                    if d.get("id") == src_id and d.get("status") == "active":
                        d["staleness_score"] = round(d.get("staleness_score", 0.0) + 2.0, 3)

        elif op.get("op") == "split":
            src_id = op.get("source_id", "")
            for d in arr:
                if d.get("id") == src_id and d.get("status") == "active":
                    d["staleness_score"] = round(d.get("staleness_score", 0.0) + 2.0, 3)

    # S2: deleted/renamed files boost
    deleted_files = _get_deleted_renamed_files(repo, commit_hash)
    if deleted_files:
        for d in arr:
            if d.get("status") != "active":
                continue
            related = set(d.get("related_files", []))
            overlap = related & deleted_files
            if overlap:
                boost = len(overlap) * 1.5
                d["staleness_score"] = round(d.get("staleness_score", 0.0) + boost, 3)

    # S3: same scope + keyword/file overlap인 새 ADR 추가됨
    new_decisions = [
        d for d in arr
        if d.get("last_active_commit") == commit_hash and d.get("id") not in active_ids
    ]
    existing = [d for d in arr if d.get("status") == "active" and d.get("last_active_commit") != commit_hash]
    for new_d in new_decisions:
        for old_d in existing:
            scope_match = new_d.get("scope", "").split("/")[0] == old_d.get("scope", "").split("/")[0]
            if not scope_match:
                continue
            title_match = _title_keyword_overlap(new_d.get("title", ""), old_d.get("title", ""))
            files_overlap = bool(set(new_d.get("related_files", [])) & set(old_d.get("related_files", [])))
            if title_match or files_overlap:
                old_d["staleness_score"] = round(old_d.get("staleness_score", 0.0) + 0.8, 3)

    # S4: related_files churn — related_files가 이번 커밋에서 변경됐으면 churn count +1
    changed_files = _get_changed_files(repo, commit_hash)
    if changed_files:
        for d in arr:
            if d.get("status") != "active":
                continue
            if d.get("id") in active_ids:
                continue  # 이미 active_commit 갱신됨
            related = set(d.get("related_files", []))
            if related & changed_files:
                d["related_churn_count"] = d.get("related_churn_count", 0) + 1
                # 10 churn마다 +0.5
                churn = d["related_churn_count"]
                if churn % 10 == 0:
                    d["staleness_score"] = round(d.get("staleness_score", 0.0) + 0.5, 3)

    return decisions_data


def build_staleness_scan_prompt(candidates: list[dict], change_summaries: dict[str, list[str]], threshold: float) -> str:
    prompt_path = PROMPT_DIR / "staleness-scan.md"
    if not prompt_path.exists():
        raise FileNotFoundError(f"staleness-scan.md 없음: {prompt_path}")

    with open(prompt_path, encoding="utf-8") as f:
        template = f.read()

    payload = json.dumps(
        {"decisions": candidates, "change_summaries": change_summaries},
        ensure_ascii=False, indent=2
    )
    return template.replace("{{STALENESS_CANDIDATES}}", payload).replace("{{THRESHOLD}}", str(threshold))


def run_staleness_scan(
    decisions_data: dict,
    llm_caller,
    threshold: float,
    today: str,
    repo: str,
    current_commit_hash: str,
    processed_count: int,
    cooldown: int = DEFAULT_STALENESS_COOLDOWN,
) -> dict:
    """
    staleness_score >= threshold인 decisions를 LLM에 전달해 keep/update/prune 판단.
    cooldown 기간(K commits) 내에 이미 review된 decision은 제외.
    """
    arr = decisions_data.get("decisions", [])

    candidates = []
    for d in arr:
        if d.get("status") != "active":
            continue
        if d.get("staleness_score", 0.0) < threshold:
            continue
        # cooldown 체크: last_reviewed_processed_count 이후 K commits 미만이면 skip
        last_reviewed_count = d.get("last_reviewed_processed_count", -1)
        if last_reviewed_count >= 0 and (processed_count - last_reviewed_count) < cooldown:
            continue
        candidates.append(d)

    if not candidates:
        return decisions_data

    print(f"\n  [staleness scan] 후보 {len(candidates)}개 (score >= {threshold})")
    for c in candidates:
        print(f"    {c['id']} | score={c.get('staleness_score', 0):.2f} | {c['title'][:50]}")

    # 각 candidate의 last_active_commit 이후 related_files 변경 커밋 subjects 수집
    change_summaries: dict[str, list[str]] = {}
    for d in candidates:
        since = d.get("last_active_commit", "")
        related = d.get("related_files", [])
        if not since or not related:
            change_summaries[d["id"]] = []
            continue
        try:
            # last_active_commit 이후 related_files 중 하나라도 변경한 커밋의 subject 목록
            subjects = []
            raw = git(repo, "log", "--oneline", f"{since}..HEAD", "--", *related[:5])
            for line in raw.splitlines()[:10]:
                subjects.append(line.strip())
            change_summaries[d["id"]] = subjects
        except Exception:
            change_summaries[d["id"]] = []

    try:
        prompt = build_staleness_scan_prompt(candidates, change_summaries, threshold)
    except FileNotFoundError as e:
        print(f"  [staleness scan] {e}", file=sys.stderr)
        return decisions_data

    try:
        response = llm_caller(prompt)
    except Exception as e:
        print(f"  [staleness scan] LLM 호출 실패: {e}", file=sys.stderr)
        return decisions_data

    parsed = extract_json(response)
    if not parsed or "operations" not in parsed:
        print("  [staleness scan] 응답에서 operations JSON을 찾을 수 없음")
        return decisions_data

    # keep/update/prune만 허용, keep은 new_score로 staleness_score 업데이트
    allowed_ops = [op for op in parsed["operations"] if op.get("op") in ("update", "prune")]
    keep_ops = [op for op in parsed["operations"] if op.get("op") == "keep"]

    if allowed_ops:
        print(f"  [staleness scan] {len(allowed_ops)}개 operation 적용")
        decisions_data = apply_operations(decisions_data, allowed_ops, today)

    # score 업데이트: update/prune은 0으로 리셋, keep은 LLM이 준 new_score로 설정
    operated_ids = {op.get("id") for op in allowed_ops}
    keep_score_map = {op.get("id"): op.get("new_score", 0.0) for op in keep_ops}
    for d in decisions_data.get("decisions", []):
        d_id = d.get("id")
        if d_id not in {c["id"] for c in candidates}:
            continue
        if d_id in operated_ids:
            d["staleness_score"] = 0.0
        else:
            new_score = keep_score_map.get(d_id, 0.0)
            d["staleness_score"] = round(float(new_score), 3)
            d["last_reviewed_commit"] = current_commit_hash
            d["last_reviewed_processed_count"] = processed_count

    return decisions_data


# ─────────────────────────────────────────────
# 상태 파일
# ─────────────────────────────────────────────

def load_state(output_dir: Path) -> dict:
    path = output_dir / STATE_FILENAME
    if path.exists():
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return {"last_processed_hash": None, "processed_count": 0}


def save_state(output_dir: Path, state: dict) -> None:
    path = output_dir / STATE_FILENAME
    with open(path, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


# ─────────────────────────────────────────────
# LLM 호출
# ─────────────────────────────────────────────

SCOPE_META: dict[str, dict[str, str]] = {
    "implementation": {
        "example": "src/api/auth or architecture/layers or src/components/common, etc.",
        "description": "scope should reflect the code path or conceptual layer impacted\n"
                       "(e.g., `src/api/auth`, `architecture/module-boundaries`, `src/components/common`, `infrastructure/docker`).",
    },
    "design": {
        "example": "design-system/tokens or ux/feedback or design-system/accessibility, etc.",
        "description": "scope should reflect the UI/UX concern\n"
                       "(e.g., `design-system/tokens`, `ux/form-patterns`, `design-system/accessibility`, `ux/navigation`).",
    },
    "planning": {
        "example": "domain/user or product/billing or policy/access, etc.",
        "description": "scope should reflect the product or domain area\n"
                       "(e.g., `domain/subscription`, `product/onboarding`, `policy/access-control`, `domain/notification`).",
    },
}


def build_prompt(target: str, commit: dict, diff: str, existing_canonical: list) -> str:
    prompt_path = PROMPT_DIR / f"{target}.md"
    global_rules_path = PROMPT_DIR / "global-rules.md"

    if not prompt_path.exists():
        available = [p.stem for p in PROMPT_DIR.glob("*.md") if p.stem != "global-rules"]
        raise FileNotFoundError(
            f"프롬프트 파일이 없습니다: {prompt_path}\n"
            f"사용 가능한 타겟: {', '.join(available)}"
        )

    with open(prompt_path, encoding="utf-8") as f:
        target_template = f.read()

    with open(global_rules_path, encoding="utf-8") as f:
        global_template = f.read()

    # 타겟별 scope 메타 치환
    meta = SCOPE_META.get(target, {"example": "...", "description": ""})
    global_template = global_template.replace("{{SCOPE_EXAMPLE}}", meta["example"])
    global_template = global_template.replace("{{SCOPE_DESCRIPTION}}", meta["description"])

    # 타겟 + 글로벌 룰 조합
    template = target_template + "\n\n" + global_template

    canonical_summary = json.dumps(existing_canonical[:50], ensure_ascii=False, indent=2)

    prompt = template.replace("{{COMMIT_HASH}}", commit["hash"][:12])
    prompt = prompt.replace("{{COMMIT_SUBJECT}}", commit["subject"])
    prompt = prompt.replace("{{COMMIT_AUTHOR}}", commit["author"])
    prompt = prompt.replace("{{GIT_DIFF}}", diff)
    prompt = prompt.replace("{{EXISTING_DECISIONS}}", canonical_summary)

    return prompt


def call_llm_api(prompt: str, api_base: str, api_key: str, model: str) -> str:
    import urllib.request

    payload = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.2,
    }).encode("utf-8")

    url = api_base.rstrip("/") + "/chat/completions"
    req = urllib.request.Request(
        url,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )

    with urllib.request.urlopen(req, timeout=120) as resp:
        data = json.loads(resp.read().decode("utf-8"))

    return data["choices"][0]["message"]["content"]


def call_llm_cmd(prompt: str, llm_cmd: str) -> str:
    result = subprocess.run(
        llm_cmd,
        shell=True,
        input=prompt,
        capture_output=True,
        text=True,
        timeout=180,
    )
    if result.returncode != 0:
        raise RuntimeError(f"LLM 커맨드 실패 (exit {result.returncode}):\n{result.stderr}")
    return result.stdout


def extract_json(text: str) -> Optional[dict]:
    m = re.search(r'```json\s*([\s\S]*?)```', text)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            pass

    m = re.search(r'```\s*([\s\S]*?)```', text)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            pass

    m = re.search(r'\{[\s\S]*"operations"[\s\S]*\}', text)
    if m:
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            pass

    return None


def get_canonical_summary(decisions_data: dict) -> list:
    result = []
    for d in decisions_data.get("decisions", []):
        if d.get("status") != "active":
            continue
        reason = d.get("reason", "")
        m = re.search(r'\.\s+[A-Z`]', reason)
        summary = reason[:m.start() + 1].strip() if m else reason.strip()
        if not summary:
            summary = d.get("title", "")

        entry = {
            "id": d.get("id"),
            "title": d.get("title"),
            "scope": d.get("scope"),
            "summary": summary,
        }

        # extensions 요약 — LLM이 중복 extend를 피할 수 있도록
        extensions = d.get("extensions", [])
        if extensions:
            entry["extensions_count"] = len(extensions)
            # 가장 최근 extension의 evidence 첫 문장만 포함
            last_evidence = extensions[-1].get("evidence", "")
            m2 = re.search(r'\.\s+[A-Z`]', last_evidence)
            entry["latest_extension"] = last_evidence[:m2.start() + 1].strip() if m2 else last_evidence[:120].strip()

        result.append(entry)
    return result


# ─────────────────────────────────────────────
# CLAUDE.md export
# ─────────────────────────────────────────────

def _build_adr_content_block(decisions_data: dict) -> str:
    summary = get_canonical_summary(decisions_data)
    if not summary:
        return "No active decisions yet."

    date_map = {
        d["id"]: d.get("documentDate", "")
        for d in decisions_data.get("decisions", [])
    }
    summary.sort(
        key=lambda item: (date_map.get(item.get("id", ""), ""), item.get("id", "")),
        reverse=True,
    )

    full_json = json.dumps(summary, ensure_ascii=False, indent=2)
    block = "```json\n" + full_json + "\n```"
    if len(block.encode("utf-8")) <= ADR_MAX_BYTES:
        return block

    while summary:
        summary.pop()
        candidate = "```json\n" + json.dumps(summary, ensure_ascii=False, indent=2) + "\n```"
        if len(candidate.encode("utf-8")) <= ADR_MAX_BYTES:
            return candidate

    return "No active decisions yet. (all entries exceed 8KB limit)"


def _upsert_claude_md(claude_md_path: Path, content_block: str) -> None:
    new_section = f"{ADR_SECTION_HEADER}\n{ADR_START_MARKER}\n{content_block}\n{ADR_END_MARKER}"

    if not claude_md_path.exists():
        claude_md_path.write_text(new_section + "\n", encoding="utf-8")
        return

    text = claude_md_path.read_text(encoding="utf-8")
    start_pos = text.find(ADR_START_MARKER)
    end_pos = text.find(ADR_END_MARKER)

    if start_pos != -1 and end_pos != -1 and start_pos < end_pos:
        # 마커 사이 내용 교체 (마커 포함)
        after_end = end_pos + len(ADR_END_MARKER)
        new_text = (
            text[:start_pos]
            + ADR_START_MARKER + "\n"
            + content_block + "\n"
            + ADR_END_MARKER
            + text[after_end:]
        )
    else:
        header_match = re.search(r'^## Architecture Decisions$', text, re.MULTILINE)
        if header_match:
            # 헤더는 있으나 마커 없음 — 섹션 전체를 마커로 감싸 교체
            header_start = header_match.start()
            content_start = header_match.end() + 1  # 헤더 뒤 \n 건너뜀
            next_h2 = re.search(r'^## ', text[content_start:], re.MULTILINE)
            if next_h2:
                section_end = content_start + next_h2.start()
                new_text = text[:header_start] + new_section + "\n" + text[section_end:]
            else:
                new_text = text[:header_start] + new_section + "\n"
        else:
            # 헤더도 마커도 없음 — 파일 끝에 추가
            new_text = text.rstrip("\n") + "\n\n" + new_section + "\n"

    claude_md_path.write_text(new_text, encoding="utf-8")


def export_claude_md(output_dir: Path, repo_dir: Path) -> None:
    decisions_path = output_dir / DECISIONS_FILENAME
    if not decisions_path.exists():
        print(f"오류: decisions.json을 찾을 수 없습니다: {decisions_path}", file=sys.stderr)
        print("먼저 git-adr.py를 실행하여 decisions.json을 생성하세요.", file=sys.stderr)
        sys.exit(1)

    with open(decisions_path, encoding="utf-8") as f:
        decisions_data = json.load(f)

    content_block = _build_adr_content_block(decisions_data)
    claude_md_path = repo_dir / CLAUDE_MD_FILENAME

    try:
        _upsert_claude_md(claude_md_path, content_block)
    except PermissionError:
        print(f"오류: {claude_md_path} 쓰기 권한이 없습니다.", file=sys.stderr)
        print(f"힌트: chmod 644 {claude_md_path}", file=sys.stderr)
        sys.exit(1)

    active_count = sum(
        1 for d in decisions_data.get("decisions", []) if d.get("status") == "active"
    )
    print(f"✓ {claude_md_path} 업데이트 완료 (active decisions: {active_count}개)")


# ─────────────────────────────────────────────
# 메인 파이프라인
# ─────────────────────────────────────────────

def process_commit(
    commit: dict,
    repo: str,
    target: str,
    output_dir: Path,
    decisions_data: dict,
    llm_caller,
    filters: dict,
    max_diff: int,
    dry_run: bool,
    verbose: bool,
    drift_threshold: float,
    no_drift_scan: bool,
    derive_threshold: float,
    no_derive_scan: bool,
    staleness_threshold: float,
    no_staleness_scan: bool,
    staleness_cooldown: int,
    processed_count: int,
) -> dict:
    print(f"\n{'─'*60}")
    print(f"  커밋: {commit['hash'][:12]} | {commit['subject'][:60]}")
    print(f"  날짜: {commit['date']} | 작성자: {commit['author']}")

    diff = get_diff(repo, commit["hash"])
    if not diff.strip():
        print("  → diff 없음, 건너뜀")
        return decisions_data

    diff, used_fallback = apply_target_filter(diff, filters, verbose=verbose)
    if not diff.strip():
        print("  → 타겟 관련 파일 없음, 건너뜀")
        return decisions_data

    if used_fallback:
        print("  [fallback 사용] 필터 미매칭으로 전체 diff 분석")

    diff = truncate_diff(diff, max_diff)
    print(f"  diff 크기: {len(diff):,} 자")

    if verbose:
        print(f"\n[diff preview]\n{diff[:500]}...\n")

    canonical = get_canonical_summary(decisions_data)
    prompt = build_prompt(target, commit, diff, canonical)

    if verbose:
        print(f"\n[prompt length] {len(prompt):,} 자")

    if dry_run:
        print("  → [dry-run] LLM 호출 건너뜀")
        return decisions_data

    print("  → LLM 호출 중...")
    try:
        response = llm_caller(prompt)
    except Exception as e:
        print(f"  ✗ LLM 호출 실패: {e}")
        return decisions_data

    if verbose:
        print(f"\n[LLM response]\n{response[:1000]}\n")

    parsed = extract_json(response)
    if not parsed or "operations" not in parsed:
        print("  ✗ LLM 응답에서 operations JSON을 찾을 수 없음")
        if not verbose:
            print(f"  응답 미리보기: {response[:300]}")
        return decisions_data

    operations = parsed["operations"]
    if not operations:
        print("  → ADR 변경사항 없음 (operations 비어있음)")
        return decisions_data

    op_summary = ", ".join(f"{op.get('op')}({op.get('title', op.get('id',''))})" for op in operations)
    print(f"  operations ({len(operations)}): {op_summary}")

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    commit_date = commit["date"].split(" ")[0] if commit.get("date") else ""
    decisions_data = apply_operations(decisions_data, operations, today, commit_date)
    print(f"  ✓ decisions 총 {len(decisions_data.get('decisions', []))}개")

    # 2. convergence score 누적
    if not no_drift_scan:
        decisions_data = accumulate_convergence(decisions_data, operations)

    # 3. drift scan: divergence_score >= threshold → split
    if not no_drift_scan:
        decisions_data = run_drift_scan(decisions_data, llm_caller, drift_threshold, today)

    # 4. derive scan: convergence_score >= threshold → derive
    if not no_derive_scan:
        decisions_data = run_derive_scan(decisions_data, llm_caller, derive_threshold, today)

    # 5. staleness score 누적 (split/derive 결과 반영 후)
    if not no_staleness_scan:
        decisions_data = accumulate_staleness(
            decisions_data, operations, commit["hash"], repo, processed_count, staleness_cooldown
        )

    # 6. staleness scan: staleness_score >= threshold → keep/update/prune
    if not no_staleness_scan:
        decisions_data = run_staleness_scan(
            decisions_data, llm_caller, staleness_threshold, today,
            repo, commit["hash"], processed_count, staleness_cooldown
        )

    return decisions_data


def main() -> None:
    parser = argparse.ArgumentParser(
        description="git 히스토리를 순회하며 ADR을 누적 생성",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""
        예시:
          # OpenAI API 사용
          python git-adr.py --repo ~/myproject --target implementation \\
            --api-base https://api.openai.com/v1 --api-key $OPENAI_API_KEY \\
            --model gpt-4o --output ~/myproject-adr/

          # 커스텀 LLM CLI 사용 (stdin으로 프롬프트 주입)
          python git-adr.py --repo ~/myproject --target implementation \\
            --llm-cmd "my-llm --model claude" --output ./adr-output/

          # 이어서 실행 (--resume)
          python git-adr.py --repo ~/myproject --target implementation \\
            --api-base https://api.openai.com/v1 --api-key $OPENAI_API_KEY \\
            --output ~/myproject-adr/ --resume

          # 처음 10개 커밋만 dry-run으로 테스트
          python git-adr.py --repo ~/myproject --target implementation \\
            --api-base https://api.openai.com/v1 --api-key $OPENAI_API_KEY \\
            --output ./test-adr/ --dry-run --limit 10
        """),
    )

    parser.add_argument("--repo", help="분석할 git 레포지터리 경로 (export 모드에서는 CWD 기본값)")
    parser.add_argument(
        "--target",
        choices=["implementation", "design", "planning"],
        help="ADR 타겟 도메인",
    )
    parser.add_argument("--output", required=True, help="decisions.json 저장 디렉터리")
    parser.add_argument(
        "--export-claude-md",
        action="store_true",
        help="decisions.json → CLAUDE.md ## Architecture Decisions 섹션 upsert (LLM 불필요)",
    )

    llm_group = parser.add_mutually_exclusive_group()
    llm_group.add_argument("--api-base", help="OpenAI-compatible API base URL")
    llm_group.add_argument("--llm-cmd", help="커스텀 LLM CLI 커맨드 (stdin으로 프롬프트 주입)")

    parser.add_argument("--api-key", help="API 키 (또는 OPENAI_API_KEY 환경변수)")
    parser.add_argument("--model", default="gpt-4o", help="모델명 (기본: gpt-4o)")

    parser.add_argument("--skip-repo-scan", action="store_true",
                        help="레포 구조 LLM 스캔 생략 (기본 필터 또는 기존 .adr-filters.yaml 사용)")
    parser.add_argument("--filters-file",
                        help="사용할 필터 파일 경로 (기본: <repo>/.adr-filters.yaml)")

    parser.add_argument("--drift-threshold", type=float, default=DEFAULT_DRIFT_THRESHOLD,
                        help=f"divergence score 임계값 (기본: {DEFAULT_DRIFT_THRESHOLD})")
    parser.add_argument("--no-drift-scan", action="store_true",
                        help="drift scan 비활성화")
    parser.add_argument("--derive-threshold", type=float, default=DEFAULT_DERIVE_THRESHOLD,
                        help=f"convergence score 임계값 (기본: {DEFAULT_DERIVE_THRESHOLD})")
    parser.add_argument("--no-derive-scan", action="store_true",
                        help="derive scan 비활성화")
    parser.add_argument("--staleness-threshold", type=float, default=DEFAULT_STALENESS_THRESHOLD,
                        help=f"staleness score 임계값 (기본: {DEFAULT_STALENESS_THRESHOLD})")
    parser.add_argument("--no-staleness-scan", action="store_true",
                        help="staleness scan 비활성화 (GC 루프)")
    parser.add_argument("--staleness-cooldown", type=int, default=DEFAULT_STALENESS_COOLDOWN,
                        help=f"keep 후 staleness scan 제외 커밋 수 (기본: {DEFAULT_STALENESS_COOLDOWN})")

    parser.add_argument("--resume", action="store_true", help="마지막 처리 커밋부터 재개")
    parser.add_argument("--limit", type=int, help="처리할 최대 커밋 수 (테스트용)")
    parser.add_argument("--max-diff", type=int, default=DEFAULT_MAX_DIFF,
                        help=f"diff 최대 문자 수 (기본: {DEFAULT_MAX_DIFF})")
    parser.add_argument("--context-lines", type=int, default=DEFAULT_CONTEXT_LINES,
                        help=f"git diff context lines (기본: {DEFAULT_CONTEXT_LINES})")
    parser.add_argument("--dry-run", action="store_true", help="LLM 호출 없이 diff만 추출 (테스트)")
    parser.add_argument("--verbose", "-v", action="store_true", help="상세 출력")
    parser.add_argument("--from-commit", help="이 커밋 해시 이후부터 처리")
    parser.add_argument("--save-every", type=int, default=1, help="N개 커밋마다 저장 (기본: 1)")

    args = parser.parse_args()

    output_dir = Path(args.output).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    if args.export_claude_md:
        repo_dir = Path(args.repo).expanduser().resolve() if args.repo else Path.cwd()
        export_claude_md(output_dir, repo_dir)
        return

    if args.repo is None:
        parser.error("--repo 는 필수입니다 (--export-claude-md 모드 외)")
    if args.target is None:
        parser.error("--target 는 필수입니다 (--export-claude-md 모드 외)")
    if args.api_base is None and args.llm_cmd is None:
        parser.error("--api-base 또는 --llm-cmd 중 하나가 필요합니다 (--export-claude-md 모드 외)")

    if args.api_base:
        api_key = args.api_key or os.environ.get("OPENAI_API_KEY", "")
        if not api_key:
            print("오류: --api-key 또는 OPENAI_API_KEY 환경변수가 필요합니다.", file=sys.stderr)
            sys.exit(1)
        llm_caller = lambda prompt: call_llm_api(prompt, args.api_base, api_key, args.model)
        print(f"LLM: {args.api_base} | 모델: {args.model}")
    else:
        llm_caller = lambda prompt: call_llm_cmd(prompt, args.llm_cmd)
        print(f"LLM: {args.llm_cmd}")

    repo = str(Path(args.repo).expanduser().resolve())
    try:
        head = git(repo, "rev-parse", "HEAD")
        print(f"레포: {repo} (HEAD: {head[:12]})")
    except subprocess.CalledProcessError:
        print(f"오류: git 레포지터리를 찾을 수 없습니다: {repo}", file=sys.stderr)
        sys.exit(1)

    # 필터 준비
    repo_filters_path = Path(repo) / FILTERS_FILENAME
    filters_exist = repo_filters_path.exists() or bool(args.filters_file)

    if not args.skip_repo_scan and not filters_exist and not args.dry_run:
        print(f"\n[필터 준비] .adr-filters.yaml 없음 → LLM 스캔 시작")
        generated = generate_filters_with_llm(repo, llm_caller)
        if generated:
            saved = save_filters_yaml(repo, generated)
            print(f"  [filters] 생성 완료: {saved}")
        else:
            print(f"  [filters] 생성 실패 → 기본 패턴 사용")
    elif args.skip_repo_scan:
        print(f"[필터 준비] --skip-repo-scan → 기본 패턴 또는 기존 파일 사용")

    filters = load_filters(repo, args.target, args.filters_file)
    if filters:
        print(f"[필터] target={args.target} | include={len(filters.get('include', []))}개 | exclude={len(filters.get('exclude', []))}개")
    else:
        print(f"[필터] target={args.target} | 필터 없음 (전체 허용)")

    drift_info = f"threshold={args.drift_threshold}" if not args.no_drift_scan else "비활성"
    print(f"[drift scan] {drift_info}")
    derive_info = f"threshold={args.derive_threshold}" if not args.no_derive_scan else "비활성"
    print(f"[derive scan] {derive_info}")
    staleness_info = f"threshold={args.staleness_threshold}, cooldown={args.staleness_cooldown}" if not args.no_staleness_scan else "비활성"
    print(f"[staleness scan] {staleness_info}")

    state = load_state(output_dir)
    decisions_data = load_decisions(output_dir)

    from_hash = None
    if args.resume and state.get("last_processed_hash"):
        from_hash = state["last_processed_hash"]
        print(f"이어서 실행: {from_hash[:12]} 이후부터")
    elif args.from_commit:
        from_hash = args.from_commit
        print(f"지정된 커밋부터: {from_hash[:12]} 이후")

    commits = get_commits(repo, from_hash)
    print(f"\n처리할 커밋: {len(commits)}개 | 타겟: {args.target}")
    print(f"출력 디렉터리: {output_dir}")
    print(f"기존 decisions: {len(decisions_data.get('decisions', []))}개\n")

    if not commits:
        print("처리할 커밋이 없습니다.")
        return

    if args.limit:
        commits = commits[:args.limit]
        print(f"(--limit {args.limit} 적용: {len(commits)}개만 처리)")

    processed = 0
    for i, commit in enumerate(commits, 1):
        print(f"\n[{i}/{len(commits)}]", end="")

        decisions_data = process_commit(
            commit=commit,
            repo=repo,
            target=args.target,
            output_dir=output_dir,
            decisions_data=decisions_data,
            llm_caller=llm_caller,
            filters=filters,
            max_diff=args.max_diff,
            dry_run=args.dry_run,
            verbose=args.verbose,
            drift_threshold=args.drift_threshold,
            no_drift_scan=args.no_drift_scan,
            derive_threshold=args.derive_threshold,
            no_derive_scan=args.no_derive_scan,
            staleness_threshold=args.staleness_threshold,
            no_staleness_scan=args.no_staleness_scan,
            staleness_cooldown=args.staleness_cooldown,
            processed_count=processed,
        )

        state["last_processed_hash"] = commit["hash"]
        state["processed_count"] = state.get("processed_count", 0) + 1
        processed += 1

        if processed % args.save_every == 0 and not args.dry_run:
            save_decisions(output_dir, decisions_data)
            save_state(output_dir, state)

    if not args.dry_run:
        save_decisions(output_dir, decisions_data)
        save_state(output_dir, state)

    print(f"\n{'═'*60}")
    print(f"완료: {processed}개 커밋 처리")
    print(f"최종 decisions: {len(decisions_data.get('decisions', []))}개")
    print(f"출력: {output_dir / DECISIONS_FILENAME}")


if __name__ == "__main__":
    main()
