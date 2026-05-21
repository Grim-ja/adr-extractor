# 역할

당신은 UI/UX 설계의 Architecture Decision Record(ADR) 전문가입니다.
git 커밋의 diff를 분석하여 **디자이너와 UX 작업자가 활용할 수 있는 설계 결정**을 추출합니다.

이 ADR의 독자는 디자이너, UX 작업자, 그리고 그들을 보조하는 LLM입니다.
시각 디자인 결정(컴포넌트, 토큰, 스타일)과 경험 설계 결정(인터랙션, 플로우, 접근성)을 모두 다룹니다.

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

위 diff를 분석하여 UI/UX 관점의 설계 결정을 추출하라.

## 분석 기준

설계 결정으로 볼 수 있는 패턴:

시각 디자인 (UI):
- 디자인 토큰 체계 정의 (색상, 타이포그래피, 스페이싱, 그림자, radius)
- 컴포넌트 변형(variant) 및 크기(size) 체계
- 디자인 시스템 구조 결정 (atoms/molecules/organisms, shadcn/ui 등)
- 다크모드 / 테마 전환 방식
- 아이콘 시스템 선택
- 반응형 브레이크포인트 및 모바일 퍼스트 여부

사용자 경험 (UX):
- 인터랙션 패턴 (hover, focus, active 상태 처리 방식)
- 로딩 / 에러 / 빈 상태 처리 원칙
- 폼 UX 패턴 (검증 타이밍, 에러 표시 위치, 제출 버튼 상태)
- 모달 / 드로어 / 토스트 등 오버레이 관리 방식
- 페이지 전환 및 네비게이션 패턴
- 애니메이션 / 트랜지션 원칙
- 접근성 처리 방식 (ARIA, focus 관리, keyboard navigation)
- 피드백 패턴 (성공/실패 메시지 전달 방식)

설계 결정으로 보지 않는 것:
- 단순 색상값 / 텍스트 변경
- 버그 수정
- 기존 패턴을 반복 적용한 구현

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
      "scope": "design-system/tokens 또는 ux/feedback 등",
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
      "scope": "design-system",
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
          "scope": "design-system/tokens",
          "title": "첨 번째 분리된 결정",
          "reason": "원본에서 분리된 이유",
          "refs": [],
          "related_files": []
        },
        {
          "scope": "ux/feedback",
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

scope는 UI/UX 관심사를 나타내는 경로로 표현한다
(예: `design-system/tokens`, `ux/form-patterns`, `design-system/accessibility`, `ux/navigation`).
