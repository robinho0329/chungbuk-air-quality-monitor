"""5개 측정소 단지 비교: 산단 영향군 vs 베이스라인 가설 검증."""

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
    STATION_DESC,
    STATION_GROUPS,
    date_range_filter,
    load_dataframe,
    page_header,
    render_data_status,
    render_footer,
    render_insight,
    render_sidebar,
)
from src.analysis.hypothesis_test import (  # noqa: E402
    InsufficientSampleError,
    industrial_vs_baseline,
)
from src.config import BASELINE_GROUP, INDUSTRIAL_GROUP  # noqa: E402

st.set_page_config(page_title="단지 비교", page_icon="🏭", layout="wide")
df = load_dataframe()
render_sidebar(df)

page_header(
    "🏭",
    "단지 간 비교",
    "산단 영향군(오창·복대·봉명·오송) vs 베이스라인(용암동). "
    "산단 인근 대기질이 거주지보다 나쁜가? 가설을 검증합니다.",
)
render_data_status(df)
st.divider()

if df.empty:
    render_footer()
    st.stop()

try:
    _r = industrial_vs_baseline(
        df, "pm25", STATION_GROUPS, INDUSTRIAL_GROUP, BASELINE_GROUP
    )
    _res_higher = []
    for _p in ["pm10", "pm25", "o3", "no2", "so2", "co"]:
        try:
            _rr = industrial_vs_baseline(
                df, _p, STATION_GROUPS, INDUSTRIAL_GROUP, BASELINE_GROUP
            )
            if _rr.significant and _rr.diff < 0:
                _res_higher.append(POLLUTANT_DISPLAY.get(_p, _p).split(" ")[0])
        except (InsufficientSampleError, ValueError):
            pass
    _msg = (
        f"PM2.5는 산단군이 거주지보다 평균 {_r.diff:+.1f}㎍/㎥ 높지만 효과크기는 "
        f"{_r.effect_label()}(d={_r.cohens_d:.2f})로 작습니다. "
    )
    if _res_higher:
        _msg += (
            f"반대로 {', '.join(_res_higher)}는 거주지가 더 높아(교통·난방 등 생활 연소), "
            "'산단=오염'이 아니라 오염물질별 발생원이 다릅니다."
        )
    else:
        _msg += "오염물질별로 산단·거주지 우위가 갈립니다."
    render_insight(_msg)
except (InsufficientSampleError, ValueError):
    render_insight("표본이 더 쌓이면 산단 vs 거주지 통계 검정 결과가 여기에 표시됩니다.")

# ----------------------------------------------------------------------
# 측정소 그룹 안내
# ----------------------------------------------------------------------
st.subheader("📌 단지 그룹화")
# config(STATION_GROUPS)에서 동적 생성 — 측정소 추가/변경 시 자동 반영(stale 방지)
group_table = pd.DataFrame(
    [
        {
            "측정소": _st,
            "단지/설명": STATION_DESC.get(_st, "-"),
            "그룹": ("🏭 " if _grp == INDUSTRIAL_GROUP else "🏘️ ") + _grp,
        }
        for _st, _grp in STATION_GROUPS.items()
    ]
)
st.dataframe(group_table, hide_index=True, use_container_width=True)

st.divider()

# 기간 필터 (계절성 비교)
df = date_range_filter(df, key="cmp")
if df.empty:
    st.warning("선택한 기간에 데이터가 없습니다.")
    render_footer()
    st.stop()
st.divider()

pollutant = st.selectbox(
    "비교할 지표",
    list(POLLUTANT_DISPLAY.keys()),
    format_func=lambda k: POLLUTANT_DISPLAY[k],
)

df_p = df[df[pollutant].notna()].copy()
if df_p.empty:
    st.info(f"{POLLUTANT_DISPLAY[pollutant]} 값이 모두 결측입니다.")
    render_footer()
    st.stop()

# ----------------------------------------------------------------------
# 그룹 단위 평균 비교
# ----------------------------------------------------------------------
st.subheader(f"📊 그룹 단위 {POLLUTANT_DISPLAY[pollutant]} 비교")
group_summary = (
    df_p.groupby("station_group")[pollutant]
    .agg(["count", "mean", "std", "median"])
    .round(3)
    .rename(
        columns={
            "count": "표본수",
            "mean": "평균 μ",
            "std": "표준편차 σ",
            "median": "중앙값",
        }
    )
)
group_summary.index.name = "그룹"
c1, c2 = st.columns([1, 1])
with c1:
    st.dataframe(group_summary, use_container_width=True)

