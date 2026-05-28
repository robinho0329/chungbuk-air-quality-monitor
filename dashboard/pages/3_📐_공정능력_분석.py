"""공정능력(Cp/Cpk) 분석 페이지."""

from __future__ import annotations

import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import pandas as pd  # noqa: E402
import plotly.graph_objects as go  # noqa: E402
import streamlit as st  # noqa: E402

from dashboard._lib import (  # noqa: E402
    POLLUTANT_DISPLAY,
    load_dataframe,
    page_header,
    render_data_status,
)
from src.analysis.capability import (  # noqa: E402
    InsufficientSampleError,
    MIN_SAMPLE_SIZE,
    compute_capability,
)
from src.analysis.usl_lsl import SPEC_LIMITS  # noqa: E402

st.set_page_config(page_title="공정능력 분석", page_icon="📐", layout="wide")
page_header(
    "📐",
    "공정능력 분석 (Cp / Cpk)",
    "대기환경보전법 환경기준을 USL로 사용. 표본 ≥ 30 충족 시 산출.",
)

df = load_dataframe()
render_data_status(df)
st.divider()

if df.empty:
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
# 측정소 × 오염물질 매트릭스
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
            # 폴백: daily → annual → hourly
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

matrix_df = pd.DataFrame(matrix_rows).set_index("측정소")
st.dataframe(matrix_df, use_container_width=True)

st.caption(
    "📌 값 해석: 음수=규격이탈 / <1.0=불량위험 / <1.33=마진부족 / "
    "<1.67=양호 / ≥1.67=우수 (6시그마 수준)  ·  "
    f"'n=N'은 표본 부족 (최소 {MIN_SAMPLE_SIZE}건)"
)

st.divider()

# ----------------------------------------------------------------------
# 게이지 차트 (선택된 측정소·오염물질)
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
    # Plotly 게이지
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

    # 상세 수치
    col_a, col_b, col_c, col_d = st.columns(4)
    col_a.metric("표본 수", f"{res.n}")
    col_b.metric("평균 μ", f"{res.mean:.3f}")
    col_c.metric("표준편차 σ", f"{res.std:.3f}")
    col_d.metric("Cpk", f"{res.cpk:.3f}", help=res.interpret_cpk())
    st.caption(f"USL={res.usl}, LSL={res.lsl}, Cp={res.cp:.3f}, CPU={res.cpu:.3f}, CPL={res.cpl:.3f}")
except InsufficientSampleError:
    st.warning(
        f"표본 부족: 현재 {len(values_g)}건. "
        f"Cp/Cpk 산출에는 최소 {MIN_SAMPLE_SIZE}건이 필요합니다. "
        "GitHub Actions가 매시 자동 누적 중이니 며칠 기다려주세요."
    )
except ValueError as e:
    st.error(f"계산 불가: {e}")
