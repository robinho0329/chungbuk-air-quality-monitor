# Chungbuk Air Quality Monitor

충북권 산업단지 대기질 실시간 모니터링 시스템.
SPC(통계적 공정관리)와 Cp/Cpk 기반 이상 탐지를 자동화하는 QC/API 직무 포트폴리오.

자세한 프로젝트 배경은 [`README_PROJECT.md`](./README_PROJECT.md) 참조.

## 빠른 시작

### 1. 의존성 설치 (이미 완료된 경우 생략)

```bash
uv sync
```

### 2. 환경 변수 설정

```bash
cp .env.example .env
# .env 파일을 열어 AIRKOREA_API_KEY 입력
```

에어코리아 인증키는 [공공데이터포털](https://www.data.go.kr/data/15073861/openapi.do)에서
신청한다. **Decoding 키**(URL 디코딩된 평문)를 `AIRKOREA_API_KEY`에 넣는다.

### 3. 측정소 정보 확인 (1회성)

```bash
uv run python scripts/check_stations.py
```

대상 4개 측정소(오창읍, 복대동, 오송읍, 용암동)의 stationName과 좌표를 확인한다.
매칭이 안 되는 측정소가 있으면 `docs/stations.md`와 `src/config.py`를 갱신한다.

### 4. 1회 수집 실행

```bash
uv run python scripts/collect_once.py
```

성공 시 `src/storage/data.db`에 측정 데이터가 저장된다.

### 5. 저장 데이터 확인

```bash
uv run python -c "from src.storage.database import query_all; rows = query_all(); print(f'총 {len(rows)}건'); [print(r) for r in rows[:10]]"
```

## 프로젝트 구조

```
src/
├── config.py              # 환경 변수 로드/검증
├── collectors/
│   └── airkorea.py        # 에어코리아 OpenAPI 클라이언트
└── storage/
    ├── models.py          # SQLModel 스키마
    └── database.py        # DB 초기화·CRUD
scripts/
├── check_stations.py        # 측정소 정보 검증
├── collect_once.py          # 수집→저장 1회 실행
└── analyze_capability.py    # Cp/Cpk 분석 리포트
src/analysis/
├── usl_lsl.py               # 환경기준 USL/LSL 상수
└── capability.py            # 공정능력지수 계산
flows/
└── collect_flow.py          # Prefect 수집 워크플로우
docs/
├── stations.md              # 측정소 정의 문서
└── PHASE2_HANDOFF.md        # Phase 2 진입 메모
.claude/agents/              # 서브에이전트 정의 5종
```

## Prefect 스케줄링으로 데이터 자동 누적

**1회 실행 (디버깅용)**:
```bash
uv run python flows/collect_flow.py
```

**자동 수집 옵션 비교**:

| 방식 | 컴퓨터 꺼져도? | 설정 난이도 | 가이드 |
|------|--------------|------------|------|
| ⭐ **GitHub Actions** (권장) | ✅ | 쉬움 (Secret 등록만) | [`docs/GITHUB_ACTIONS_SETUP.md`](docs/GITHUB_ACTIONS_SETUP.md) |
| Prefect 정식 서버 (로컬) | ❌ | 중간 (터미널 3개) | [`docs/PREFECT_SETUP.md`](docs/PREFECT_SETUP.md) |

**GitHub Actions 자동 수집 워크플로우** (`.github/workflows/collect.yml`):
- 매시 :15 UTC에 GitHub 서버가 자동 실행
- 결과 DB는 레포에 자동 commit → 컴퓨터 안 켜도 영구 누적
- 무료 (public repo 무제한)
- 사용자가 할 일: GitHub repo 생성 → `AIRKOREA_API_KEY` Secret 등록 → push

> ⚠️ Prefect `flow.serve()`만으로는 **스케줄러가 동작하지 않습니다** (Prefect 3 ephemeral 서버 한계). 매시 cron을 로컬에서 돌리려면 `prefect server start`가 별도로 필요합니다.

## Cp/Cpk 분석

```bash
# 누적 데이터가 측정소당 30건 이상일 때부터 의미 있는 결과
uv run python scripts/analyze_capability.py            # daily USL
uv run python scripts/analyze_capability.py --basis hourly
uv run python scripts/analyze_capability.py --basis annual
```

## Phase 진행 상태

- [x] **Phase 1**: 수집 + SQLite 저장
- [~] **Phase 2**: SPC 분석 (Cp/Cpk 완료, 관리도/WE Rules/이상탐지 예정)
- [~] **Phase 3**: Prefect 스케줄 완료. Streamlit 대시보드 + Discord 알림 예정
- [ ] **Phase 4**: 기상 데이터 결합 + 회귀 분석 (선택)