with c2:
    # 그룹 평균 차이 (산단 - 베이스라인)
    if {"산단 영향군", "베이스라인"}.issubset(group_summary.index):
        san_mean = group_summary.loc["산단 영향군", "평균 μ"]
        base_mean = group_summary.loc["베이스라인", "평균 μ"]
        if base_mean > 0:
            diff_pct = (san_mean - base_mean) / base_mean * 100
            st.metric(
                "산단 - 베이스라인 평균 차이",
                f"{san_mean - base_mean:+.3f}",
                f"{diff_pct:+.1f}% vs 베이스라인",
            )
        # 선택 지표의 Welch t-test 실제 결과 (산단 vs 베이스라인)
        try:
            tt = industrial_vs_baseline(
                df_p, pollutant, STATION_GROUPS, INDUSTRIAL_GROUP, BASELINE_GROUP
            )
            st.metric(
                "Welch t-test p-value",
                f"{tt.p_value:.3g}",
                f"{'유의 (p<0.05)' if tt.significant else '비유의'} · 효과크기 d={tt.cohens_d:+.2f} ({tt.effect_label()})",
                delta_color="off",
            )
            st.caption(
                f"t={tt.t_stat:.2f}, df={tt.dof:.0f} · "
                f"{'p값은 1만 건 기준이라 자기상관(유효표본↓) 감안 시 과대평가될 수 있음' if tt.n_a > 1000 else ''}"
            )
        except (InsufficientSampleError, ValueError) as _e:
            st.caption(f"⚠️ t-test 계산 불가: 표본/분산 부족 ({_e})")

# ----------------------------------------------------------------------
# Boxplot (측정소별)
# ----------------------------------------------------------------------
st.subheader(f"📦 측정소별 {POLLUTANT_DISPLAY[pollutant]} 분포")
fig_box = px.box(
    df_p,
    x="station_name",
    y=pollutant,
    color="station_group",
    points="all",
    labels={
        "station_name": "측정소",
        pollutant: POLLUTANT_DISPLAY[pollutant],
        "station_group": "그룹",
    },
    color_discrete_map={"산단 영향군": "#d62728", "베이스라인": "#2ca02c"},
)
fig_box.update_layout(height=420)
st.plotly_chart(fig_box, use_container_width=True)

# ----------------------------------------------------------------------
# 측정소별 통계 + 베이스라인 대비
# ----------------------------------------------------------------------
st.subheader("📋 측정소별 요약 통계")
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
summary["그룹"] = [STATION_GROUPS.get(name, "?") for name in summary.index]

if "용암동" in summary.index:
    baseline_mean = summary.loc["용암동", "평균 μ"]
    if baseline_mean > 0:
        summary["베이스라인 대비"] = (
            (summary["평균 μ"] - baseline_mean) / baseline_mean * 100
        ).round(1).astype(str) + " %"

summary.index.name = "측정소"
# 그룹 순서: 산단 영향군 먼저, 베이스라인 마지막
sort_key = summary["그룹"].map({"산단 영향군": 0, "베이스라인": 1}).fillna(2)
summary = summary.assign(_sort=sort_key).sort_values("_sort").drop(columns="_sort")
st.dataframe(summary, use_container_width=True)

# ----------------------------------------------------------------------
# 시계열 overlay
# ----------------------------------------------------------------------
st.divider()
st.subheader(f"🕐 시계열 — 산단군 vs 베이스라인")
df_p["data_time"] = pd.to_datetime(df_p["data_time"])
fig_line = px.line(
    df_p.sort_values("data_time"),
    x="data_time",
    y=pollutant,
    color="station_name",
    line_dash="station_group",
    markers=True,
    labels={
        "data_time": "측정 시각 (KST)",
        pollutant: POLLUTANT_DISPLAY[pollutant],
        "station_name": "측정소",
        "station_group": "그룹",
    },
)
fig_line.update_layout(height=420, hovermode="x unified")
st.plotly_chart(fig_line, use_container_width=True)

render_footer()
