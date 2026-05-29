"""실시간 측정값 시계열 차트 + 환경기준선."""

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
    date_range_filter,
    fmt_kst,
    load_dataframe,
    page_header,
    render_data_status,
    render_footer,
    render_sidebar,
)
from src.analysis.usl_lsl import SPEC_LIMITS  # noqa: E402

st.set_page_config(page_title="실시간 측정값", page_icon="🌬️", layout="wide")
df = load_dataframe()
render_sidebar(df)

page_header(
    "🌬️",
    "실시간 측정값",
    "측정소별 6개 지표 시계열. 환경기준선(USL)을 차트에 표시합니다. (모든 시각 KST)",
)

render_data_status(df)
st.divider()

if df.empty:
    render_footer()
    st.stop()

# ----------------------------------------------------------------------
# 기간 필터 (계절성 등 기간 분석)
# ----------------------------------------------------------------------
df = date_range_filter(df, key="rt")
if df.empty:
    st.warning("선택한 기간에 데이터가 없습니다.")
    render_footer()
    st.stop()
st.divider()

# ----------------------------------------------------------------------
# 필터 (사이드바 아래)
# ----------------------------------------------------------------------
col_sel1, col_sel2 = st.columns([1, 1])
all_stations = sorted(df["station_name"].unique().tolist())
selected_stations = col_sel1.multiselect(
    "측정소 선택", all_stations, default=all_stations
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
    render_footer()
    st.stop()

# ----------------------------------------------------------------------
# 시계열 차트 + 환경기준선
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
            "data_time": "측정 시각 (KST)",
            selected_pollutant: POLLUTANT_DISPLAY[selected_pollutant],
            "station_name": "측정소",
        },
    )
    # 환경기준선(USL) 표시
    spec = SPEC_LIMITS[selected_pollutant]
    for basis_name, label_kr, dash in [
        ("hourly", "1시간 USL", "dot"),
        ("daily", "24h USL", "dash"),
        ("annual", "연평균 USL", "longdash"),
    ]:
        usl = spec.usl_for(basis_name)
        if usl is not None:
            fig.add_hline(
                y=usl,
                line_dash=dash,
                line_color="red",
                opacity=0.6,
                annotation_text=f"{label_kr} = {usl}",
                annotation_position="right",
                annotation_font_color="red",
                annotation_font_size=11,
            )
    fig.update_layout(height=480, hovermode="x unified")
    st.plotly_chart(fig, use_container_width=True)
    st.caption(
        "🔴 빨간 점선: 대기환경보전법 환경기준 (USL). "
        "지표별 1시간/24시간/연평균 기준치 중 정의된 것만 표시."
    )

    # 측정소별 요약 통계
    st.subheader("📋 요약 통계")
    summary = (
        df_filtered.groupby("station_name")[selected_pollutant]
        .agg(["count", "mean", "std", "min", "max"])
        .round(3)
        .rename(
            columns={
                "count": "표본수",
                "mean": "평균 μ",
                "std": "표준편차 σ",
                "min": "최소",
                "max": "최대",
            }
        )
    )
    summary.index.name = "측정소"
    st.dataframe(summary, use_container_width=True)

# ----------------------------------------------------------------------
# 결측·flag 이력
# ----------------------------------------------------------------------
st.divider()
st.subheader("⚠️ 결측·플래그 이력")
flagged = df[df["flag"].notna()].copy()
if flagged.empty:
    st.success("결측 사유 플래그가 기록된 측정 이력이 없습니다.")
else:
    flagged["data_time"] = pd.to_datetime(flagged["data_time"])
    flagged_display = flagged[["station_name", "data_time", "flag"]].copy()
    flagged_display["data_time"] = flagged_display["data_time"].apply(
        lambda t: fmt_kst(t)
    )
    flagged_display = flagged_display.sort_values("data_time", ascending=False)
    flagged_display.columns = ["측정소", "측정 시각", "결측 사유"]
    st.dataframe(flagged_display, hide_index=True, use_container_width=True)

render_footer()
