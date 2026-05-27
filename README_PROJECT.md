# 충북권 산업단지 대기질 모니터링 시스템

## 프로젝트 개요
QC/API 생산관리 직무 포트폴리오. 청주 지역 4개 대기 측정소에서
실시간 데이터를 수집해 SPC 분석과 이상 탐지를 자동화한다.

## 측정소 정의
| 그룹 | 측정소 | 단지 |
|------|--------|------|
| 첨단소재 | 오창읍 | 오창과학단지 (이차전지) |
| 일반제조 | 복대동 | 청주산업단지 |
| 바이오·제약 | 오송읍 | 오송생명과학단지 (API 직무 핵심) |
| 베이스라인 | 용암동 | 청주 상당구 거주지 |

## 분석 가설
1. 산단 영향군(오창·복대·오송) 평균이 베이스라인(용암동)보다 높다
2. 단지 업종에 따라 주요 오염물질 프로파일이 다르다
3. 주중 vs 주말 패턴에서 산단 영향이 두드러진다
4. 풍향에 따라 산단→측정소 방향일 때 농도 상승

## 기술 스택
- Python 3.14.3 (uv venv)
- requests, pandas, sqlmodel
- Prefect (워크플로우)
- Streamlit (대시보드)
- Discord Webhook (알림)
- loguru (로깅)
- pytest (테스트)

## 폴더 구조
```
src/
├── config.py
├── collectors/      # API 수집
├── storage/         # SQLite
├── analysis/        # SPC, Cp/Cpk, 이상 탐지
├── notifier/        # Discord
└── dashboard/       # Streamlit
flows/               # Prefect flows
scripts/             # 일회성 실행 스크립트
tests/               # pytest
data/                # raw/processed (gitignore)
docs/                # 설계 문서
```

## Phase 계획
- Phase 1 (현재): 수집 + SQLite 저장 (MVP)
- Phase 2: SPC 분석 (Cp/Cpk, 관리도, 이상 탐지)
- Phase 3: Prefect 스케줄링 + Streamlit 대시보드 + Discord 알림
- Phase 4: 기상 데이터 결합 + 회귀 분석 (선택)

## 절대 원칙
1. 인증키 하드코딩 금지 → .env
2. 더미 데이터 사용 금지 → 실제 API만
3. 측정 단위·등급 임의 변경 금지
4. uv 외 패키지 관리 도구 사용 금지
