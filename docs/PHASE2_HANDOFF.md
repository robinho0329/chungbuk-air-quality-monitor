# Phase 2 진입 핸드오프

> 다음 세션에서 SPC 분석 단계로 들어갈 때 컨텍스트를 빠르게 복원하기 위한 메모.
> Phase 1 종료 직후 기록.

## Phase 1 최종 상태

| 항목 | 상태 | 비고 |
|------|------|------|
| 프로젝트 인프라 (uv, pyproject, 폴더 구조) | ✅ | Python 3.14.3, `package=false` |
| 서브에이전트 5종 | ✅ | `.claude/agents/`에 정의 |
| 환경 변수 시스템 (`src/config.py`) | ✅ | `.env` 로드, 필수 변수 검증 |
| 에어코리아 클라이언트 (`src/collectors/airkorea.py`) | ✅ | 측정소정보 / 시도별 실시간 / 마스킹 / 재시도 |
| SQLite 저장소 (`src/storage/models.py`, `database.py`) | ✅ | UNIQUE(station_name, data_time), INSERT OR IGNORE |
| 통합 스크립트 (`scripts/`) | ✅ | `check_stations.py`, `collect_once.py` |
| 측정소 정보 검증 | ✅ | 4/4 매칭 (오창읍, 복대동, 오송읍, 용암동) |
| pytest 단위 테스트 | ✅ | 38건 통과 (변환·마스킹·모델·제약) |
| 실데이터 수집 검증 | ⏳ | 공공데이터포털 1:1 문의 답변 대기 중 |

**핵심**: 코드는 완성됐고 외부 API 활성화만 남았다. 활성화되면 `uv run python scripts/collect_once.py` 한 번으로 Phase 1 종결.

## 핵심 모듈 맵

```
src/
├── config.py                   # AIRKOREA_API_KEY, DATABASE_URL, TARGET_STATIONS
├── collectors/airkorea.py      # AirkoreaClient, to_measurement, filter_target_stations
└── storage/
    ├── models.py               # AirQualityMeasurement (SQLModel)
    └── database.py             # init_db, insert_measurements, query_all, query_by_station
scripts/
├── check_stations.py           # 측정소 메타 확인용
└── collect_once.py             # 수집-저장 1회 사이클
docs/
├── stations.md                 # 4개 측정소 확정 정보
└── PHASE2_HANDOFF.md           # 이 문서
tests/
├── test_collectors.py          # 변환·마스킹 (34건)
└── test_storage.py             # DB 스키마·제약 (4건)
```

## 데이터 스키마

`AirQualityMeasurement` (테이블 `air_quality_measurement`):

| 컬럼 | 타입 | 의미 |
|------|------|------|
| id | int PK | 자동 증가 |
| station_name | str (index) | 측정소명 |
| data_time | datetime (index) | 측정 시각 |
| pm10, pm25 | float | ㎍/㎥ |
| o3, no2, so2, co | float | ppm |
| khai | float | 통합대기환경지수 |
| *_grade (7개) | int | 1=좋음, 2=보통, 3=나쁨, 4=매우나쁨 |
| flag | str | 결측 사유 (점검/통신장애 등) |
| created_at | datetime | DB 저장 시각 |

**UNIQUE 제약**: `(station_name, data_time)`. 중복 호출 시 자동 스킵.

## Phase 2 작업 범위 (예정)

### 목표
충분히 누적된 측정 데이터(권장: 표본 30개 이상)에 SPC 분석을 적용해
공정능력지수(Cp/Cpk)와 이상 탐지 결과를 산출하는 분석 모듈을 추가한다.

### 신설 모듈 (예상)
```
src/analysis/
├── __init__.py
├── usl_lsl.py              # 환경기준 상수 (USL/LSL) 모음
├── capability.py           # Cp, Cpk, Pp, Ppk 계산
├── control_chart.py        # X-bar, I-MR, EWMA, CUSUM 데이터 생성
├── western_electric.py     # WE 8 룰 자동 판정
└── anomaly.py              # IsolationForest 다변량 이상 탐지
scripts/
├── analyze_capability.py   # Cp/Cpk 리포트
└── analyze_anomaly.py      # 이상 탐지 리포트
tests/
├── test_capability.py
├── test_western_electric.py
└── test_anomaly.py
```

