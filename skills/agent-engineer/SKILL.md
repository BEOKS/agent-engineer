---
name: agent-engineer
description: 패턴 조합형 에이전트 아키텍처를 설계하고 승인 후 실행하도록 오케스트레이션한다. Use when Codex must coordinate coding, research, docx/pptx/xlsx document work, or operations analysis through task decomposition, role decomposition, context isolation, state externalization, validation loops, parallel execution, and central orchestration with an explicit approval gate.
---

# Agent Engineer

승인 게이트(approval gate)가 있는 메타 오케스트레이터로 동작하라. 작업별 세션 정보와 요청 정보는 기본 에이전트가 관리한다고 가정하고, 이 스킬은 패턴 선택, 아키텍처 문서화, 상태 저장, 검증, 실행 러너 생성만 담당하라.

## Core Workflow

1. 요청을 해석하고 부족한 사실만 추가로 확인하라.
2. 아래 참조 문서 중 필요한 것만 읽어 패턴 조합을 결정하라.
   - `references/pattern-catalog.md`
   - `references/architecture-selection.md`
   - `references/domain-routing.md`
   - `references/source-index.md`
3. `command -v codex`, `command -v claude`, `command -v opencode`로 설치 여부를 확인하라.
4. 현재 작업 디렉터리의 `.codex/agent-engineer/architecture.md`에 승인안을 작성하라.
5. `scripts/render_architecture.py`로 Mermaid와 승인 요약표를 렌더링하라.
6. 사용자에게 승인안을 제시하라.
7. 명시적 승인 전에는 실행 스크립트를 만들거나 실행하지 말라.
8. 승인 후 `scripts/build_runner.py`로 러너를 생성하라.
9. 승인 후 `scripts/run_architecture.py`로 러너를 실행하라.

## Non-Negotiables

- 세션 정보와 요청 전문을 별도 저장하지 말라.
- 아키텍처는 반드시 `.codex/agent-engineer/architecture.md`에만 기록하라.
- 승인 전에는 `build_runner.py` 또는 `run_architecture.py`를 실행하지 말라.
- 상태 JSON은 직접 수정하지 말고 `scripts/agent_state.py`만 사용하라.
- 새로운 상태 조작 스크립트를 즉흥적으로 만들지 말라.
- 필요한 기능이 번들 스크립트에 없으면 승인 후 스킬 개정 작업으로 분리하라.

## Path Contract

- 아키텍처: `.codex/agent-engineer/architecture.md`
- 상태 저장소: `.codex/agent-engineer/store/`
- 상태 파일: `.codex/agent-engineer/store/events.jsonl`, `.codex/agent-engineer/store/snapshot.json`
- 실행 산출물: `.codex/agent-engineer/runs/<run-id>/`

## Architecture Authoring

`architecture.md`는 사람 승인용 단일 소스 오브 트루스(single source of truth)다. 문서 마지막에는 반드시 machine-readable JSON code fence를 두고, 실행 스크립트는 그 JSON 블록만 파싱한다고 가정하라.

승인안에는 반드시 아래를 포함하라.

- 선택된 기본 패턴과 조합 방식
- 단계별 실행 순서
- 각 단계 또는 역할별 사용 CLI
- 각 단계 또는 역할별 모델
- 병렬도
- 검증 정책
- 재시도 정책
- 위임 지점

JSON 블록은 아래 필드를 포함해야 한다.

- `version`
- `approval_status`
- `composition`
- `selected_patterns`
- `engines`
- `steps`
- `parallel_policy`
- `retry_policy`
- `validation_policy`
- `delegation_policy`

선택한 CLI가 설치되지 않았으면 `render_architecture.py` 출력에 경고를 표시하라. 현재 환경에서는 `codex`와 `claude`가 보통 후보이고, `opencode`는 설치된 경우에만 선택하라.

## Execution Discipline

승인 후 러너는 아래 불변식을 강제해야 한다.

- 상태 변경은 `agent_state.py`로만 수행한다.
- 각 단계 시작 전후로 `verify_store.py`를 호출한다.
- 검증이 통과하기 전에는 어떤 작업도 `done`으로 전이하지 않는다.
- `retry_policy.max_attempts`를 초과하면 `blocked`로 전이하고 사용자 개입을 요청한다.
- 병렬 작업은 scope 충돌이 없을 때만 시작한다.
- 승인안에 없는 CLI 또는 모델 조합은 `invoke_agent.py`가 거부한다.

## Script Map

- `scripts/agent_state.py`
  - 상태 저장소의 유일한 CRUD 진입점
- `scripts/verify_store.py`
  - 이벤트 해시 체인, 스냅샷 재생성, enum, 참조 무결성, 승인 게이트, 완료 전이 규칙을 검증
- `scripts/render_architecture.py`
  - 승인용 Mermaid와 요약표를 생성
- `scripts/build_runner.py`
  - 승인된 아키텍처에서 러너 디렉터리를 생성
- `scripts/run_architecture.py`
  - 생성된 러너를 실행하고 각 단계 전후에 저장소를 검증
- `scripts/invoke_agent.py`
  - 승인된 CLI와 모델 조합만 사용해 `codex exec`, `claude -p`, `opencode` 호출을 표준화

## Domain Notes

코딩, 리서치, 문서 작업, 운영 분석은 모두 같은 저장 구조를 쓰되 라우팅만 다르게 잡아라. 도메인별 권장 패턴, 워커 역할, 검증 방식은 `references/domain-routing.md`만 읽어 결정하라. 패턴 선택 기준은 `references/architecture-selection.md`를 우선하라.

## Minimal Operating Procedure

아키텍처 초안을 만들 때는 다음 순서를 따르라.

1. 작업 성격을 분류하라.
2. 필요한 패턴만 고르라.
3. CLI와 모델을 단계별로 배정하라.
4. 병렬도와 재시도 정책을 정하라.
5. 검증 명령 또는 검증 준비 방법을 명시하라.
6. `render_architecture.py` 결과를 확인한 뒤 승인 요청을 하라.

실행할 때는 다음 순서를 따르라.

1. `verify_store.py` 통과 여부를 확인하라.
2. 승인 상태가 `approved`인지 확인하라.
3. `build_runner.py`로 러너를 생성하라.
4. 검증 명령을 준비한 뒤 `run_architecture.py`를 실행하라.
5. 실패한 작업은 승인된 정책으로만 재시도하라.
