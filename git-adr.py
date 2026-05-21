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
DEFAULT_MAX_DIFF = 12000        # characters (roughly 3k tokens)
DEFAULT_CONTEXT_LINES = 5       # git diff unified context lines

# 전역 제외 목록 — 타겟 무관하게 항상 제외
GLOBAL_EXCLUDE = [
    # 패키지 락 파일
    "*.lock", "*.sum",
    "package-lock.json", "yarn.lock", "pnpm-lock.yaml",
    "Cargo.lock", "Gemfile.lock", "poetry.lock",
    # 바이너리 / 압축
    "*.zip", "*.tar", "*.tar.gz", "*.tgz", "*.gz", "*.bz2", "*.xz",
    "*.7z", "*.rar", "*.jar", "*.war", "*.ear",
    # 이미지
    "*.png", "*.jpg", "*.jpeg", "*.gif", "*.webp", "*.avif",
    "*.ico", "*.bmp", "*.tiff",
    # 폰트
    "*.woff", "*.woff2", "*.ttf", "*.otf", "*.eot",
    # 문서/미디어
    "*.pdf", "*.doc", "*.docx", "*.xls", "*.xlsx",
    "*.mp3", "*.mp4", "*.wav", "*.mov", "*.avi",
    # 컴파일 산출물
    "*.pyc", "*.pyo", "*.class", "*.o", "*.so", "*.dll", "*.exe",
    "*.map",
    # 스냅샷/생성 파일
    "*.snap",
    "*.min.js", "*.min.css",
    # AI 에이전트 지시/설정 파일 — 범용 툴 설정, 결정 기록 아님
    "CLAUDE.md", "AGENTS.md",
    ".cursorrules", "COPILOT-INSTRUCTIONS.md", ".github/copilot-instructions.md",
    # 텍스트 상태/메모 파일 — 코드 아님
    "*.txt",
    # 경로 기반 제외
    ".git/*",
    "node_modules/*",
    "__pycache__/*",
    "dist/*", "build/*", ".next/*", ".nuxt/*",
    "coverage/*", ".cache/*",
    "vendor/*", ".venv/*", "venv/*", "env/*",
]

