"""공정능력(Cp/Cpk) 분석 페이지: 색상 코딩 매트릭스 + 게이지."""

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
    color_cpk_cell,
    load_dataframe,
    page_header,
    render_data_status,
    render_footer,
    render_sidebar,
)
from src.analysis.capability import (  # noqa: E402
    InsufficientSampleError,
    MIN_SAMPLE_SIZE,
    compute_capability,
)
from src.analysis.usl_lsl import SPEC_LIMITS  # noqa: E402
from src.config import STATION_COORDS  # noqa: E402


def _usl_with_fallback(spec, basis: str) -> float | None:
    """선택 basis의 USL, 없으면 daily→annual→hourly 순으로 대체."""
    usl = spec.usl_for(basis)
    if usl is None:
        for fb in ("daily", "annual", "hourly"):
            usl = spec.usl_for(fb)
            if usl is not None:
                break
    return usl


def _cpk_band(cpk: float | None) -> str:
    """Cpk를 6시그마 표준 구간 라벨로 (지도 색상 카테고리)."""
    if cpk is None:
        return "표본부족"
    if cpk < 0:
        return "규격이탈(<0)"
    if cpk < 1.0:
        return "불량위험(<1.0)"
    if cpk < 1.33:
        return "마진부족(1.0~1.33)"
    if cpk < 1.67:
        return "양호(1.33~1.67)"
    return "우수(≥1.67)"


# Cpk 구간 → 색상 (게이지 밴드와 동일 팔레트)
_BAND_COLORS = {
    "규격이탈(<0)": "#d62728",
    "불량위험(<1.0)": "#ff7f0e",
    "마진부족(1.0~1.33)": "#ffd700",
    "양호(1.33~1.67)": "#90ee90",
    "우수(≥1.67)": "#2ca02c",
    "표본부족": "#9e9e9e",
}

st.set_page_config(page_title="공정능력 분석", page_icon="📐", layout="wide")
df = load_dataframe()
render_sidebar(df)

page_header(
    "📐",
    "공정능력 분석 (Cp / Cpk)",
    "대기환경보전법 환경기준을 USL로 사용. 표본 ≥ 30 충족 시 산출.",
)
render_data_status(df)
st.divider()

if df.empty:
    render_footer()
    st.stop()

# ----------------------------------------------------------------------
# 옵션
# ----------------------------------------------------------------------
col1, col2 = st.columns([1, 1])
basis = col1.selectbox(
    "USL 기준 시간",
    ["daily", "hourly", "annual"],
    format_func=lambda x: {
        "daily": "일평균 (24시간)",
        "hourly": "1시간",
        "annual": "연평균",
    }[x],
    index=0,
)
all_stations = sorted(df["station_name"].unique().tolist())
selected_stations = col2.multiselect(
    "측정소 선택", all_stations, default=all_stations
)

st.divider()

# ----------------------------------------------------------------------
# 측정소 × 오염물질 매트릭스 (색상 코딩)
# ----------------------------------------------------------------------
st.subheader("🎯 측정소 × 오염물질 Cpk 매트릭스")
pollutants = list(POLLUTANT_DISPLAY.keys())
matrix_rows: list[dict] = []
for station in selected_stations:
    sub = df[df["station_name"] == station]
    row: dict[str, str] = {"측정소": station}
    for p in pollutants:
        spec = SPEC_LIMITS[p]
        usl = spec.usl_for(basis)
        if usl is None:
            for fb in ("daily", "annual", "hourly"):
                usl = spec.usl_for(fb)
                if usl is not None:
                    break
        if usl is None:
            row[p.upper()] = "기준없음"
            continue
        values = sub[p].dropna()
        try:
            result = compute_capability(values, usl=usl, lsl=0.0)
            row[p.upper()] = f"{result.cpk:.3f}"
        except InsufficientSampleError:
            row[p.upper()] = f"n={len(values)}"
        except ValueError:
            row[p.upper()] = "오류"
    matrix_rows.append(row)

if matrix_rows:
    matrix_df = pd.DataFrame(matrix_rows).set_index("측정소")
    # Pandas Styler로 셀 색상 적용
    styled = matrix_df.style.map(color_cpk_cell)
    st.dataframe(styled, use_container_width=True)

st.caption(
    "📌 **색상 해석**: 🔴 음수 (규격이탈) · 🟠 < 1.0 (불량 위험) · "
    "🟡 1.0~1.33 (마진 부족) · 🟢 1.33~1.67 (양호) · 🟢🟢 ≥ 1.67 (우수 / 6σ)"
)
st.caption(f"'n=N'은 표본 부족 (최소 {MIN_SAMPLE_SIZE}건 필요), '기준없음'은 해당 basis USL 미정의")

st.divider()

# ----------------------------------------------------------------------
# GIS 지도: 측정소별 Cpk 분포
# ----------------------------------------------------------------------
st.subheader("🗺️ 측정소 지도 — 공정능력(Cpk) 분포")
map_pollutant = st.selectbox(
    "지도에 표시할 지표",
    pollutants,
    format_func=lambda k: POLLUTANT_DISPLAY[k],
    key="map_pollutant",
)
map_spec = SPEC_LIMITS[map_pollutant]
map_usl = _usl_with_fallback(map_spec, basis)

