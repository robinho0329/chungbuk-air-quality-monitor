"""수집 모니터링: 시간대별 누적·24h 성공률·GHA 이력."""

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
    GITHUB_URL,
    compute_24h_success_rate,
    fmt_kst,
    load_dataframe,
    next_cron_eta_kst,
    page_header,
    render_data_status,
    render_footer,
    render_insight,
    render_sidebar,
)

st.set_page_config(page_title="수집 모니터링", page_icon="📊", layout="wide")
df = load_dataframe()
render_sidebar(df)

page_header(
    "📊",
    "수집 모니터링",
    "GitHub Actions로 매시 자동 수집되는 이력을 확인합니다. (모든 시각 KST 기준)",
)

render_data_status(df)
st.divider()

if df.empty:
    render_footer()
    st.stop()

render_insight(
    "외부 스케줄러가 **시간당 3회(:15/:35/:55) 폴링**하지만, 이는 에어코리아의 *가변 공개 지연*에 "
    "대응하는 **재시도(가용성)**일 뿐 데이터 해상도(1시간)와 무관합니다. 빈 시간대는 **self-healing**이 "
    "다음 실행에서 자동 복구하고, 측정시각(`data_time`)과 수집시각(`created_at`)을 분리 기록해 "
    "**'원천 결측' vs '수집 누락'**을 구분합니다."
)
st.divider()

# ----------------------------------------------------------------------
# 24h 성공률 KPI
# ----------------------------------------------------------------------
st.subheader("⏱️ 최근 24시간 자동 수집 상태")
received, expected, rate = compute_24h_success_rate(df)
c1, c2, c3, c4 = st.columns(4)
c1.metric(
    "성공률",
    f"{rate * 100:.1f}%",
    help=f"{received} / {expected}건 (4 측정소 × 24시간)",
)
c2.metric("받은 시각 × 측정소", f"{received}")
c3.metric("다음 자동 수집 예정", next_cron_eta_kst())
c4.metric(
    "마지막 수집 시각", fmt_kst(df["data_time"].max(), with_tz=False)
)

st.divider()

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
fig_bar.update_layout(showlegend=False, coloraxis_showscale=False, height=360)
st.plotly_chart(fig_bar, use_container_width=True)

# ----------------------------------------------------------------------
# 시간대별 누적 수집 (data_time 기준)
# ----------------------------------------------------------------------
st.subheader("🕐 일자별 수집 카운트")
df_time = df.copy()
df_time["data_time"] = pd.to_datetime(df_time["data_time"])
df_time["일자"] = df_time["data_time"].dt.date

daily = (
    df_time.groupby(["일자", "station_name"]).size().reset_index(name="건수")
)
daily.columns = ["일자", "측정소", "건수"]
fig_line = px.line(daily, x="일자", y="건수", color="측정소", markers=True)
fig_line.update_layout(height=360, hovermode="x unified")
st.plotly_chart(fig_line, use_container_width=True)

# ----------------------------------------------------------------------
# DB 저장 시각 (created_at) 분포
# ----------------------------------------------------------------------
st.subheader("⚙️ DB Insert 시각 분포 (GitHub Actions 실행 이력)")
st.caption(
    f"매시 :15 UTC = 대략 :24-:30 KST 사이에 자동 insert됩니다. "
    f"다음 예정: {next_cron_eta_kst()}"
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
    f"""
- **GitHub Actions 실행 이력** ([Actions 탭]({GITHUB_URL}/actions))
- **자동 커밋 히스토리** ([Commits]({GITHUB_URL}/commits/main))
  → `auto(collect): airkorea snapshot ...` 패턴 커밋이 매시 자동 push됨
- **데일리 자율 개발 루프 결과** ([reports/daily/]({GITHUB_URL}/tree/main/reports/daily))
"""
)

render_footer()
