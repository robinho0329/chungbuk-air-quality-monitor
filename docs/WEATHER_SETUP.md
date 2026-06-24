# 기상 데이터 결합 (Phase 4) — 셋업 & 분석

분산분해에서 드러난 **"PM2.5 변동의 97.6%는 시간·기상"** 의 *기상* 내역을 실증하고,
원래 가설 H4(**풍향이 산단→측정소 방향일 때 농도 상승**)를 검정하기 위한 파이프라인.

## 무엇이 들어왔나
| 파일 | 역할 |
|------|------|
| `src/collectors/weather.py` | 기상청 ASOS 시간자료 클라이언트(청주 지점 131) — 기온·습도·풍속·풍향·강수 |
| `src/storage/models.py` `WeatherObservation` | 기상 관측 테이블 (obs_time, ta/hm/ws/wd/rn) |
| `scripts/collect_weather.py` | 최근 3일 멱등 수집(백필 포함). `collect.yml`에 통합돼 같은 외부 cron으로 누적 |
| `src/analysis/wind_regression.py` | ① 오염장미(8방위 농도) ② 산단 방위 검정(Welch t-test) ③ 기상 회귀(농도~풍속·기온·습도) |

## 활성화 (2단계)
1. **API 키 발급** — [공공데이터포털](https://www.data.go.kr)에서 *"기상청 지상(종관, ASOS) 시간자료 조회서비스"* 활용신청 → **Decoding 키** 확보.
2. **키 등록**
   - GitHub: Repo → Settings → Secrets → `WEATHER_API_KEY` 추가 (대기질 키와 별도)
   - 로컬: `.env`에 `WEATHER_API_KEY=...`

→ 등록 즉시 매시 수집에 기상 단계가 붙어 데이터가 누적된다. 키가 없으면 수집 단계는 조용히 스킵(워크플로 영향 없음).

## 분석 사용 예
```python
import pandas as pd
from src.storage.database import query_all, query_weather
from src.analysis.wind_regression import (
    join_air_weather, pollution_rose, directional_test, weather_regression, bearing,
)
from src.config import STATION_COORDS, INDUSTRIAL_SOURCES

air = pd.DataFrame([r.model_dump() for r in query_all()])
wx  = pd.DataFrame([r.model_dump() for r in query_weather()])
st  = air[air.station_name == "오송읍"]
m   = join_air_weather(st, wx)

pollution_rose(m, "pm25")                      # 8방위별 PM2.5 평균
b = bearing(*STATION_COORDS["오송읍"], *INDUSTRIAL_SOURCES["오송생명과학단지"])
directional_test(m, "pm25", source_bearing=b)  # 산단 방위 바람일 때 농도↑? (H4)
weather_regression(m, "pm25")                  # 농도 ~ 풍속·기온·습도 R²·계수
```

## 데이터 충분도
풍향 검정·회귀는 **측정소·방위 섹터별 30+ 표본**이 권장. 기상 누적이 수 주 쌓이면
덱에 오염장미·풍향 검정 차트를 추가해 "시간·기상 97.6%"를 *기상 변수로 분해*한 실증으로 격상한다.
