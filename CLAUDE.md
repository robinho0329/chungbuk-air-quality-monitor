# 충북 대기질 모니터링 프로젝트 지침

## 작업 권한

- 이 레포의 `main` 브랜치에 대한 `git push`는 확인 없이 바로 실행한다
- GitHub Actions 워크플로우 수동 트리거도 확인 없이 바로 실행한다
- 파일 생성·수정·삭제도 확인 없이 바로 실행한다

## 프로젝트 구조

- `src/` — 수집·분석·저장 로직
- `dashboard/pages/` — Streamlit 멀티페이지 (현재 7페이지)
- `scripts/` — 1회 실행 스크립트
- `flows/` — Prefect/GHA 플로우
- `.github/workflows/` — GitHub Actions

## 자동화 현황

- 매시 에어코리아 + 기상청 ASOS 자동 수집 (GitHub Actions)
- 매시 SPC 이상 탐지 → Discord 알림
- 매일 포트폴리오 PPT 자동 생성