map_rows: list[dict] = []
for station, (lat, lon) in STATION_COORDS.items():
    if station not in selected_stations:
        continue
    vals = df[df["station_name"] == station][map_pollutant].dropna()
    cpk: float | None = None
    n = len(vals)
    mean = float(vals.mean()) if n else float("nan")
    if map_usl is not None:
        try:
            r = compute_capability(vals, usl=map_usl, lsl=0.0)
            cpk = r.cpk
            n, mean = r.n, r.mean
        except (InsufficientSampleError, ValueError):
            cpk = None
    band = _cpk_band(cpk)
    map_rows.append(
        {
            "측정소": station,
            "lat": lat,
            "lon": lon,
            "Cpk": cpk,
            "Cpk표시": "표본부족" if cpk is None else f"{cpk:.3f}",
            "등급": band,
            "표본수": n,
            "평균": round(mean, 3) if n else None,
            "라벨": f"{station}<br>Cpk={'N/A' if cpk is None else f'{cpk:.2f}'}",
        }
    )

if map_rows:
    map_df = pd.DataFrame(map_rows)
    fig_map = px.scatter_map(
        map_df,
        lat="lat",
        lon="lon",
        color="등급",
        color_discrete_map=_BAND_COLORS,
        text="측정소",
        size=[14] * len(map_df),
        size_max=18,
        hover_name="측정소",
        hover_data={
            "Cpk표시": True,
            "표본수": True,
            "평균": True,
            "lat": False,
            "lon": False,
            "등급": False,
            "Cpk": False,
        },
        zoom=10,
        height=520,
    )
    fig_map.update_traces(textposition="top center")
    fig_map.update_layout(
        map_style="open-street-map",
        margin={"l": 0, "r": 0, "t": 0, "b": 0},
        legend=dict(title="Cpk 등급", orientation="h", yanchor="bottom", y=1.01),
    )
    st.plotly_chart(fig_map, use_container_width=True)
    st.caption(
        f"📍 {POLLUTANT_DISPLAY[map_pollutant]} · {basis} 기준 USL로 측정소별 Cpk 산출. "
        "마커 색=공정능력 등급(🔴규격이탈 🟠불량위험 🟡마진부족 🟢양호/우수 ⚪표본부족). "
        "지도 타일: OpenStreetMap."
    )
else:
    st.info("표시할 측정소를 선택해주세요.")

st.divider()

# ----------------------------------------------------------------------
# 게이지 차트
# ----------------------------------------------------------------------
st.subheader("🎛️ 개별 게이지 보기")
c1, c2 = st.columns(2)
gauge_station = c1.selectbox("측정소", all_stations, key="gauge_station")
gauge_pollutant = c2.selectbox(
    "지표",
    pollutants,
    format_func=lambda k: POLLUTANT_DISPLAY[k],
    key="gauge_pollutant",
)

sub_g = df[df["station_name"] == gauge_station]
spec = SPEC_LIMITS[gauge_pollutant]
usl = spec.usl_for(basis)
if usl is None:
    for fb in ("daily", "annual", "hourly"):
        usl = spec.usl_for(fb)
        if usl is not None:
            break

values_g = sub_g[gauge_pollutant].dropna()
try:
    res = compute_capability(values_g, usl=usl or 1.0, lsl=0.0)
    fig = go.Figure(
        go.Indicator(
            mode="gauge+number",
            value=res.cpk,
            domain={"x": [0, 1], "y": [0, 1]},
            title={
                "text": f"{gauge_station} · {POLLUTANT_DISPLAY[gauge_pollutant]}<br>"
                f"<span style='font-size:0.8em;color:#888'>Cpk · {res.interpret_cpk()}</span>"
            },
            gauge={
                "axis": {"range": [-1, 3]},
                "bar": {"color": "#1f77b4"},
                "steps": [
                    {"range": [-1, 0], "color": "#d62728"},
                    {"range": [0, 1.0], "color": "#ff7f0e"},
                    {"range": [1.0, 1.33], "color": "#ffd700"},
                    {"range": [1.33, 1.67], "color": "#90ee90"},
                    {"range": [1.67, 3], "color": "#2ca02c"},
                ],
                "threshold": {
                    "line": {"color": "white", "width": 3},
                    "thickness": 0.75,
                    "value": res.cpk,
                },
            },
        )
    )
    fig.update_layout(height=400)
    st.plotly_chart(fig, use_container_width=True)

    col_a, col_b, col_c, col_d = st.columns(4)
    col_a.metric("표본 수", f"{res.n}")
    col_b.metric("평균 μ", f"{res.mean:.3f}")
    col_c.metric("표준편차 σ", f"{res.std:.3f}")
    col_d.metric("Cpk", f"{res.cpk:.3f}", help=res.interpret_cpk())
    st.caption(
        f"USL={res.usl}, LSL={res.lsl}, Cp={res.cp:.3f}, CPU={res.cpu:.3f}, CPL={res.cpl:.3f}"
    )
except InsufficientSampleError:
    st.warning(
        f"표본 부족: 현재 {len(values_g)}건. "
        f"Cp/Cpk 산출에는 최소 {MIN_SAMPLE_SIZE}건이 필요합니다. "
        "GitHub Actions가 매시 자동 누적 중이니 며칠 기다려주세요."
    )
except ValueError as e:
    st.error(f"계산 불가: {e}")

render_footer()
