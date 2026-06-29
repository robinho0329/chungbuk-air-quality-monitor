"""IsolationForest 다변량 이상탐지 페이지."""

from __future__ import annotations

import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import pandas as pd  # noqa: E402
import plotly.express as px  # noqa: E402
import plotly.graph_objects as go  # noqa: E402
import streamlit as st  # noqa: E402

from dashboard._lib import (  # noqa: E402
    POLLUTANT_DISPLAY,
    load_dataframe,
    page_header,
    render_data_status,
    render_footer,
    render_insight,
    render_sidebar,
)
from src.analysis.anomaly import (  # noqa: E402
    InsufficientSampleError,
    detect_anomalies,
    detect_anomalies_by_station,
)

st.set_page_config(page_title="이상탐지", page_icon="🔍", layout="wide")
df = load_dataframe()
render_sidebar(df)

page_header(
    "🔍",
    "다변량 이상탐지 (IsolationForest)",
    "단변량 관리도가 놓치는 복합 오염 패턴을 IsolationForest로 비지도 탐지. "
    "PM10·PM2.5·O3·NO2·SO2·CO 6개 지표를 동시에 고려합니다.",
)
render_data_status(df)
st.divider()

if df.empty:
    render_footer()
    st.stop()

# 전체 측정소 요약 인사이트
try:
    results_all = detect_anomalies_by_station(df, contamination="auto")
    if results_all:
        total_anomalies = sum(r.n_anomalies for r in results_all.values())
        total_n = sum(r.n for r in results_all.values())
        worst_station = max(results_all, key=lambda s: results_all[s].anomaly_rate)
        render_insight(
            f"전체 {total_n:,}건 중 {total_anomalies}건({total_anomalies/total_n*100:.1f}%)이 "
            f"다변량 이상치로 탐지됐습니다. "
            f"이상률이 가장 높은 측정소는 {worst_station} "
            f"({results_all[worst_station].anomaly_rate*100:.1f}%)입니다."
        )
except (InsufficientSampleError, ValueError):
    pass

# ----------------------------------------------------------------------
# 옵션
# ----------------------------------------------------------------------
all_stations = sorted(df["station_name"].unique().tolist())
c1, c2, c3 = st.columns([1, 1, 1])
station = c1.selectbox("측정소", all_stations)
contamination_pct = c2.slider(
    "이상치 비율 (contamination, %)",
    min_value=1, max_value=20, value=5, step=1,
    help="전체 데이터 중 이상치로 간주할 비율. 'auto'는 알고리즘 자동 결정.",
)
use_auto = c3.checkbox("auto (알고리즘 자동)", value=False)
contamination: float | str = "auto" if use_auto else contamination_pct / 100.0

pollutant_options = [k for k in POLLUTANT_DISPLAY if k in df.columns]
selected_features = st.multiselect(
    "분석 지표 (피처)",
    pollutant_options,
    default=pollutant_options,
    format_func=lambda k: POLLUTANT_DISPLAY[k],
)

st.divider()

# ----------------------------------------------------------------------
# 계산
# ----------------------------------------------------------------------
sub = df[df["station_name"] == station].sort_values("data_time").reset_index(drop=True)

try:
    result = detect_anomalies(
        sub,
        features=selected_features if selected_features else None,
        contamination=contamination,
        random_state=42,
    )
except InsufficientSampleError as e:
    st.warning(f"표본 부족: {e}\nGitHub Actions가 매시 자동 누적 중입니다.")
    render_footer()
    st.stop()
except ValueError as e:
    st.error(f"계산 불가: {e}")
    render_footer()
    st.stop()

# ----------------------------------------------------------------------
# 요약 지표
# ----------------------------------------------------------------------
m1, m2, m3, m4 = st.columns(4)
m1.metric("분석 표본", f"{result.n:,} 건")
m2.metric("탐지 이상치", f"{result.n_anomalies} 건")
m3.metric("이상률", f"{result.anomaly_rate * 100:.1f}%")
m4.metric("사용 피처", f"{len(result.features)} 개")

if result.n_anomalies == 0:
    st.success("✅ 이상치 없음 — 다변량 이상 패턴이 탐지되지 않았습니다.")
else:
    st.warning(
        f"⚠️ {result.n_anomalies}건의 다변량 이상치가 탐지됐습니다. "
        "단일 지표로는 정상처럼 보이지만 여러 지표가 동시에 비정상 패턴을 보이는 시각입니다."
    )

st.divider()

# ----------------------------------------------------------------------
# 이상점수 시계열 플롯
# ----------------------------------------------------------------------
st.subheader("📉 이상 점수 시계열")
st.caption("점수가 낮을수록 이상치에 가깝습니다 (음수 = 이상, 양수 = 정상).")

