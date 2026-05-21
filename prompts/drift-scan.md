# 역할

당신은 Architecture Decision Record(ADR)의 boundary drift를 감지하는 전문가입니다.
아래는 divergence score가 임계값을 초과한 decisions 목록입니다.
각 decision의 history를 분석하여, 하나의 decision에 서로 다른 클러스터의 내용이 섞여 있는지 판단하세요.

# Drift 후보 Decisions

```json
{{DRIFT_CANDIDATES}}
```

# 지시사항

각 decision의 `history`를 순서대로 읽으면서 아래를 판단하세요:

## 판단 기준

**split이 필요한 경우:**
- history 항목들이 명확히 두 개 이상의 서로 다른 관심사(concern)를 다루고 있다
- 각 클러스터가 독립적으로 의미를 가지며, 분리해도 맥락이 유지된다
- 현재 title/scope가 일부 history 항목과 맞지 않는다

**split이 불필요한 경우:**
- history 항목들이 같은 주제의 보강/심화다
- 변화가 있더라도 하나의 결정으로 볼 수 있는 범위다
- 분리하면 오히려 맥락이 파편화된다

**원칙: 불명확하면 split하지 않는다.**

## 출력 형식

다음 JSON을 **반드시 ```json ... ``` 코드블록으로** 반환하라.

split이 필요한 decision만 operations에 포함한다.
split이 필요 없는 decision은 operations에 포함하지 않는다 (score는 코드에서 자동 감소).

```json
{
  "operations": [
    {
      "op": "split",
      "source_id": "d-007",
      "into": [
        {
          "scope": "첫 번째 클러스터의 scope",
          "title": "첫 번째 클러스터를 대표하는 제목 (40자 이내)",
          "reason": "이 클러스터의 핵심 결정 내용",
          "alternatives": [],
          "consequences": [],
          "refs": [],
          "related_files": ["이 클러스터와 관련된 파일들"]
        },
        {
          "scope": "두 번째 클러스터의 scope",
          "title": "두 번째 클러스터를 대표하는 제목 (40자 이내)",
          "reason": "이 클러스터의 핵심 결정 내용",
          "alternatives": [],
          "consequences": [],
          "refs": [],
          "related_files": ["이 클러스터와 관련된 파일들"]
        }
      ]
    }
  ]
}
```

split할 decision이 없으면:
```json
{
  "operations": []
}
```