# 타겟별 기본 include 패턴 — 없으면 전체 허용(GLOBAL_EXCLUDE만 적용)
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
            "docs/**", "*.md",     # 개발 문서 포함
        ],
        "exclude": [
            "**/*.test.*", "**/*.spec.*", "**/__tests__/**",
            "**/*.stories.*",
            "**/styles/**", "**/tokens/**", "**/themes/**",
            "**/*.css", "**/*.scss", "**/*.sass", "**/*.less",
            "**/*.sh",             # 스크립팅/운영 목적, 구현 결정 아님
            "CHANGELOG.md",        # 릴리즈 로그, 결정 기록 아님
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
        # 경로의 각 부분에 대해서도 시도 (예: **/foo/** 패턴)
        if fnmatch.fnmatch(fpath, pat.lstrip("*/")):
            return True
        # fnmatch는 ** 를 제대로 처리 못하므로 간단히 변환
        regex = _glob_to_regex(pat)
        if re.match(regex, fpath):
            return True
    return False


def _glob_to_regex(pat: str) -> str:
    """glob 패턴을 정규식으로 변환 (** 지원)."""
    pat = pat.replace(".", r"\.")
    pat = pat.replace("**", "\x00")   # ** 임시 치환
    pat = pat.replace("*", "[^/]*")
    pat = pat.replace("\x00", ".*")   # ** → 경로 포함 임의 문자열
    pat = pat.replace("?", "[^/]")
    return f"^{pat}$"


def should_include_file(fpath: str, filters: dict) -> tuple[bool, str]:
    """
    파일을 포함할지 여부와 이유를 반환.
    반환: (include: bool, reason: str)
    """
    # 1. 전역 제외 우선
    if matches_any(fpath, GLOBAL_EXCLUDE):
        return False, "global_exclude"

    include_pats = filters.get("include", [])
    exclude_pats = filters.get("exclude", [])

    # 2. include 패턴이 없으면 전체 허용 (fallback)
    if not include_pats:
        if exclude_pats and matches_any(fpath, exclude_pats):
            return False, "target_exclude"
        return True, "no_include_filter"

    # 3. include 매칭 확인
    included = matches_any(fpath, include_pats)
    if not included:
        return False, "not_in_include"

    # 4. exclude 매칭 확인
    if exclude_pats and matches_any(fpath, exclude_pats):
        return False, "target_exclude"

    return True, "matched"


# ─────────────────────────────────────────────
# 필터 관리
# ─────────────────────────────────────────────

def load_filters(repo: str, target: str, filters_file: Optional[str] = None) -> dict:
    """
    필터 로딩 우선순위:
    1. --filters-file 명시적 지정
    2. 레포 루트의 .adr-filters.yaml
    3. DEFAULT_TARGET_FILTERS 기본값
    """
    # 명시적 파일 지정
    if filters_file:
        path = Path(filters_file)
        if path.exists():
            return _parse_filters_yaml(path, target)
        else:
            print(f"  [경고] --filters-file '{filters_file}' 없음, 기본값 사용", file=sys.stderr)

    # 레포 루트 .adr-filters.yaml
    repo_filters = Path(repo) / FILTERS_FILENAME
    if repo_filters.exists():
        parsed = _parse_filters_yaml(repo_filters, target)
        if parsed:
            print(f"  [filters] {repo_filters} 로드")
            return parsed

    # 기본값
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
    """LLM이 생성한 필터를 .adr-filters.yaml로 저장."""
    path = Path(repo) / FILTERS_FILENAME
    if HAS_YAML:
        with open(path, "w", encoding="utf-8") as f:
            yaml.dump(filters, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
    else:
        # yaml 없으면 간단한 직렬화
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
    """
    git ls-files로 파일 목록을 수집하고 디렉터리 구조 요약 반환.
    LLM에게 레포 구조를 파악할 충분한 컨텍스트를 제공.
    """
    raw = git(repo, "ls-files")
    all_files = [f for f in raw.splitlines() if f.strip()]

    # GLOBAL_EXCLUDE 적용해서 노이즈 제거
    filtered = [f for f in all_files if not matches_any(f, GLOBAL_EXCLUDE)]

    # 최대 파일 수 제한 (프롬프트 크기 관리)
    sample = filtered[:max_files]
    truncated = len(filtered) > max_files

    # 디렉터리 트리 요약
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
    """LLM이 레포 구조를 보고 .adr-filters.yaml 내용을 생성."""
    print("  레포 구조 스캔 중...")
    structure = scan_repo_structure(repo)

    print("  LLM으로 필터 패턴 생성 중...")
    prompt = build_filter_scan_prompt(structure)

    try:
        response = llm_caller(prompt)
    except Exception as e:
        print(f"  [경고] 필터 생성 LLM 호출 실패: {e}", file=sys.stderr)
        return None

    # YAML 블록 추출
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
        # yaml 없으면 간단한 파싱 시도 (기본 구조만)
        print("  [경고] PyYAML 미설치. 기본 필터 사용. pip install pyyaml 권장.", file=sys.stderr)
        return None

    return None


# ─────────────────────────────────────────────
# diff 필터링 (타겟 적용)
# ─────────────────────────────────────────────

def apply_target_filter(diff: str, filters: dict, verbose: bool = False) -> tuple[str, bool]:
    """
    diff에서 타겟 필터에 맞는 파일만 추출.
    반환: (filtered_diff, used_fallback)

    fallback 조건: 필터 적용 후 파일이 0개 → 전체 diff 반환 + 경고
    """
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
        # fallback: 필터가 모든 파일을 걸러냄 → 전체 반환
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
    """initial commit부터 최신 순서대로 커밋 목록 반환."""
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
    """커밋의 diff를 반환. initial commit은 empty tree와 비교."""
    parent_check = git(repo, "rev-parse", "--verify", f"{commit_hash}^", check=False)
    if not parent_check:
        empty_tree = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"
        raw_diff = git(repo, "diff", f"--unified={context_lines}", empty_tree, commit_hash)
    else:
        raw_diff = git(repo, "diff", f"--unified={context_lines}", f"{commit_hash}^", commit_hash)

    # 전역 제외만 적용 (타겟 필터는 apply_target_filter에서 별도 처리)
    return _apply_global_exclude(raw_diff)


def _apply_global_exclude(diff: str) -> str:
    """GLOBAL_EXCLUDE만 적용한 diff 반환."""
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
    """diff가 너무 크면 파일별로 균등 분배 후 truncate."""
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
# decisions.json 관리
# ─────────────────────────────────────────────

def load_decisions(output_dir: Path) -> dict:
    path = output_dir / DECISIONS_FILENAME
    if path.exists():
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return {"decisions": []}


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


def apply_operations(decisions_data: dict, operations: list, today: str, commit_date: str = "") -> dict:
    """update-decisions.sh 로직을 Python으로 구현."""
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
        op_pat = op.get("title_pattern", "")

        if op_type == "add":
            arr.append({
                "id": fmt_id(counter),
                "status": "active",
                "documentDate": today,
                "commitDate": commit_date,
                "scope": op_scope,
                "title": op.get("title", ""),
                "reason": op.get("reason", ""),
                "alternatives": op.get("alternatives", []),
                "consequences": op.get("consequences", []),
                "refs": op.get("refs", []),
                "related_files": op.get("related_files", []),
                "derived_from": None,
                "history": [],
            })
            counter += 1

        elif op_type == "update":
            idx = find_idx(arr, id_=op_id, scope=op_scope, pat=op_pat)
            if idx >= 0:
                d = arr[idx]
                d["history"] = d.get("history", []) + [{
                    "documentDate": d.get("documentDate", d.get("date")),
                    "commitDate": d.get("commitDate", ""),
                    "title": d.get("title"),
                    "reason": d.get("reason"),
                    "action": "updated",
                }]
                d["documentDate"] = today
                d["commitDate"] = commit_date
                if op.get("reason"):
                    d["reason"] = op["reason"]
                if op.get("refs") is not None:
                    d["refs"] = op["refs"]
                if op.get("related_files") is not None:
                    d["related_files"] = op["related_files"]
                if op.get("title"):
                    d["title"] = op["title"]
                if op.get("scope"):
                    d["scope"] = op["scope"]

        elif op_type == "prune":
            idx = find_idx(arr, id_=op_id, scope=op_scope, pat=op_pat)
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
            arr.append({
                "id": fmt_id(counter),
                "status": "active",
                "documentDate": today,
                "commitDate": commit_date,
                "scope": op_scope,
                "title": op.get("title", ""),
                "reason": op.get("reason", ""),
                "alternatives": op.get("alternatives", []),
                "consequences": op.get("consequences", []),
                "refs": op.get("refs", []),
                "related_files": op.get("related_files", []),
                "derived_from": op.get("source_ids", []),
                "history": [],
            })
            counter += 1

        elif op_type == "merge":
            sources = op.get("source_ids", [])
            arr.append({
                "id": fmt_id(counter),
                "status": "active",
                "documentDate": today,
                "commitDate": commit_date,
                "scope": op_scope,
                "title": op.get("title", ""),
                "reason": op.get("reason", ""),
                "alternatives": op.get("alternatives", []),
                "consequences": op.get("consequences", []),
                "refs": op.get("refs", []),
                "related_files": op.get("related_files", []),
                "merged_from": sources,
                "history": [],
            })
            counter += 1
            for d in arr:
                if d.get("id") in sources:
                    d["history"] = d.get("history", []) + [{
                        "documentDate": d.get("documentDate", d.get("date")),
                        "commitDate": d.get("commitDate", ""),
                        "title": d.get("title"),
                        "reason": d.get("reason"),
                        "action": "merged",
                        "merged_into": fmt_id(counter - 1),
                    }]
                    d["status"] = "superseded"

        elif op_type == "split":
            src_id = op.get("source_id", "")
            parts = op.get("into", [])
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
                    break
            for part in parts:
                arr.append({
                    "id": fmt_id(counter),
                    "status": "active",
                    "documentDate": today,
                    "commitDate": commit_date,
                    "scope": part.get("scope", ""),
                    "title": part.get("title", ""),
                    "reason": part.get("reason", ""),
                    "alternatives": part.get("alternatives", []),
                    "consequences": part.get("consequences", []),
                    "refs": part.get("refs", []),
                    "related_files": part.get("related_files", []),
                    "split_from": src_id,
                    "history": [],
                })
                counter += 1

    return {"decisions": arr}


# ─────────────────────────────────────────────
# 상태 파일 (resume 지원)
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

def build_prompt(target: str, commit: dict, diff: str, existing_canonical: list) -> str:
    prompt_path = PROMPT_DIR / f"{target}.md"
    if not prompt_path.exists():
        available = [p.stem for p in PROMPT_DIR.glob("*.md")]
        raise FileNotFoundError(
            f"프롬프트 파일이 없습니다: {prompt_path}\n"
            f"사용 가능한 타겟: {', '.join(available)}"
        )

    with open(prompt_path, encoding="utf-8") as f:
        template = f.read()

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
        if d.get("history"):
            entry["history_count"] = len(d["history"])
        result.append(entry)
    return result


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
) -> dict:
    print(f"\n{'─'*60}")
    print(f"  커밋: {commit['hash'][:12]} | {commit['subject'][:60]}")
    print(f"  날짜: {commit['date']} | 작성자: {commit['author']}")

    # diff 추출 (전역 제외 적용)
    diff = get_diff(repo, commit["hash"])
    if not diff.strip():
        print("  → diff 없음, 건너뜀")
        return decisions_data

    # 타겟 필터 적용
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
    # commit["date"] 형식: "2026-03-15 14:30:00 +0900" → 날짜만 추출
    commit_date = commit["date"].split(" ")[0] if commit.get("date") else ""
    decisions_data = apply_operations(decisions_data, operations, today, commit_date)
    print(f"  ✓ decisions 총 {len(decisions_data.get('decisions', []))}개")

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

    parser.add_argument("--repo", required=True, help="분석할 git 레포지터리 경로")
    parser.add_argument(
        "--target",
        required=True,
        choices=["implementation", "design", "planning"],
        help="ADR 타겟 도메인",
    )
    parser.add_argument("--output", required=True, help="decisions.json 저장 디렉터리")

    # LLM 설정
    llm_group = parser.add_mutually_exclusive_group(required=True)
    llm_group.add_argument("--api-base", help="OpenAI-compatible API base URL")
    llm_group.add_argument("--llm-cmd", help="커스텀 LLM CLI 커맨드 (stdin으로 프롬프트 주입)")

    parser.add_argument("--api-key", help="API 키 (또는 OPENAI_API_KEY 환경변수)")
    parser.add_argument("--model", default="gpt-4o", help="모델명 (기본: gpt-4o)")

    # 필터 옵션
    parser.add_argument(
        "--skip-repo-scan",
        action="store_true",
        help="레포 구조 LLM 스캔 생략 (기본 필터 또는 기존 .adr-filters.yaml 사용)",
    )
    parser.add_argument(
        "--filters-file",
        help="사용할 필터 파일 경로 (기본: <repo>/.adr-filters.yaml)",
    )

    # 동작 옵션
    parser.add_argument("--resume", action="store_true", help="마지막 처리 커밋부터 재개")
    parser.add_argument("--limit", type=int, help="처리할 최대 커밋 수 (테스트용)")
    parser.add_argument("--max-diff", type=int, default=DEFAULT_MAX_DIFF, help=f"diff 최대 문자 수 (기본: {DEFAULT_MAX_DIFF})")
    parser.add_argument("--context-lines", type=int, default=DEFAULT_CONTEXT_LINES, help=f"git diff context lines (기본: {DEFAULT_CONTEXT_LINES})")
    parser.add_argument("--dry-run", action="store_true", help="LLM 호출 없이 diff만 추출 (테스트)")
    parser.add_argument("--verbose", "-v", action="store_true", help="상세 출력")
    parser.add_argument("--from-commit", help="이 커밋 해시 이후부터 처리")
    parser.add_argument("--save-every", type=int, default=1, help="N개 커밋마다 저장 (기본: 1)")

    args = parser.parse_args()

    output_dir = Path(args.output).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    # LLM caller 설정
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

    # 레포 확인
    repo = str(Path(args.repo).expanduser().resolve())
    try:
        head = git(repo, "rev-parse", "HEAD")
        print(f"레포: {repo} (HEAD: {head[:12]})")
    except subprocess.CalledProcessError:
        print(f"오류: git 레포지터리를 찾을 수 없습니다: {repo}", file=sys.stderr)
        sys.exit(1)

    # ── 필터 준비 ──────────────────────────────
    repo_filters_path = Path(repo) / FILTERS_FILENAME
    filters_exist = repo_filters_path.exists() or bool(args.filters_file)

    if not args.skip_repo_scan and not filters_exist and not args.dry_run:
        # 레포 구조 스캔 + LLM 필터 생성
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
        include_count = len(filters.get("include", []))
        exclude_count = len(filters.get("exclude", []))
        print(f"[필터] target={args.target} | include={include_count}개 | exclude={exclude_count}개")
    else:
        print(f"[필터] target={args.target} | 필터 없음 (전체 허용)")

    # ── 커밋 처리 준비 ─────────────────────────
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

    # ── 커밋 순회 ──────────────────────────────
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
