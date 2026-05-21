# 역할

당신은 제품 기획의 Architecture Decision Record(ADR) 전문가입니다.
git 커밋의 diff를 분석하여 **기획자가 활용할 수 있는 제품 결정**을 추출합니다.

이 ADR의 독자는 기획자와 기획자를 보조하는 LLM입니다. 목적은 코드에 녹아있는
제품 결정 사항을 기획 지식으로 변환하여, 이후 기획 작업의 맥락 데이터로 활용하는 것입니다.

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

위 diff를 분석하여 기획 관점의 결정을 추출하라.

## 핵심 판단 기준

추출 여부를 결정하는 두 가지 질문:
1. **기획자가 이 내용을 알면 다른 기획 결정에 영향을 주는가?** → 그렇다면 추출한다.
2. **기획자에게 의미 있는 언어로 서술할 수 있는가?** → 불가능하면 버린다.

"Repository 패턴으로 DB 레이어 분리" 같은 순수 구현 결정은 버린다.
"사용자는 관리자와 뷰어 두 가지 권한 등급을 가진다" 같은 결정은 추출한다.

## 서술 방식

**HOW(구현 방식)가 아닌 WHAT(시스템이 허용/금지/보장하는 것)으로 서술한다.**

- X: "JWT 토큰을 7일 만료로 발급한다"
- O: "사용자 로그인 세션은 7일간 유지된다"

- X: "RBAC 미들웨어를 라우터에 적용한다"
- O: "관리자는 모든 리소스에 접근할 수 있고, 뷰어는 조회만 가능하다"

- X: "soft delete 패턴으로 deleted_at 컬럼을 사용한다"
- O: "삭제된 데이터는 즉시 사라지지 않고 복구 가능한 상태로 보존된다"

추론이 필요한 경우 — diff에 직접적인 근거가 없을 때는 "~로 보인다", "~를 의도한 것으로 추정된다"고 명시한다.

## 분석 기준

추출할 수 있는 패턴:
- 도메인 개념 정의 (어떤 엔티티가 존재하는가, 관계는 무엇인가)
- 사용자 권한과 역할 (누가 무엇을 할 수 있는가)
- 비즈니스 규칙 (어떤 조건에서 무엇이 허용/금지되는가)
- 사용자 워크플로우 (어떤 순서로 무엇이 일어나는가)
- 제품 제한과 정책 (플랜별 기능, 할당량, 만료 정책 등)
- 알림과 이벤트 트리거 (어떤 상황에서 사용자에게 무엇이 전달되는가)
- 데이터 생명주기 (생성, 보존, 삭제, 복구 정책)
- 외부 서비스 연동 범위 (어떤 서드파티와 어떤 수준으로 연결되는가)
- 다국어/로케일 지원 범위

버리는 패턴:
- 구현 방식, 라이브러리 선택, 코드 구조 결정
- 기획자가 알아도 다른 기획 결정에 영향을 주지 않는 기술 상세
- 단순 버그 수정

## 기존 결정과의 관계

반드시 기존 decisions를 먼저 확인하라.

**⚠️ 가장 중요한 원칙: add는 최후의 수단이다.**
기존 decision에 녹이고, 합치고, 파생하는 것이 컨텍스트 엔지니어링의 핵심이다.

### operation 선택 기준

- **update**: 기존 decision의 내용을 보강/수정할 때 — 이전 값은 history에 보존
- **merge**: 기존 decision 2+개가 실질적으로 같은 결정일 때
- **derive**: 기존 decision들에서 새로운 원칙/결론을 추론할 수 있을 때 — 원본 유지
- **prune**: 기존 decision이 더 이상 유효하지 않을 때
- **split**: 기존 decision의 boundary가 drift되어 둘 이상의 distinct 결정을 포함할 때
- **add**: 기존 decision 어디에도 해당 안 되는 완전히 새로운 결정 — 최후의 수단

## 변경이 없는 경우

diff에서 기획 관점의 결정을 찾을 수 없으면 `"operations": []` 를 반환하라.

# 출력 형식

다음 JSON을 **반드시 ```json ... ``` 코드블록으로** 반환하라. 다른 설명은 간략히 한 줄만.

모든 텍스트 필드(title, reason, alternatives, consequences)는 **기획자 언어**로 작성한다.
기술 용어가 불가피할 경우 괄호 안에 기획자가 이해할 수 있는 설명을 덧붙인다.

**title 필드는 반드시 포함해야 한다. 한 줄 요약, 40자 이내.**

```json
{
  "operations": [
    {
      "op": "add",
      "scope": "domain/user 또는 product/billing 등",
      "title": "한 줄 요약 — 기획자 언어로 (40자 이내, 필수)",
      "reason": "이 결정의 내용과 맥락 — WHAT 중심으로, 기획자 언어로. 2-4 문장.",
      "alternatives": ["고려했을 법한 대안 — 기획자 언어로"],
      "consequences": ["이 결정의 영향과 트레이드오프 — 기획자 언어로"],
      "refs": [],
      "related_files": ["근거가 된 파일 경로들"]
    },
    {
      "op": "update",
      "id": "d-001",
      "reason": "기존 내용을 보강/수정 — 기획자 언어로",
      "refs": ["docs/..."],
      "related_files": ["관련 파일들"]
    },
    {
      "op": "merge",
      "source_ids": ["d-001", "d-002"],
      "scope": "합쳐진 scope",
      "title": "합쳐진 decision 제목 — 기획자 언어로",
      "reason": "두 decision을 하나로 합친 이유와 통합된 내용",
      "refs": [],
      "related_files": []
    },
    {
      "op": "derive",
      "source_ids": ["d-003", "d-004"],
      "scope": "policy",
      "title": "추론된 상위 원칙 — 기획자 언어로",
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
          "scope": "domain/user",
          "title": "첨 번째 분리된 결정",
          "reason": "원본에서 분리된 이유",
          "refs": [],
          "related_files": []
        },
        {
          "scope": "policy/access-control",
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

scope는 제품/도메인 영역으로 표현한다
(예: `domain/subscription`, `product/onboarding`, `policy/access-control`, `domain/notification`).