### 환경 기준치 (대기환경보전법, 사전 확정)

LSL은 모두 0. Cp/Cpk 계산 시 시간평균(1h) USL 사용 권장:

| 지표 | 1시간 USL | 24시간 USL | 연평균 USL | 단위 |
|------|----------|-----------|-----------|------|
| PM10 | (해당 없음) | 100 | 50 | ㎍/㎥ |
| PM2.5 | (해당 없음) | 35 | 15 | ㎍/㎥ |
| O3 | 0.1 | (해당 없음) | (해당 없음) | ppm |
| NO2 | 0.1 | 0.06 | 0.03 | ppm |
| SO2 | 0.15 | 0.05 | 0.02 | ppm |
| CO | 25 | (해당 없음) | (해당 없음) | ppm |

> Phase 2에서는 일평균 USL을 기본으로, 시간단위 분석에서는 1h USL을 옵션으로 제공.

### Cp/Cpk 규칙 (서브에이전트 정의 인용)
- 표본 < 30이면 계산 거부 (경고)
- 표준편차는 표본표준편차 (`ddof=1`)
- `Cp = (USL - LSL) / (6σ)`
- `Cpk = min((USL - μ) / (3σ), (μ - LSL) / (3σ))`
- Cpk 음수는 그대로 보고 (절댓값 처리 금지)

### 이상 탐지 우선순위
1. Western Electric Rules (해석가능성 ★★★)
2. EWMA (미세 평균 이동)
3. IsolationForest (다변량 보조)

룰 기반과 ML 충돌 시 룰 기반 우선.

## 다음 세션 시작 시 입력할 프롬프트 (템플릿)

```
Phase 2 진입. Phase 1은 코드 측면 완료 상태.
프로젝트 루트: C:/Users/xcv54/workspace/Sideproject_260526

먼저 docs/PHASE2_HANDOFF.md를 읽고 컨텍스트 파악.
그 후 다음을 수행:

1. 실데이터 충분히 누적됐는지 확인 (query_all 카운트)
2. data-analyst 서브에이전트에게 위임해 src/analysis/ 모듈 골조 작성
   - usl_lsl.py: 환경기준 상수
   - capability.py: Cp/Cpk 계산 + 최소표본 30 검증
3. scripts/analyze_capability.py: 4개 측정소 × 6개 지표 Cp/Cpk 리포트
4. 단위 테스트 추가 (tests/test_capability.py)
5. 김태현 스카우트 페르소나는 본 프로젝트 외 EPL 프로젝트 컨텍스트이므로 무시.
   본 프로젝트는 QC/API 직무 포트폴리오.

설계 결정 필요한 부분은 먼저 질문할 것.
```

## 사전 체크 명령

새 세션에서 가장 먼저 실행:

```bash
cd "C:/Users/xcv54/workspace/Sideproject_260526"

# 1. 의존성 정상인지
uv run python -c "import pandas, sqlmodel, loguru; print('OK')"

# 2. 누적 데이터 카운트
uv run python -c "from src.storage.database import query_all; rows = query_all(); print(f'누적 {len(rows)}건'); from collections import Counter; c = Counter(r.station_name for r in rows); [print(f'  {k}: {v}건') for k, v in c.items()]"

# 3. 테스트 정상인지
uv run pytest -q
```

데이터가 충분치 않으면 (`< 30건/측정소`) Phase 2 분석은 의미가 약하므로,
`collect_once.py`를 일정 주기로 반복 실행하거나 Prefect 도입을 먼저 고민.

## Phase 2가 끝난 후 Phase 3 예고

- Prefect flow: `flows/collect_flow.py` (매시 정각 5분 후 실행)
- Streamlit 멀티페이지 대시보드: `src/dashboard/`
- Discord Webhook 알림: `src/notifier/`

위 셋은 모두 파일 겹침이 없어 병렬 작업 가능.

## 변경 이력

- 2026-05-27: 초기 작성 (Phase 1 종료 직후)