valid_mask = sub[result.features].dropna(how="any").index
plot_df = sub.loc[valid_mask].copy().reset_index(drop=True)
plot_df["anomaly_score"] = result.scores
plot_df["is_anomaly"] = [i in result.anomaly_indices for i in range(len(plot_df))]

fig_score = go.Figure()
fig_score.add_trace(go.Scatter(
    x=plot_df["data_time"],
    y=plot_df["anomaly_score"],
    mode="lines",
    name="이상 점수",
    line=dict(color="#1f77b4", width=1.5),
))

# 이상치 시점 강조
anomaly_df = plot_df[plot_df["is_anomaly"]]
if not anomaly_df.empty:
    fig_score.add_trace(go.Scatter(
        x=anomaly_df["data_time"],
        y=anomaly_df["anomaly_score"],
        mode="markers",
        name="이상치",
        marker=dict(color="#d62728", size=9, symbol="x"),
    ))

# 임계선 (0)
fig_score.add_hline(
    y=0, line=dict(color="#ff7f0e", dash="dash", width=1),
    annotation_text="임계(0)", annotation_position="top left",
)

fig_score.update_layout(
    height=400,
    title=f"{station} · 이상 점수 (contamination={contamination})",
    xaxis_title="측정 시각",
    yaxis_title="Anomaly Score",
    hovermode="x unified",
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
)
st.plotly_chart(fig_score, use_container_width=True)

st.divider()

# ----------------------------------------------------------------------
# 이상치 산점도 (PM10 vs PM2.5)
# ----------------------------------------------------------------------
st.subheader("🔵 이상치 산점도")
scatter_cols = [f for f in result.features if f in plot_df.columns]
if len(scatter_cols) >= 2:
    sc1, sc2 = st.columns(2)
    x_col = sc1.selectbox("X축", scatter_cols, index=0, format_func=lambda k: POLLUTANT_DISPLAY.get(k, k))
    y_col = sc2.selectbox("Y축", scatter_cols, index=min(1, len(scatter_cols) - 1), format_func=lambda k: POLLUTANT_DISPLAY.get(k, k))

    plot_df["상태"] = plot_df["is_anomaly"].map({True: "이상치", False: "정상"})
    fig_sc = px.scatter(
        plot_df,
        x=x_col, y=y_col,
        color="상태",
        color_discrete_map={"이상치": "#d62728", "정상": "#aec7e8"},
        opacity=0.7,
        hover_data=["data_time"] + scatter_cols,
        title=f"{station} · {POLLUTANT_DISPLAY.get(x_col, x_col)} vs {POLLUTANT_DISPLAY.get(y_col, y_col)}",
        height=420,
    )
    fig_sc.update_traces(marker=dict(size=6))
    st.plotly_chart(fig_sc, use_container_width=True)

st.divider()

# ----------------------------------------------------------------------
# 전 측정소 이상률 비교
# ----------------------------------------------------------------------
st.subheader("📊 측정소별 이상률 비교")
st.caption("같은 contamination 파라미터로 전 측정소를 동시에 분석합니다.")

try:
    station_results = detect_anomalies_by_station(
        df,
        features=selected_features if selected_features else None,
        contamination=contamination,
        random_state=42,
    )
    if station_results:
        compare_rows = [
            {
                "측정소": s,
                "표본수": r.n,
                "이상치 수": r.n_anomalies,
                "이상률 (%)": round(r.anomaly_rate * 100, 2),
            }
            for s, r in sorted(station_results.items(), key=lambda x: -x[1].anomaly_rate)
        ]
        compare_df = pd.DataFrame(compare_rows)
        fig_bar = px.bar(
            compare_df,
            x="측정소", y="이상률 (%)",
            color="이상률 (%)",
            color_continuous_scale=["#2ca02c", "#ffd700", "#d62728"],
            text="이상률 (%)",
            title="측정소별 다변량 이상률",
            height=360,
        )
        fig_bar.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
        st.plotly_chart(fig_bar, use_container_width=True)
        st.dataframe(compare_df, use_container_width=True, hide_index=True)
except (InsufficientSampleError, ValueError):
    st.info("측정소별 비교는 표본이 충분히 쌓이면 자동으로 표시됩니다.")

st.caption(
    "📌 **해석 가이드**: IsolationForest는 '고립되기 쉬운 점'을 이상치로 탐지합니다. "
    "단변량 관리도가 각 지표를 독립 처리하는 것과 달리, 여러 오염물질의 복합 패턴을 동시에 고려합니다. "
    "탐지된 시각의 기상 조건·이벤트를 별도로 확인해 특수원인을 규명하세요."
)

render_footer()
