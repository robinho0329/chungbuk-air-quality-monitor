"""실시간 측정값 시계열 차트."""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from dashboard._lib import (
    POLLUTANT_DISPLAY,
    load_dataframe,
    page_header,
    render_data_status,
)

st.set_page_config(page_title="실시간 측정값", page_icon="🌬️", layout="wide")
page_header(
    "🌬️",
    "실시간 측정값",
    "측정소별 6개 지표 시계열. 결측(통신장애 등)은 자동 제외.",
)

df = load_dataframe()
render_data_status(df)
st.divider()

if df.empty:
    st.stop()

# ----------------------------------------------------------------------
# 필터
# ----------------------------------------------------------------------
col_sel1, col_sel2 = st.columns([1, 1])
all_stations = sorted(df["station_name"].unique().tolist())
selected_stations = col_sel1.multiselect(
    "측정소 선택",
    all_stations,
    default=all_stations,
)
pollutant_keys = list(POLLUTANT_DISPLAY.keys())
selected_pollutant = col_sel2.selectbox(
    "지표 선택",
    pollutant_keys,
    format_func=lambda k: POLLUTANT_DISPLAY[k],
    index=0,
)

if not selected_stations:
    st.warning("측정소를 1곳 이상 선택해주세요.")
    st.stop()

# ----------------------------------------------------------------------
# 시계열 차트
# ----------------------------------------------------------------------
df_filtered = df[df["station_name"].isin(selected_stations)].copy()
df_filtered["data_time"] = pd.to_datetime(df_filtered["data_time"])
df_filtered = df_filtered.dropna(subset=[selected_pollutant])

if df_filtered.empty:
    st.info(
        f"선택한 조건에 해당하는 데이터가 없습니다. "
        f"({selected_pollutant.upper()} 값이 모두 결측)"
    )
else:
    st.subheader(f"📈 {POLLUTANT_DISPLAY[selected_pollutant]} 시계열")
    fig = px.line(
        df_filtered.sort_values("data_time"),
        x="data_time",
        y=selected_pollutant,
        color="station_name",
        markers=True,
        labels={
            "data_time": "측정 시각",
            selected_pollutant: POLLUTANT_DISPLAY[selected_pollutant],
            "station_name": "측정소",
        },
    )
    fig.update_layout(height=480, hovermode="x unified")
    st.plotly_chart(fig, use_container_width=True)

    # 측정소별 요약 통계
    st.subheader("📋 요약 통계")
    summary = (
        df_filtered.groupby("station_name")[selected_pollutant]
        .agg(["count", "mean", "std", "min", "max"])
        .round(3)
        .rename(
            columns={
                "count": "표본수",
                "mean": "평균",
                "std": "표준편차",
                "min": "최소",
                "max": "최대",
            }
        )
    )
    summary.index.name = "측정소"
    st.dataframe(summary, use_container_width=True)

# ----------------------------------------------------------------------
# 결측·flag 안내
# ----------------------------------------------------------------------
st.divider()
st.subheader("⚠️ 결측·플래그 이력")
flagged = df[df["flag"].notna()].copy()
if flagged.empty:
    st.success("결측 사유 플래그가 기록된 측정 이력이 없습니다. (모든 데이터 정상)")
else:
    flagged["data_time"] = pd.to_datetime(flagged["data_time"])
    st.dataframe(
        flagged[["station_name", "data_time", "flag"]]
        .sort_values("data_time", ascending=False)
        .rename(
            columns={
                "station_name": "측정소",
                "data_time": "측정 시각",
                "flag": "결측 사유",
            }
        ),
        hide_index=True,
        use_container_width=True,
    )
