"""4개 측정소(단지) 간 통계 비교."""

from __future__ import annotations

import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import pandas as pd  # noqa: E402
import plotly.express as px  # noqa: E402
import streamlit as st  # noqa: E402

from dashboard._lib import (  # noqa: E402
    POLLUTANT_DISPLAY,
    load_dataframe,
    page_header,
    render_data_status,
)

st.set_page_config(page_title="단지 비교", page_icon="🏭", layout="wide")
page_header(
    "🏭",
    "단지 간 비교",
    "오창과학·청주산업·오송바이오 vs 용암동 베이스라인. 산단 영향 가설 검증용.",
)

df = load_dataframe()
render_data_status(df)
st.divider()

if df.empty:
    st.stop()

pollutant = st.selectbox(
    "비교할 지표",
    list(POLLUTANT_DISPLAY.keys()),
    format_func=lambda k: POLLUTANT_DISPLAY[k],
)

df_p = df[df[pollutant].notna()].copy()
if df_p.empty:
    st.info(f"{POLLUTANT_DISPLAY[pollutant]} 값이 모두 결측입니다.")
    st.stop()

# ----------------------------------------------------------------------
# Boxplot
# ----------------------------------------------------------------------
st.subheader(f"📦 {POLLUTANT_DISPLAY[pollutant]} 분포 비교")
fig_box = px.box(
    df_p,
    x="station_name",
    y=pollutant,
    color="station_name",
    points="all",
    labels={
        "station_name": "측정소",
        pollutant: POLLUTANT_DISPLAY[pollutant],
    },
)
fig_box.update_layout(height=450, showlegend=False)
st.plotly_chart(fig_box, use_container_width=True)

# ----------------------------------------------------------------------
# 측정소별 통계 테이블
# ----------------------------------------------------------------------
st.subheader("📊 측정소별 요약 통계")
summary = (
    df_p.groupby("station_name")[pollutant]
    .agg(["count", "mean", "std", "min", "max", "median"])
    .round(3)
    .rename(
        columns={
            "count": "표본수",
            "mean": "평균 μ",
            "std": "표준편차 σ",
            "min": "최소",
            "max": "최대",
            "median": "중앙값",
        }
    )
)
summary.index.name = "측정소"

# 베이스라인(용암동) 대비 차이 표시
if "용암동" in summary.index:
    baseline_mean = summary.loc["용암동", "평균 μ"]
    summary["베이스라인 대비"] = (
        (summary["평균 μ"] - baseline_mean) / baseline_mean * 100
    ).round(1).astype(str) + " %"

st.dataframe(summary, use_container_width=True)

st.caption(
    "💡 가설: 산단 영향군(오창·복대·오송) 평균이 베이스라인(용암동)보다 높다면 "
    "산단 영향으로 해석할 수 있음 (단, 표본 충분·정규성 검증 필요)."
)

# ----------------------------------------------------------------------
# 시계열 분포 (overlay)
# ----------------------------------------------------------------------
st.divider()
st.subheader(f"🕐 {POLLUTANT_DISPLAY[pollutant]} 시계열 (4개 측정소 동시)")
df_p["data_time"] = pd.to_datetime(df_p["data_time"])
fig_line = px.line(
    df_p.sort_values("data_time"),
    x="data_time",
    y=pollutant,
    color="station_name",
    markers=True,
    labels={
        "data_time": "측정 시각",
        pollutant: POLLUTANT_DISPLAY[pollutant],
        "station_name": "측정소",
    },
)
fig_line.update_layout(height=420, hovermode="x unified")
st.plotly_chart(fig_line, use_container_width=True)
