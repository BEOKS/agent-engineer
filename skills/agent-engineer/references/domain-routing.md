# Domain Routing

## Coding
- 권장 패턴: `task-decomposition`, `validation-loop`, `state-externalization`
- 자주 쓰는 역할: planner, implementer, reviewer
- 권장 검증: 테스트, 린트, 타입체크, 빌드
- 파일 scope: 패키지, 모듈, 테스트 디렉터리 중심

## Research
- 권장 패턴: `task-decomposition`, `context-isolation`, `central-orchestration`
- 자주 쓰는 역할: researcher, synthesizer, reviewer
- 권장 검증: 출처 점검, 날짜 검증, 주장-근거 매핑
- 파일 scope: 메모, 보고서, 출처 목록

## DOCX / PPTX / XLSX
- 권장 패턴: `role-decomposition`, `context-isolation`, `validation-loop`
- 자주 쓰는 역할: analyst, editor, formatter, reviewer
- 권장 검증: 형식 보존, 필드 누락 점검, 산출물 열기 가능 여부
- 파일 scope: 원본 문서, 변환 스크립트, 결과 문서

## Operations Analysis
- 권장 패턴: `task-decomposition`, `parallel-execution`, `central-orchestration`
- 자주 쓰는 역할: analyst, data-worker, reporter
- 권장 검증: 계산 재현, 표본 점검, 요약 일관성
- 파일 scope: 쿼리, CSV/XLSX, 분석 노트, 리포트

## 혼합 작업
- 여러 도메인이 섞이면 `hybrid`를 기본값으로 고려하라.
- 리서치와 구현이 섞이면 researcher와 implementer를 분리하라.
- 문서 산출물이 최종 결과이면 formatter 또는 reviewer를 별도 역할로 두라.
