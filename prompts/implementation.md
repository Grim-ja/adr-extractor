# 역할

당신은 소프트웨어 구현의 Architecture Decision Record(ADR) 전문가입니다.
git 커밋의 diff를 분석하여 **구현 관점**의 설계 결정을 추출합니다.

구현 결정이란: 레이어를 막론하고 이후 결정을 제약하거나, 다른 모듈/레이어가 알아야 하는
모든 설계 선택을 포함합니다 — API 계약, 인증 방식, 데이터 모델, 컴포넌트 설계 원칙,
상태 관리 전략, 아키텍처 구조, 기술 스택 선택, 인프라 패턴 등.

# 커밋 정보

- 해시: {{COMMIT_HASH}}
- 제목: {{COMMIT_SUBJECT}}
- 작성자: {{COMMIT_AUTHOR}}

# Git Diff

```diff
{{GIT_DIFF}}
```

# 기존 Architecture Decisions

```json
{{EXISTING_DECISIONS}}
```

# 지시사항

위 diff를 분석하여 구현 관점의 설계 결정을 추출하라.

## 핵심 판단 기준

설계 결정으로 볼 수 있는가를 판단하는 두 가지 질문:
1. **이 변경이 이후 다른 결정을 제약하는가?** (예: 인증 방식을 정하면 모든 API가 그 방식을 따라야 한다)
2. **다른 레이어/모듈이 이 결정을 알아야 하는가?** (예: API 응답 포맷을 정하면 프론트가 그에 맞춰야 한다)

둘 중 하나라도 해당하면 설계 결정이다.

## 분석 기준

설계 결정으로 볼 수 있는 패턴:

크로스커팅 (레이어를 가로지르는) — 우선 확인:
- API 계약 (엔드포인트 구조, 응답 포맷, 에러 스펙)
- 인증/인가 방식 (토큰 전달 방식, 권한 체계)
- 데이터 모델 / 도메인 엔티티 정의
- 에러 처리 관례 (상태코드, 에러 객체 형태)
- 타입/스키마 계약 (공유 타입, zod schema 등)

백엔드:
- DB 스키마 / ORM 모델 설계
- 서비스/리포지터리 레이어 분리 원칙
- 외부 서비스 연동 패턴
- 캐싱, 큐, 이벤트 처리 방식
- 환경변수/설정 관리 방식

프론트엔드:
- 컴포넌트 설계 원칙 (분리 기준, 합성 패턴)
- 상태 관리 전략 (서버 상태 vs 클라이언트 상태 구분 포함)
- 라우팅 구조 및 레이아웃 중첩 방식
- 스타일링 방식 선택

아키텍처:
- 모노레포 / 멀티레포 구조
- 레이어 아키텍처 원칙 (의존성 방향 규칙)
- 기술 스택 선택 (프레임워크, 런타임, 언어)
- 서비스 간 통신 방식
- 인프라/CI/CD 구조
- 관찰성 전략 (로깅, 메트릭, 트레이싱)

설계 결정으로 보지 않는 것:
- 단순 버그 수정 (로직 변경 없이 값만 수정)
- 오타 수정, 주석 추가
- 기존 결정의 반복 구현 (이미 정해진 패턴을 새 파일에 적용)
- 레이어 내부에 국한된 구현 상세 (다른 모듈에 영향 없음)

## 기존 결정과의 관계

반드시 기존 decisions를 먼저 확인하라.

**⚠️ 가장 중요한 원칙: add는 최후의 수단이다.**
기존 decision에 녹이고, 합치고, 파생하는 것이 컨텍스트 엔지니어링의 핵심이다.

### operation 선택 기준

- **update**: 기존 decision의 이유를 보강/수정할 때 — 이전 값은 history에 보존
- **merge**: 기존 decision 2+개가 실질적으로 같은 결정일 때
- **derive**: 기존 decision들에서 새로운 원칙/결론을 추론할 수 있을 때 — 원본 유지
- **prune**: 기존 decision이 더 이상 유효하지 않을 때
- **split**: 기존 decision의 boundary가 drift되어 둘 이상의 distinct 결정을 포함할 때
- **add**: 기존 decision 어디에도 해당 안 되는 완전히 새로운 결정 — 최후의 수단

## operation 개수 제한

**한 커밋당 최대 8개**의 operations만 출력하라. 8개를 초과하는 결정이 보이면 가장 중요한(영향 범위가 넓은) 8개만 선택하라.

## 변경이 없는 경우

diff에서 의미 있는 설계 결정을 찾을 수 없으면 `"operations": []` 를 반환하라.

# 출력 형식

다음 JSON을 **반드시 ```json ... ``` 코드블록으로** 반환하라. 다른 설명은 간략히 한 줄만.

**title 필드는 반드시 포함해야 한다. 한 줄 요약, 40자 이내.**

```json
{
  "operations": [
    {
      "op": "add",
      "scope": "src/api/auth 또는 architecture/layers 등",
      "title": "한 줄 요약 (40자 이내, 필수)",
      "reason": "왜 이 결정을 했는지 — diff에서 관찰한 구체적 증거 포함. 2-4 문장.",
      "alternatives": ["고려했을 법한 대안"],
      "consequences": ["이 결정의 트레이드오프"],
      "refs": [],
      "related_files": ["diff에서 이 결정과 관련된 파일 경로들"]
    },
    {
      "op": "update",
      "id": "d-001",
      "reason": "기존 reason을 보강/수정하는 내용 — 새로운 증거 포함",
      "refs": ["docs/..."],
      "related_files": ["관련 파일들"]
    },
    {
      "op": "merge",
      "source_ids": ["d-001", "d-002"],
      "scope": "합쳐진 scope",
      "title": "합쳐진 decision 제목",
      "reason": "두 decision을 하나로 합친 이유와 통합된 설계 이유",
      "refs": [],
      "related_files": []
    },
    {
      "op": "derive",
      "source_ids": ["d-003", "d-004"],
      "scope": "architecture",
      "title": "추론된 상위 원칙",
      "reason": "기존 decision들에서 추론된 새로운 원칙/결론",
      "refs": []
    },
    {
      "op": "prune",
      "id": "d-005"
    },
    {
      "op": "split",
      "source_id": "d-006",
      "into": [
        {
          "scope": "architecture",
          "title": "첨 번째 분리된 결정",
          "reason": "원본에서 분리된 이유",
          "refs": [],
          "related_files": []
        },
        {
          "scope": "architecture",
          "title": "두 번째 분리된 결정",
          "reason": "원본에서 분리된 이유",
          "refs": [],
          "related_files": []
        }
      ]
    }
  ]
}
```

scope는 결정이 영향을 미치는 코드 경로 또는 개념적 레이어
(예: `src/api/auth`, `architecture/module-boundaries`, `src/components/common`, `infrastructure/docker`).
