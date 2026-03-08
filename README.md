# Agent Engineer Skills

`agent-engineer` 스킬을 GitHub 저장소로 배포하는 레포다.

## Install

GitHub URL에서 직접 설치:

```bash
npx skills add https://github.com/BEOKS/agent-engineer.git --skill agent-engineer
```

로컬 체크아웃에서 설치:

```bash
npx skills add . --skill agent-engineer
```

Claude Code에만 설치:

```bash
npx skills add https://github.com/BEOKS/agent-engineer.git --skill agent-engineer --agent claude-code
```

## Layout

- `skills/agent-engineer/`: 배포 대상 스킬
- `scripts/validate_repo.py`: 레포 구조와 스킬 메타데이터 검증
- `scripts/smoke_test.py`: 승인 게이트와 드라이런 오케스트레이션 스모크 테스트
- `.github/workflows/ci.yml`: 로컬 설치와 원격 설치까지 검증하는 CI/CD 파이프라인

## Deployment Model

- `main` 브랜치가 배포 소스다.
- `skills/<skill-name>/SKILL.md` 구조를 유지하면 `npx skills add <repo> --skill <skill-name>`로 설치할 수 있다.
- GitHub Actions는 푸시/PR마다 레포 구조, 파이썬 스크립트, 드라이런 오케스트레이션, `skills` CLI 설치를 검증한다.
- `main` 푸시에서는 공개 GitHub URL 기준 설치도 다시 검증한다.
