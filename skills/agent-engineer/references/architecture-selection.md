# Architecture Selection

## 빠른 선택 규칙

### `lightweight`
- 조건: 작업 수가 적고 병렬 이득이 작다.
- 권장: 단일 planner 또는 worker
- 기본 정책: `max_workers=1`, 낮은 재시도 횟수

### `ralph`
- 조건: 결과물을 PRD/작업 보드/검증 루프로 관리하고 싶다.
- 권장: planner 1개 + worker 1~2개 + validation 엔진
- 기본 정책: 작업 분해를 먼저 확정하고 상태 외부화를 강하게 유지

### `agent-team`
- 조건: 리서치, 구현, 문서화처럼 역할별 handoff가 중요하다.
- 권장: lead + specialist worker 구조
- 기본 정책: 역할 소유 경로와 handoff contract를 먼저 명시

### `hybrid`
- 조건: 역할 분해와 작업 분해가 모두 중요하고 병렬도도 필요하다.
- 권장: planner, researcher, implementer, reviewer를 단계별로 배정
- 기본 정책: `parallel_execution`과 `central_orchestration`을 같이 설계

### `custom`
- 조건: 위 네 가지로 설명이 어려운 경우
- 기본 정책: 왜 표준 조합이 부족한지 명시하고 예외를 최소화

## 단계별 CLI/모델 선택 힌트

- `codex`
  - 코드베이스 탐색, 파일 편집, 로컬 검증 루프에 유리
- `claude`
  - 긴 문서 해석, 대안 비교, 구조화된 리서치에 유리
- `opencode`
  - 로컬 설치가 있을 때만 선택

각 단계마다 CLI와 모델을 분리해서 적어라. 한 문서 안에서 "engine_id -> cli -> model -> purpose"가 추적 가능해야 한다.

## 승인안 체크리스트

- 패턴 조합 이유가 적혀 있는가
- 단계 순서가 의존관계와 일치하는가
- 각 단계의 CLI와 모델이 비어 있지 않은가
- 병렬도와 join point가 적혀 있는가
- 검증 정책과 재시도 정책이 적혀 있는가
- 승인 전 실행 금지 원칙이 명시되어 있는가
