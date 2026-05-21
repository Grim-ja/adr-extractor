# git-adr

git 히스토리를 initial commit부터 순회하며 Architecture Decision Records(ADR)를
누적 생성하는 도구.

## 개요

커밋 하나씩 `git diff`를 추출하고 LLM에 분석을 맡겨, 설계 결정을 `decisions.json`에 쌓아간다.
기존 ADR 시스템(`decisions.sh`, `update-decisions.sh`)과 동일한 데이터 포맷을 사용하므로
생성된 `decisions.json`을 기존 도구로 바로 쿼리할 수 있다.

## 파일 구조

```
adr/
  git-adr.py              - 메인 스크립트
  decisions.sh            - decisions.json 쿼리 도구 (기존)
  update-decisions.sh     - plan_output.json 반영 도구 (기존)
  prompts/
    impl-backend.md       - 백엔드 구현 결정 분석 프롬프트
    impl-frontend.md      - 프론트엔드 구현 결정 분석 프롬프트
    ui.md                 - UI/UX 결정 분석 프롬프트
    planning.md           - 기획/제품 결정 분석 프롬프트
    architecture.md       - 전체 아키텍처 결정 분석 프롬프트
```

## 사용법

### 기본 실행 (OpenAI-compatible API)

```bash
python git-adr.py \
  --repo /path/to/your/repo \
  --target impl-backend \
  --output ./my-project-adr/ \
  --api-base https://api.openai.com/v1 \
  --api-key $OPENAI_API_KEY \
  --model gpt-4o
```

### 커스텀 LLM CLI 사용

프롬프트를 stdin으로 받아 결과를 stdout으로 출력하는 어떤 CLI든 사용 가능.

```bash
python git-adr.py \
  --repo /path/to/your/repo \
  --target architecture \
  --output ./adr-output/ \
  --llm-cmd "hermes run --no-stream"
```

### 이어서 실행 (--resume)

중단된 경우 마지막 처리된 커밋 이후부터 재개:

```bash
python git-adr.py \
  --repo /path/to/your/repo \
  --target impl-backend \
  --output ./my-project-adr/ \
  --api-base https://api.openai.com/v1 \
  --api-key $OPENAI_API_KEY \
  --resume
```

### 특정 커밋 이후부터

```bash
python git-adr.py \
  --repo /path/to/your/repo \
  --target ui \
  --output ./adr-output/ \
  --api-base https://api.openai.com/v1 \
  --api-key $OPENAI_API_KEY \
  --from-commit abc1234def
```

### Dry-run (LLM 호출 없이 diff만 확인)

```bash
python git-adr.py \
  --repo /path/to/your/repo \
  --target planning \
  --output ./test-adr/ \
  --api-base https://api.openai.com/v1 \
  --api-key dummy \
  --dry-run \
  --limit 5 \
  --verbose
```

## 타겟 종류

| 타겟 | 분석 관점 | 적합한 경우 |
|------|-----------|-------------|
| `implementation` | 백엔드/프론트엔드/아키텍처를 통합한 구현 결정 | 대부분의 레포 |
| `design` | UI/UX — 디자인 시스템, 인터랙션, 접근성 등 | 디자인 시스템 / UI 컴포넌트 레포 |
| `planning` | 도메인 모델, 비즈니스 규칙, 권한 등 | 기획 결정 중심 분석 |

하나의 레포에 여러 타겟을 별도 output 디렉터리에 동시 실행할 수 있다:

```bash
python git-adr.py --repo . --target implementation --output ./adr/impl/ ...
python git-adr.py --repo . --target design --output ./adr/design/ ...
```

## 옵션 전체 목록

```
필수:
  --repo PATH           분석할 git 레포지터리 경로
  --target TARGET       ADR 타겟 (impl-backend/impl-frontend/ui/planning/architecture)
  --output DIR          decisions.json 저장 디렉터리

LLM (둘 중 하나 필수):
  --api-base URL        OpenAI-compatible API base URL
  --llm-cmd CMD         커스텀 LLM CLI (stdin 프롬프트 → stdout 결과)

API 옵션:
  --api-key KEY         API 키 (또는 OPENAI_API_KEY 환경변수)
  --model MODEL         모델명 (기본: gpt-4o)

동작 제어:
  --resume              마지막 처리 커밋부터 재개
  --from-commit HASH    이 커밋 이후부터 처리
  --limit N             처리할 최대 커밋 수 (테스트용)
  --max-diff N          diff 최대 문자 수 (기본: 12000)
  --context-lines N     git diff context lines (기본: 5)
  --save-every N        N개 커밋마다 저장 (기본: 1)
  --dry-run             LLM 호출 없이 diff만 추출
  --verbose, -v         상세 출력
```

## 출력 파일

| 파일 | 설명 |
|------|------|
| `decisions.json` | 누적된 ADR 데이터 (decisions.sh로 쿼리 가능) |
| `.adr-state.json` | 진행 상태 (last_processed_hash, processed_count) |

## decisions.json 쿼리

생성된 `decisions.json`은 기존 `decisions.sh` 도구로 쿼리할 수 있다:

```bash
# 전체 canonical 목록
DECISIONS_FILE=./my-project-adr/decisions.json ./decisions.sh --canonical

# 특정 결정 상세
DECISIONS_FILE=./my-project-adr/decisions.json ./decisions.sh --id d-001 --evidence

# 특정 파일 관련 결정
DECISIONS_FILE=./my-project-adr/decisions.json ./decisions.sh --file src/api/users.ts

# 범위별 조회
DECISIONS_FILE=./my-project-adr/decisions.json ./decisions.sh --scope architecture
```

## 동작 원리

1. `git log --reverse`로 initial commit부터 커밋 목록 수집
2. `--resume` 시 `.adr-state.json`에서 마지막 처리 커밋 이후부터 시작
3. 각 커밋에 대해:
   - `git diff`로 변경사항 추출 (lock 파일, node_modules 등 자동 제외)
   - diff 크기 초과 시 파일별 균등 분배 후 truncate
   - 기존 decisions 요약 + diff → 타겟 프롬프트로 LLM 호출
   - LLM 응답에서 `operations` JSON 파싱
   - `add/update/merge/derive/prune/split` 연산을 `decisions.json`에 적용
4. 매 커밋(또는 `--save-every N`)마다 저장 (중단해도 데이터 보존)

## decisions.json 포맷

```json
{
  "decisions": [
    {
      "id": "d-001",
      "status": "active",
      "date": "2024-01-15",
      "scope": "src/api/auth",
      "title": "JWT 기반 stateless 인증 채택",
      "reason": "세션 서버 없이 수평 확장이 필요했다. ...",
      "alternatives": ["세션 기반 인증", "OAuth only"],
      "consequences": ["토큰 무효화 복잡성 증가"],
      "refs": [],
      "related_files": ["src/api/auth/jwt.ts"],
      "derived_from": null,
      "history": []
    }
  ]
}
```
