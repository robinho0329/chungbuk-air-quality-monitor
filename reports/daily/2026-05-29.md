# 📅 데일리 리포트 — 2026-05-29 (KST)

> 자동 생성: 2026-05-29 13:40 KST · GitHub Actions `daily_dev_loop.yml`

## ✅ 회귀 테스트
- 🟢 `60 passed in 0.63s`

## 📦 누적 데이터
- 총 누적: **24 건**
- 시각 범위: 2026-05-28 20:00:00 ~ 2026-05-29 08:00:00 (6개 unique 시각)
- 측정소별:
  - 복대동: 6건
  - 오송읍: 6건
  - 오창읍: 6건
  - 용암동: 6건

## ⏱️ 최근 24시간 수집 성공률
- 24 / 96건 = **25.0%**
- 누락 시각(최대 5개): 2026-05-28 13:00, 2026-05-28 14:00, 2026-05-28 15:00, 2026-05-28 16:00, 2026-05-28 17:00

## 📐 Cp/Cpk 매트릭스 (daily basis)
| 측정소 | PM10 | PM25 | O3 | NO2 | SO2 | CO |
|---|---|---|---|---|---|---|
| 오창읍 | n=6 | n=6 | n=6 | n=6 | n=6 | n=6 |
| 복대동 | n=0 | n=0 | n=0 | n=0 | n=0 | n=0 |
| 오송읍 | n=6 | n=6 | n=6 | n=6 | n=6 | n=6 |
| 용암동 | n=6 | n=6 | n=6 | n=6 | n=6 | n=6 |

표기: `n=N` → 표본 부족 (최소 30), `기준없음` → 해당 basis USL 미정의

## 🎯 데이터 마일스톤 진행률
- `DATA_30_PER_STATION`: 6/30 (최소 측정소 기준) ██░░░░░░░░ 20%
- `DATA_50_PER_STATION`: 6/50 █░░░░░░░░░ 12%
- `DATA_500`: 24/500 ░░░░░░░░░░ 5%
- `DATA_1000`: 24/1000 ░░░░░░░░░░ 2%

## 🚀 다음 후보 작업 (PHASE_QUEUE.yml 기준)
- **[P2/CONTROL_CHART]** EWMA/CUSUM/X-bar 관리도 데이터 생성 — ★★★ — ✅ READY
- **[P2/HYPOTHESIS_TEST]** t-test/ANOVA 단지 비교 통계 검정 — ★★★ — ⛔ blocked by ['DATA_30_PER_STATION']
- **[P2/WE_RULES]** Western Electric 8 Rules 자동 판정 — ★★★ — ⛔ blocked by ['DATA_30_PER_STATION']
- **[P3/DMAIC_REPORT]** DMAIC 분석 보고서 자동 생성 (PDF) — ★★★ — ⛔ blocked by ['DATA_500', 'HYPOTHESIS_TEST', 'WE_RULES']
- **[P2/ISOLATION_FOREST]** IsolationForest 다변량 이상 탐지 — ★★ — ⛔ blocked by ['DATA_50_PER_STATION']

---
🤖 *이 리포트는 매일 KST 09:15에 자동 생성됩니다. Claude 세션에서 다음 작업을 결정할 때 참조하세요.*