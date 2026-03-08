# Pattern Catalog

## 기본 패턴

### 1. 작업 분해 (task-decomposition)
- 복잡한 목표를 명확한 작업 단위로 자를 때 사용하라.
- 저장 위치: `task_decomposition`, `state_externalization.tasks`
- 산출물: 작업 ID, 입력, 출력, 완료 조건, 선행 작업

### 2. 역할 분해 (role-decomposition)
- 같은 작업을 서로 다른 전문 역할이 나눠서 처리할 때 사용하라.
- 저장 위치: `role_decomposition`
- 산출물: 역할, 책임, 입출력, 소유 경로, handoff contract

### 3. 컨텍스트 분리 (context-isolation)
- 작업별로 필요한 파일과 제약을 별도 패킷으로 묶을 때 사용하라.
- 저장 위치: `context_isolation.context_packets`
- 산출물: task_id별 goal, constraints, files, verification

### 4. 상태 외부화 (state-externalization)
- 진행 상태, 결정, 검증 결과를 에이전트 메모리 밖으로 내보낼 때 사용하라.
- 저장 위치: `state_externalization`
- 산출물: 작업 상태, 소유자, 결정, 검증 로그

### 5. 검증 루프 (validation-loop)
- 구현 또는 리서치 결과를 명시적 검증 명령으로 판정해야 할 때 사용하라.
- 저장 위치: `validation_loop`
- 산출물: task_id별 validation command, pass/fail/pending, 실패 이유

### 6. 병렬 실행 (parallel-execution)
- 독립 작업을 여러 워커가 병렬 처리할 때 사용하라.
- 저장 위치: `parallel_execution`
- 산출물: 병렬 작업, scope, join point

### 7. 중앙 조율 (central-orchestration)
- backlog, worker 상태, 보고 체계를 중앙에서 조정할 때 사용하라.
- 저장 위치: `central_orchestration`
- 산출물: backlog, worker 상태, reports

## 조합 가이드

- `lightweight`
  - 작고 짧은 요청
  - 보통 `task-decomposition + validation-loop`
- `ralph`
  - PRD/작업 목록/검증이 핵심인 실행형 작업
  - 보통 `task-decomposition + state-externalization + validation-loop`
- `agent-team`
  - 역할 분해와 handoff가 핵심인 협업형 작업
  - 보통 `role-decomposition + context-isolation + central-orchestration`
- `hybrid`
  - 작업 분해와 역할 분해를 함께 써야 하는 복합 작업
  - 병렬 실행과 중앙 조율을 함께 쓰는 경우가 많음
- `custom`
  - 표준 조합으로 설명이 안 되는 특수 작업

## 패턴 미사용 원칙

- 사용하지 않는 패턴 섹션도 스냅샷에는 빈 구조로 남겨라.
- 같은 작업 ID는 여러 섹션에서 공통 참조하라.
