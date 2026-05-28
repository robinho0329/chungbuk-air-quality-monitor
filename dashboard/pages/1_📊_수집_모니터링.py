"""수집 모니터링: 시간대별 누적·created_at 기반 수집 이력."""

from __future__ import annotations

import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import pandas as pd  # noqa: E402
import plotly.express as px  # noqa: E402
import streamlit as st  # noqa: E402

from dashboard._lib import load_dataframe, page_header, render_data_status  # noqa: E402

st.set_page_config(page_title="수집 모니터링", page_icon="📊", layout="wide")
page_header(
    "📊",
    "수집 모니터링",
    "GitHub Actions로 매시 자동 수집되는 이력을 확인합니다.",
)

df = load_dataframe()
render_data_status(df)
st.divider()

if df.empty:
    st.stop()

# ----------------------------------------------------------------------
# 측정소별 누적 카운트
# ----------------------------------------------------------------------
st.subheader("📦 측정소별 누적 레코드")
count_by_station = (
    df.groupby("station_name").size().reset_index(name="레코드 수")
)
count_by_station.columns = ["측정소", "레코드 수"]
count_by_station = count_by_station.sort_values("레코드 수", ascending=False)

fig_bar = px.bar(
    count_by_station,
    x="측정소",
    y="레코드 수",
    text="레코드 수",
    color="레코드 수",
    color_continuous_scale="Blues",
)
fig_bar.update_traces(textposition="outside")
fig_bar.update_layout(showlegend=False, coloraxis_showscale=False, height=380)
st.plotly_chart(fig_bar, use_container_width=True)

# ----------------------------------------------------------------------
# 시간대별 누적 수집 (data_time 기준)
# ----------------------------------------------------------------------
st.subheader("🕐 시간대별 수집 분포 (측정 시각 기준)")
df_time = df.copy()
df_time["data_time"] = pd.to_datetime(df_time["data_time"])
df_time["일자"] = df_time["data_time"].dt.date

daily = (
    df_time.groupby(["일자", "station_name"]).size().reset_index(name="건수")
)
daily.columns = ["일자", "측정소", "건수"]
fig_line = px.line(
    daily,
    x="일자",
    y="건수",
    color="측정소",
    markers=True,
)
fig_line.update_layout(height=380, hovermode="x unified")
st.plotly_chart(fig_line, use_container_width=True)

# ----------------------------------------------------------------------
# DB 저장 시각 (created_at) 기반 자동화 동작 확인
# ----------------------------------------------------------------------
st.subheader("⚙️ 자동 수집 가동 이력 (DB 저장 시각)")
st.caption(
    "GitHub Actions가 매시 :15 UTC에 자동 실행됩니다. "
    "아래는 실제 row가 DB에 insert된 시각의 분포입니다."
)
df_created = df.copy()
df_created["created_at"] = pd.to_datetime(df_created["created_at"])
df_created["시각"] = df_created["created_at"].dt.floor("h")
created_count = (
    df_created.groupby("시각").size().reset_index(name="신규 insert 건수")
)
fig_created = px.bar(created_count, x="시각", y="신규 insert 건수")
fig_created.update_layout(height=320)
st.plotly_chart(fig_created, use_container_width=True)

st.divider()

# ----------------------------------------------------------------------
# 외부 링크
# ----------------------------------------------------------------------
st.subheader("🔗 외부 모니터링")
st.markdown(
    """
- **GitHub Actions 실행 이력** (영어 UI):
  https://github.com/robinho0329/chungbuk-air-quality-monitor/actions
- **자동 커밋 히스토리**:
  https://github.com/robinho0329/chungbuk-air-quality-monitor/commits/main

`auto(collect): airkorea snapshot ...` 패턴의 커밋이 매시 자동으로 push됩니다.
"""
)
