"""대시보드 공통 헬퍼.

여러 페이지에서 재사용하는 데이터 로드·캐싱·스타일 유틸.
"""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

# 프로젝트 루트를 sys.path에 추가 (streamlit run dashboard/app.py 대응)
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

from src.storage.database import query_all  # noqa: E402


# 등급별 색상 (대기환경 표준)
GRADE_COLORS: dict[int, str] = {
    1: "#1f77b4",  # 좋음 (파랑)
    2: "#2ca02c",  # 보통 (초록)
    3: "#ff7f0e",  # 나쁨 (주황)
    4: "#d62728",  # 매우나쁨 (빨강)
}

GRADE_LABELS: dict[int, str] = {
    1: "좋음",
    2: "보통",
    3: "나쁨",
    4: "매우나쁨",
}

POLLUTANT_DISPLAY: dict[str, str] = {
    "pm10": "PM10 (㎍/㎥)",
    "pm25": "PM2.5 (㎍/㎥)",
    "o3": "오존 O3 (ppm)",
    "no2": "이산화질소 NO2 (ppm)",
    "so2": "아황산가스 SO2 (ppm)",
    "co": "일산화탄소 CO (ppm)",
}


@st.cache_data(ttl=60, show_spinner=False)
def load_dataframe() -> pd.DataFrame:
    """전체 측정 데이터를 DataFrame으로 로드한다 (60초 캐시).

    Streamlit 캐시 덕분에 페이지 전환·재실행 시 DB 호출 최소화.
    """
    rows = query_all()
    if not rows:
        return pd.DataFrame()
    records = [
        {
            "station_name": r.station_name,
            "data_time": r.data_time,
            "created_at": r.created_at,
            "pm10": r.pm10,
            "pm25": r.pm25,
            "o3": r.o3,
            "no2": r.no2,
            "so2": r.so2,
            "co": r.co,
            "khai": r.khai,
            "pm10_grade": r.pm10_grade,
            "pm25_grade": r.pm25_grade,
            "khai_grade": r.khai_grade,
            "flag": r.flag,
        }
        for r in rows
    ]
    return pd.DataFrame.from_records(records)


def render_data_status(df: pd.DataFrame) -> None:
    """페이지 상단에 누적 데이터 현황을 안내한다.

    Cp/Cpk 분석을 위한 최소 표본(30)에 대한 진행률 표시.
    """
    if df.empty:
        st.warning(
            "🌬️ 누적 데이터가 없습니다. GitHub Actions 첫 수집이 완료될 때까지 잠시 기다려주세요."
        )
        return
    total = len(df)
    stations = df["station_name"].nunique()
    last_time = df["data_time"].max()
    min_per_station = df.groupby("station_name").size().min()
    progress = min(min_per_station / 30.0, 1.0)

    cols = st.columns(4)
    cols[0].metric("총 누적", f"{total:,} 건")
    cols[1].metric("측정소", f"{stations} 곳")
    cols[2].metric(
        "마지막 측정 시각",
        last_time.strftime("%m-%d %H:%M") if pd.notna(last_time) else "—",
    )
    cols[3].metric(
        "Cp/Cpk 준비도",
        f"{int(progress * 100)}%",
        help=f"가장 적은 측정소 기준 {min_per_station}/30건",
    )

    if min_per_station < 30:
        st.info(
            f"📈 Cp/Cpk 분석은 측정소당 최소 30건 필요합니다. "
            f"현재 최소 {min_per_station}건. 매시 자동 누적 중 (GitHub Actions)."
        )


def page_header(emoji: str, title: str, description: str = "") -> None:
    """페이지 상단 헤더 일관 적용."""
    st.title(f"{emoji} {title}")
    if description:
        st.caption(description)
