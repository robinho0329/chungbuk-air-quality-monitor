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
├── check_stations.py      # 측정소 정보 검증
└── collect_once.py        # 수집→저장 1회 실행
docs/
└── stations.md            # 측정소 정의 문서
.claude/agents/            # 서브에이전트 정의 5종
```

## Phase 진행 상태

- [x] **Phase 1**: 수집 + SQLite 저장 (현재 세션)
- [ ] **Phase 2**: SPC 분석 (Cp/Cpk, 관리도, Western Electric Rules)
- [ ] **Phase 3**: Prefect 스케줄 + Streamlit 대시보드 + Discord 알림
- [ ] **Phase 4**: 기상 데이터 결합 + 회귀 분석 (선택)
