# 개발 제안 — 에이전트 논의 종합 + 업계 리서치

> 작성: 2026-05-29. 두 전문 관점(QC/6시그마 블랙벨트 vs 시니어 데이터엔지니어/ML)의
> 제안을 종합하고, 실제 대기질 모니터링(AQM) 시스템 리서치를 반영한 다음 단계 로드맵.

## 1. 업계 리서치 요약 (실제 AQM 시스템은 어떻게 돌아가나)

| 영역 | 실무 표준 | 우리 프로젝트 시사점 |
|------|----------|---------------------|
| 데이터 품질 | 에어코리아 NAMIS는 **2단계 이상자료 선별**(1차 장비상태, 2차 통계적 범위·변화율) | 결측/이상치 게이트를 명시적 단계로 구현 |
| 실시간 이탈 탐지 | Shewhart/EWMA/CUSUM + **alert/action 2단 한계** | 단순 3σ를 넘어 alert/action 정책화 |
| ⚠️ 통계 한계 | 전통 SPC는 관측치 **i.i.d. 가정** — 대기질은 강한 시계열 자기상관 → 거짓경보 多 | **핵심 약점. 잔차 관리도로 정면돌파 필요** |
| 예측 | LSTM/CNN-LSTM/Transformer-LSTM. 기상·이웃측정소·타오염물질 결합이 정확도↑ | 데이터 부족 단계에선 베이스라인부터 |
| 운영 | ETL(Airflow/Kafka), 엣지 버퍼링으로 네트워크 단절 대응 | best-effort cron의 누락을 멱등 백필로 수렴 |

출처: airkorea.or.kr(NAMIS 이상자료 선별), MDPI/arXiv(LSTM·SPC), Annals of Applied Statistics(동적 공정 관리도).

## 2. 두 관점의 합의 / 쟁점

**강한 합의 (둘 다 최우선급):**
- 🎯 **자기상관(i.i.d. 위반) 정면돌파가 1순위.** 현재 `estimate_sigma_mr`(MR n=2 기반)는 자기상관 데이터에서 σ를 과소추정 → 관리한계가 좁아져 거짓경보 폭증. 신규 기능을 얹기 전에 이 통계적 타당성부터 복구해야 한다.
- ⛔ **ISOLATION_FOREST·순수 LSTM은 보류.** QC 관점: "SPC를 못 풀어 ML로 도피"로 읽힘. DE 관점: 측정소당 ~720건(1개월)은 딥러닝에 명백히 부족, persistence 베이스라인도 못 이김.
- 🔁 **WE_RULES는 자기상관 처리 후에.** 거짓경보 위에 8규칙을 얹으면 오경보를 증폭.

**상호보완 (충돌 아님, 두 트랙으로 병행):**
- QC 트랙(통계적 성숙도): 잔차 관리도 → MSA 대체분석 → DMAIC PDF → 기상 결합 원인분석
- DE 트랙(운영 견고성): self-healing 백필 → 데이터 품질 게이트 → data.db 저장전략

## 3. 통합 로드맵 (우선순위)

### P0 — 자기상관 정면돌파: 잔차 관리도 (Residual / ARIMA-based SPC) ★최우선
- lag-1 ACF/PACF로 자기상관 진단 → AR(1)/ARIMA 적합 후 **잔차에 I-Chart/EWMA 적용**.
- 원천 직접 관리도 vs 잔차 관리도의 **거짓경보율 Before/After 비교표**를 리포트에 박제.
- `estimate_sigma_mr`에 자기상관 경고 게이트(ACF>0.5 시 σ 과소추정 위험 플래그).
- 공수 M / 임팩트 **최상** — "SPC를 짤 줄 아는 사람"과 "SPC를 실무에 쓸 줄 아는 사람"의 분기점.

### P1 — Self-healing 수집 백필 (운영 신뢰성 근본 해결) ✅ 완료 (2026-05-29)
- 매 수집 실행에서 직전 24h 갭 감지 → DAILY 기간조회로 자동 복구(>30h 갭은 MONTH escalate).
  cron 시도 횟수↑가 아니라 **수렴 보장 구조**. cron이 며칠 드롭돼도 다음 1회 성공이 메움.
- 구현: `src/collectors/self_heal.py`(find_missing_hours/self_heal), `collect_once.py`에 연결,
  `database.py:query_pairs_since`. 테스트 7건. 원본 부재 시각은 "잔여"로 정직 보고.
- "best-effort cron 한계를 멱등 백필로 극복" — 운영 서사 확보.

### P2 — 데이터 품질 게이트 + MSA 대체분석
- (운영) 측정소×시간 커버리지·결측률·물리범위 검증을 수집모니터링 페이지+daily 리포트에 노출. 복대동 PM2.5 통신장애를 명시적 결측사유로 구분.
- (QC) 동일권역 측정소(복대 vs 봉명) 일치도·Bland-Altman, 분산성분 분해(측정소 간 vs 시간변동)로 **DMAIC Measure(MSA) 공백** 메움.
- 공수 S~M / 신규 의존성 불필요.

### P3 — DMAIC 분석 보고서 (PDF): 도구 나열 → 문제해결 서사
- Cpk·관리도·가설검정·P0~P2를 D→M→A→I→C 한 편으로 통합. Improve/Control은 alert/action limit 운영안 + 잔차 관리도 도입으로 실질화(가짜 Improve 금지).
- 공수 M / 임팩트 상 — 면접 제출용 핵심 산출물.

### P4 — WEATHER_API (기상 결합 + 풍향 회귀) — 교란변수 통제
- 풍향·풍속 결합 → "기상 통제 후에도 산단 효과가 유의한가"(ARIMAX 외생변수). P0 시계열 모델과 시너지.
- 가설 H1(풍상측 외부유입) 직접 검증. 공수 L.

### P5 — WE_RULES + Discord 알림 (SPC 운영 완성) — 단, P0 이후
- Western Electric 8 Rules를 **잔차/EWMA 기반 위에서** 적용 + alert/action 2단 한계 정책화 + 이상신호 Discord 푸시. 공수 S.

### 보류
- ISOLATION_FOREST: 3개월+ 데이터 확보 후 SPC 타당성 증명 뒤 보조수단으로.
- 순수 LSTM/Transformer: 데이터 축적(측정소당 2000건+) 후. 그 전엔 persistence·계절성 나이브·LightGBM(시차+기상) 베이스라인으로 ML 가치를 정직하게 진단.
- data.db 저장전략: 1단계(일1회 커밋 + binary 머지전략)로 충돌 완화, 수 MB 초과 시 Turso/libSQL(SQLite 호환) 이전.

## 4. 한 줄 결론
**신규 기능 추가(큐 소진)보다, 이미 만든 관리도의 통계적 타당성 복구(P0 잔차 관리도)와 수집 자가복구(P1)가 압도적 우선이다.** 화려한 LSTM·다변량 이상탐지보다 "self-healing 수집 + 자기상관 보정 SPC + 정직한 ML 진단"이 QC·DE 양쪽 모두에 설득력 있는 시니어 포트폴리오다.
