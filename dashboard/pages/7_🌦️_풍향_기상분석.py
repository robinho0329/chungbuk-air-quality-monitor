"""풍향·기상 결합 분석 페이지 (Phase 4).

기상청 ASOS 데이터가 수집된 경우: 오염장미, 산단 방위 검정, 기상 회귀.
기상 데이터 미수집 시: 안내 메시지 + WEATHER_API_KEY 설정 가이드.
"""

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
from src.analysis.wind_regression import (  # noqa: E402
    SECTORS_8,
    InsufficientSampleError,
    bearing,
    directional_test,
    join_air_weather,
    pollution_rose,
    weather_regression,
)
from src.config import INDUSTRIAL_SOURCES, STATION_COORDS  # noqa: E402
from src.storage.database import query_weather  # noqa: E402

st.set_page_config(page_title="풍향·기상 분석", page_icon="🌦️", layout="wide")
df_air = load_dataframe()
render_sidebar(df_air)

page_header(
    "🌦️",
    "풍향·기상 결합 분석 (Phase 4)",
    "기상청 ASOS(청주 지점)와 대기질을 시간 단위로 조인. "
    "오염장미, 산단 방위 검정(Welch t-test), 기상 회귀(OLS)로 배출원 방향을 실증합니다.",
)
render_data_status(df_air)
st.divider()

if df_air.empty:
    render_footer()
    st.stop()

# ----------------------------------------------------------------------
# 기상 데이터 로드
# ----------------------------------------------------------------------
@st.cache_data(ttl=60, show_spinner=False)
def load_weather_df() -> pd.DataFrame:
    """기상 관측 데이터를 DataFrame으로 로드 (60초 캐시)."""
    rows = query_weather()
    if not rows:
        return pd.DataFrame()
    records = [
        {
            "obs_time": r.obs_time,
            "ta": r.ta,
            "hm": r.hm,
            "ws": r.ws,
            "wd": r.wd,
            "rn": r.rn,
        }
        for r in rows
    ]
    df = pd.DataFrame.from_records(records)
    df["obs_time"] = pd.to_datetime(df["obs_time"])
    return df


df_wx = load_weather_df()

# ----------------------------------------------------------------------
# 날짜 범위 필터 (대기질 데이터 범위에 맞춤)
# ----------------------------------------------------------------------
if not df_wx.empty and not df_air.empty:
    air_min = df_air["data_time"].min().date()
    air_max = df_air["data_time"].max().date()
    wx_min = df_wx["obs_time"].min().date()
    wx_max = df_wx["obs_time"].max().date()
    date_min = max(air_min, wx_min)
    date_max = min(air_max, wx_max)

    if date_min <= date_max:
        st.markdown("**📅 분석 기간**")
        fc1, fc2 = st.columns(2)
        sel_start = fc1.date_input("시작일", value=date_min, min_value=date_min, max_value=date_max, key="wx_start")
        sel_end = fc2.date_input("종료일", value=date_max, min_value=date_min, max_value=date_max, key="wx_end")
        if sel_start > sel_end:
            sel_start, sel_end = sel_end, sel_start

        df_air = df_air[
            (df_air["data_time"].dt.date >= sel_start) &
            (df_air["data_time"].dt.date <= sel_end)
        ]
        df_wx = df_wx[
            (df_wx["obs_time"].dt.date >= sel_start) &
            (df_wx["obs_time"].dt.date <= sel_end)
        ]
        st.caption(f"선택 기간: {sel_start} ~ {sel_end} | 대기질 {len(df_air):,}건 / 기상 {len(df_wx):,}건")

if df_wx.empty:
    st.info(
        "📡 기상청 ASOS 데이터가 아직 수집되지 않았습니다.\n\n"
        "**설정 방법:**\n"
        "1. [공공데이터포털](https://www.data.go.kr)에서 "
        "'기상청 지상(종관, ASOS) 시간자료' 활용신청\n"
        "2. 발급받은 Decoding 키를 GitHub Secrets → `WEATHER_API_KEY`에 등록\n"
        "3. GitHub Actions `collect.yml`이 매시 `collect_weather.py`를 자동 실행합니다.\n\n"
        "키가 등록되면 다음 수집 사이클부터 자동으로 누적됩니다."
    )
    render_footer()
    st.stop()

# 대기질 + 기상 조인
df_joined = join_air_weather(df_air, df_wx)

if df_joined.empty:
    st.warning(
        "대기질·기상 조인 결과가 없습니다. 두 데이터의 시간 범위가 겹치지 않을 수 있습니다. "
        "기상 수집이 시작된 이후 시각부터 분석이 가능합니다."
    )
    render_footer()
    st.stop()

