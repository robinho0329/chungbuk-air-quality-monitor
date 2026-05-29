"""SPC 관리도 페이지: I-Chart / EWMA / CUSUM 시계열 관리도 + 이탈 강조."""

from __future__ import annotations

import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import plotly.graph_objects as go  # noqa: E402
import streamlit as st  # noqa: E402

from dashboard._lib import (  # noqa: E402
    POLLUTANT_DISPLAY,
    load_dataframe,
    page_header,
    render_data_status,
    render_footer,
    render_sidebar,
)
from src.analysis.control_chart import (  # noqa: E402
    InsufficientSampleError,
    cusum_chart,
    ewma_chart,
    i_chart,
)

st.set_page_config(page_title="관리도", page_icon="📈", layout="wide")
df = load_dataframe()
render_sidebar(df)

page_header(
    "📈",
    "SPC 관리도 (Control Chart)",
    "I-Chart(개별값) · EWMA · CUSUM. σ는 이동범위(MR) 기반 추정. 관리한계 이탈 시점을 자동 강조.",
)
render_data_status(df)
st.divider()

if df.empty:
    render_footer()
    st.stop()

# ----------------------------------------------------------------------
# 옵션
# ----------------------------------------------------------------------
all_stations = sorted(df["station_name"].unique().tolist())
pollutants = list(POLLUTANT_DISPLAY.keys())

c1, c2, c3 = st.columns([1, 1, 1])
station = c1.selectbox("측정소", all_stations)
pollutant = c2.selectbox(
    "지표", pollutants, format_func=lambda k: POLLUTANT_DISPLAY[k]
)
chart_type = c3.selectbox(
    "관리도 종류",
    ["I", "EWMA", "CUSUM"],
    format_func=lambda x: {
        "I": "I-Chart (개별값) — 단발성 이상치",
        "EWMA": "EWMA — 작은 평균 이동",
        "CUSUM": "CUSUM — 지속적 이동 누적",
    }[x],
)

# 시간순 정렬된 측정값
sub = (
    df[df["station_name"] == station]
    .sort_values("data_time")
    .reset_index(drop=True)
)
series = sub[pollutant]
times = sub["data_time"]

# ----------------------------------------------------------------------
# 차트별 파라미터
# ----------------------------------------------------------------------
params: dict[str, float] = {}
if chart_type == "EWMA":
    pc1, pc2 = st.columns(2)
    params["lam"] = pc1.slider("λ (가중치)", 0.05, 1.0, 0.2, 0.05,
                               help="작을수록 과거를 더 반영 → 작은 이동에 민감")
    params["L"] = pc2.slider("L (관리한계 σ배수)", 2.0, 3.5, 3.0, 0.1)
elif chart_type == "CUSUM":
    pc1, pc2 = st.columns(2)
    params["k"] = pc1.slider("k (기준이동 σ배수)", 0.0, 1.5, 0.5, 0.1,
                             help="탐지하려는 이동량의 절반(통상 0.5σ)")
    params["h"] = pc2.slider("h (결정구간 σ배수)", 3.0, 6.0, 5.0, 0.5)

st.divider()

# ----------------------------------------------------------------------
# 계산
# ----------------------------------------------------------------------
try:
    if chart_type == "I":
        res = i_chart(series)
    elif chart_type == "EWMA":
        res = ewma_chart(series, lam=params["lam"], L=params["L"])
    else:
        res = cusum_chart(series, k=params["k"], h=params["h"])
except InsufficientSampleError:
    st.warning(
        f"표본 부족: 현재 {series.dropna().shape[0]}건. "
        "관리도는 최소 2건부터 그려지나, 의미 있는 해석에는 30건 이상을 권장합니다. "
        "GitHub Actions가 매시 자동 누적 중입니다."
    )
    render_footer()
    st.stop()
except ValueError as e:
    st.error(f"계산 불가: {e}")
    render_footer()
    st.stop()

# 결측 제외 후 길이에 맞춰 시간축 정렬 (series와 res.values 길이가 다를 수 있음)
valid_mask = series.notna().to_numpy()
x_times = times[valid_mask].reset_index(drop=True)

# ----------------------------------------------------------------------
# 플롯
# ----------------------------------------------------------------------
fig = go.Figure()

# 관리한계 영역
fig.add_trace(go.Scatter(
    x=x_times, y=res.ucl, mode="lines", name="UCL",
    line=dict(color="#d62728", dash="dash", width=1),
))
fig.add_trace(go.Scatter(
    x=x_times, y=res.lcl, mode="lines", name="LCL",
    line=dict(color="#d62728", dash="dash", width=1),
))
# 중심선
fig.add_hline(
    y=res.center, line=dict(color="#2ca02c", width=1),
    annotation_text="중심선", annotation_position="top left",
)

# 통계량 본선
y_label = {
    "I": "측정값",
    "EWMA": "EWMA 통계량",
    "CUSUM": "누적합 max(C⁺, C⁻)",
}[chart_type]
fig.add_trace(go.Scatter(
    x=x_times, y=res.values, mode="lines+markers", name=y_label,
    line=dict(color="#1f77b4", width=1.5),
    marker=dict(size=5),
))

# 이탈 시점 강조
if res.violations:
    vx = [x_times.iloc[i] for i in res.violations]
    vy = [res.values[i] for i in res.violations]
    fig.add_trace(go.Scatter(
        x=vx, y=vy, mode="markers", name="이탈",
        marker=dict(color="#d62728", size=11, symbol="x"),
    ))

fig.update_layout(
    height=480,
    title=f"{station} · {POLLUTANT_DISPLAY[pollutant]} · {chart_type}-Chart",
    xaxis_title="측정 시각 (KST)",
    yaxis_title=y_label,
    hovermode="x unified",
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
)
st.plotly_chart(fig, use_container_width=True)

# ----------------------------------------------------------------------
# 요약 지표
# ----------------------------------------------------------------------
m1, m2, m3, m4 = st.columns(4)
m1.metric("표본 수", f"{res.n}")
m2.metric("추정 σ (MR)", f"{res.sigma:.4f}")
m3.metric("목표/중심", f"{res.target:.4f}")
m4.metric(
    "이탈 시점",
    f"{len(res.violations)} 건",
    delta="관리 상태" if res.is_in_control else "이탈 발생",
    delta_color="normal" if res.is_in_control else "inverse",
)

if res.is_in_control:
    st.success("✅ 모든 시점이 관리한계 이내 — 통계적 관리 상태(특수원인 신호 없음).")
else:
    st.warning(
        f"⚠️ {len(res.violations)}개 시점이 관리한계를 이탈했습니다. "
        "특수원인(설비 이상·기상 급변·통신장애 등) 점검이 필요합니다."
    )

st.caption(
    "📌 **관리도 선택 가이드**: 단발성 튐 → **I-Chart**, "
    "0.5~1.5σ 작은 평균 이동 → **EWMA/CUSUM**이 더 빨리 탐지합니다. "
    "σ는 인접 관측치 이동범위(MR̄/1.128)로 추정합니다."
)

render_footer()
