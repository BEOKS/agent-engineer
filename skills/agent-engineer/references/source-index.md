# Source Index

## 필수 파일

- `SKILL.md`
- `agents/openai.yaml`
- `scripts/agent_state.py`
- `scripts/verify_store.py`
- `scripts/render_architecture.py`
- `scripts/build_runner.py`
- `scripts/run_architecture.py`
- `scripts/invoke_agent.py`

## 저장 경로

- 아키텍처: `.codex/agent-engineer/architecture.md`
- 이벤트 로그: `.codex/agent-engineer/store/events.jsonl`
- 스냅샷: `.codex/agent-engineer/store/snapshot.json`
- 러너: `.codex/agent-engineer/runs/<run-id>/`

## 읽기 우선순위

1. `SKILL.md`
2. 현재 작업의 `.codex/agent-engineer/architecture.md`
3. 필요 시 `references/architecture-selection.md`
4. 필요 시 `references/domain-routing.md`
5. 구현 또는 디버깅 시 `scripts/*.py`

## 빠른 검색 패턴

- 아키텍처 JSON 블록 찾기: ```` ```json ````
- 승인 상태 찾기: `approval_status`
- 실행 정책 찾기: `retry_policy|validation_policy|delegation_policy`
- 상태 무결성 디버깅: `hash`, `prev_hash`, `snapshot`