st.success(
    f"✅ 기상 데이터 {len(df_wx):,}건 수집 완료. "
    f"대기질과 조인된 시각: {len(df_joined):,}건 "
    f"({df_joined['data_time'].min().strftime('%Y-%m-%d')} ~ "
    f"{df_joined['data_time'].max().strftime('%Y-%m-%d')})"
)

# 인사이트
try:
    rose_all = pollution_rose(df_joined, "pm25")
    if rose_all:
        max_sector = max(rose_all, key=rose_all.get)
        render_insight(
            f"전체 PM2.5 오염장미: {max_sector} 방향 바람일 때 평균 농도가 가장 높습니다 "
            f"({rose_all[max_sector]:.1f} ㎍/㎥). "
            "이 방향에 주요 배출원이 있는지 산단 위치와 비교해보세요."
        )
except (InsufficientSampleError, ValueError):
    pass

st.divider()

# ----------------------------------------------------------------------
# 옵션
# ----------------------------------------------------------------------
all_stations = sorted(df_joined["station_name"].unique().tolist())
c1, c2 = st.columns(2)
station = c1.selectbox("측정소", all_stations)
pollutant = c2.selectbox(
    "오염물질",
    [k for k in POLLUTANT_DISPLAY if k in df_joined.columns],
    format_func=lambda k: POLLUTANT_DISPLAY[k],
)

sub = df_joined[df_joined["station_name"] == station].reset_index(drop=True)

st.divider()

# ----------------------------------------------------------------------
# 1. 오염장미
# ----------------------------------------------------------------------
st.subheader("🌹 오염장미 (Pollution Rose)")
st.caption("풍향 8방위별 평균 농도. 특정 방위에서 바람이 불 때 농도가 높으면 그 방향에 배출원이 있을 가능성이 높습니다.")

try:
    rose = pollution_rose(sub, pollutant)
    if rose:
        sectors_ordered = SECTORS_8
        values_ordered = [rose.get(s, 0.0) for s in sectors_ordered]

        fig_rose = go.Figure(go.Barpolar(
            r=values_ordered,
            theta=sectors_ordered,
            name=POLLUTANT_DISPLAY.get(pollutant, pollutant),
            marker_color=[
                f"rgba(31,119,180,{min(0.3 + v / max(values_ordered) * 0.7, 1.0)})"
                for v in values_ordered
            ],
        ))
        fig_rose.update_layout(
            height=420,
            title=f"{station} · {POLLUTANT_DISPLAY.get(pollutant, pollutant)} 오염장미",
            polar=dict(radialaxis=dict(showticklabels=True, tickfont=dict(size=10))),
        )
        st.plotly_chart(fig_rose, use_container_width=True)

        max_s = max(rose, key=rose.get)
        st.caption(
            f"📌 최고 농도 방위: **{max_s}** ({rose[max_s]:.2f}) "
            f"/ 최저: **{min(rose, key=rose.get)}** ({min(rose.values()):.2f})"
        )
    else:
        st.info("풍향 데이터 부족으로 오염장미를 생성할 수 없습니다.")
except ValueError as e:
    st.warning(f"오염장미 계산 불가: {e}")

st.divider()

# ----------------------------------------------------------------------
# 2. 산단 방위 검정
# ----------------------------------------------------------------------
st.subheader("🏭 산단 방위 검정 (Welch t-test)")
st.caption(
    "측정소 기준 산단 방향에서 부는 바람일 때 농도가 유의하게 높은지 검정합니다. "
    "H4 가설: '산단 방위 바람이 불 때 오염이 더 심하다'를 통계적으로 검증합니다."
)

station_coord = STATION_COORDS.get(station)
if station_coord:
    source_options = list(INDUSTRIAL_SOURCES.items())
    source_labels = [f"{name} ({lat:.3f}, {lon:.3f})" for name, (lat, lon) in source_options]
    selected_source_idx = st.selectbox(
        "배출원 (산단) 선택",
        range(len(source_options)),
        format_func=lambda i: source_labels[i],
    )
    source_name, source_coord = source_options[selected_source_idx]

    src_bearing = bearing(station_coord[0], station_coord[1], source_coord[0], source_coord[1])
    st.info(f"📐 {station} 기준 {source_name} 방위: **{src_bearing:.1f}°** (0°=북, 시계방향)")

    sector_width = st.slider("방위 섹터 너비 (±도)", min_value=15, max_value=90, value=45, step=15)

    try:
        dir_res = directional_test(sub, pollutant, source_bearing=src_bearing, sector_width=sector_width)

        d1, d2, d3, d4 = st.columns(4)
        d1.metric("산단 방위 표본", f"{dir_res.n_in}건")
        d2.metric("산단 방위 평균", f"{dir_res.mean_in:.3f}")
        d3.metric("그 외 평균", f"{dir_res.mean_out:.3f}")
        d4.metric(
            "유의성 (p)",
            f"{dir_res.p_value:.4f}",
            delta="유의 (p<0.05)" if dir_res.significant else "비유의",
            delta_color="inverse" if dir_res.significant else "normal",
        )

        st.metric("Cohen's d (효과 크기)", f"{dir_res.cohens_d:.3f}")

        if dir_res.significant:
            st.success(f"✅ {dir_res.interpret()}")
        else:
            st.info(f"ℹ️ {dir_res.interpret()}")

    except InsufficientSampleError as e:
        st.warning(f"표본 부족: {e}")
    except ValueError as e:
        st.warning(f"검정 불가: {e}")
else:
    st.info(f"'{station}' 측정소 좌표 정보가 없습니다.")

st.divider()

# ----------------------------------------------------------------------
# 3. 기상 회귀
# ----------------------------------------------------------------------
st.subheader("📈 기상 회귀 분석 (OLS)")
st.caption(
    "농도 ~ 풍속(ws)·기온(ta)·습도(hm) 다중선형회귀. "
    "어떤 기상 요인이 농도 변동을 얼마나 설명하는지 확인합니다."
)

predictor_options = {
    "ws": "풍속 (m/s)",
    "ta": "기온 (℃)",
    "hm": "습도 (%)",
}
available_predictors = [p for p in predictor_options if p in sub.columns]
selected_predictors = st.multiselect(
    "예측변수 선택",
    available_predictors,
    default=available_predictors,
    format_func=lambda k: predictor_options[k],
)

if selected_predictors:
    try:
        reg_res = weather_regression(sub, pollutant, predictors=tuple(selected_predictors))

        r1, r2 = st.columns(2)
        r1.metric("R² (설명력)", f"{reg_res.r2:.4f}", help="1.0에 가까울수록 기상이 농도를 잘 설명")
        r2.metric("표본 수", f"{reg_res.n:,}건")

        coef_rows = [
            {
                "변수": predictor_options.get(k, k),
                "계수": round(v, 4),
                "방향": "↑ 농도 증가" if v > 0 else "↓ 농도 감소",
            }
            for k, v in reg_res.coef.items()
        ]
        coef_rows.append({"변수": "절편", "계수": round(reg_res.intercept, 4), "방향": ""})
        st.dataframe(pd.DataFrame(coef_rows), use_container_width=True, hide_index=True)

        st.caption(
            f"📌 R²={reg_res.r2:.4f}: 선택한 기상 변수가 {pollutant.upper()} 농도 분산의 "
            f"{reg_res.r2*100:.1f}%를 설명합니다. "
            "나머지는 배출원 가동률·교통량·화학반응 등 미포함 요인의 영향입니다."
        )

        # 풍속 vs 농도 산점도 (OLS 트렌드라인 직접 계산)
        if "ws" in sub.columns and pollutant in sub.columns and "ws" in reg_res.coef:
            plot_sub = sub[[pollutant, "ws"]].dropna()
            if not plot_sub.empty:
                import numpy as _np
                ws_range = _np.linspace(plot_sub["ws"].min(), plot_sub["ws"].max(), 50)
                trend_y = reg_res.intercept + reg_res.coef["ws"] * ws_range

                fig_ws = go.Figure()
                fig_ws.add_trace(go.Scatter(
                    x=plot_sub["ws"], y=plot_sub[pollutant],
                    mode="markers", name="측정값",
                    marker=dict(color="#aec7e8", opacity=0.5, size=5),
                ))
                fig_ws.add_trace(go.Scatter(
                    x=ws_range, y=trend_y,
                    mode="lines", name="OLS 트렌드",
                    line=dict(color="#d62728", width=2),
                ))
                fig_ws.update_layout(
                    height=360,
                    title=f"{station} · 풍속 vs {POLLUTANT_DISPLAY.get(pollutant, pollutant)}",
                    xaxis_title="풍속 (m/s)",
                    yaxis_title=POLLUTANT_DISPLAY.get(pollutant, pollutant),
                    hovermode="closest",
                )
                st.plotly_chart(fig_ws, use_container_width=True)

    except InsufficientSampleError as e:
        st.warning(f"표본 부족: {e}")
    except ValueError as e:
        st.warning(f"회귀 계산 불가: {e}")
else:
    st.info("예측변수를 최소 1개 선택하세요.")

render_footer()
