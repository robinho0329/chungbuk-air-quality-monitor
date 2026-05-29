"""홈 화면: 4개 측정소 현재 상태 + KPI.

실행:
    uv run streamlit run dashboard/app.py
"""

from __future__ import annotations

import sys
from pathlib import Path

# streamlit은 실행 파일 디렉토리만 sys.path에 추가하므로
# 프로젝트 루트를 명시적으로 추가해야 `dashboard._lib` import 가능
_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

from dashboard._lib import (  # noqa: E402
    GRADE_BG_GRADIENT,
    GRADE_COLORS,
    GRADE_LABELS,
    STATION_DESC,
    fmt_kst,
    load_dataframe,
    page_header,
    render_data_status,
    render_footer,
    render_insight,
    render_sidebar,
)
from src.config import TARGET_STATIONS  # noqa: E402

# 페이지 설정 (반드시 첫 streamlit 호출이어야 함)
st.set_page_config(
    page_title="충북권 대기질 모니터",
    page_icon="🌬️",
    layout="wide",
    initial_sidebar_state="expanded",
)

df = load_dataframe()
render_sidebar(df)

page_header(
    "🌬️",
    "충북권 산업단지 대기질 모니터링",
    "오창과학·청주산업·오송바이오 + 용암동 베이스라인 — SPC 기반 자동 수집·분석",
)

render_data_status(df)
st.divider()

# ----------------------------------------------------------------------
# 측정소별 최신 카드 (등급별 그라데이션 + 측정 시각)
# ----------------------------------------------------------------------
if not df.empty and df["pm25"].notna().any():
    _m = df.groupby("station_name")["pm25"].mean()
    _piv = df.pivot_table(index="data_time", columns="station_name", values="pm25")
    _spatial = _piv.std(axis=1).mean()  # 같은 시각 측정소 간 편차
    _temporal = _piv.mean(axis=1).std()  # 시간에 따른 변동
    _ratio = _temporal / _spatial if _spatial else float("nan")
    render_insight(
        f"PM2.5 측정소별 평균은 {_m.min():.0f}~{_m.max():.0f}㎍/㎥로 편차가 작고"
        f"(최고 {_m.idxmax()} {_m.max():.0f}, 최저 {_m.idxmin()} {_m.min():.0f}), "
        f"같은 시각 측정소 간 편차보다 시간에 따른 변동이 약 {_ratio:.1f}배 큽니다. "
        f"→ 농도를 가르는 건 측정소(위치)가 아니라 시간·기상입니다."
    )

st.subheader("📍 측정소별 최신 측정값")

if df.empty:
    st.warning("아직 데이터가 없습니다.")
else:
    cols = st.columns(len(TARGET_STATIONS))
    for col, station in zip(cols, TARGET_STATIONS, strict=False):
        sub = df[df["station_name"] == station]
        if sub.empty:
            with col:
                st.markdown(
                    f"""
                    <div style="padding:14px;border-radius:8px;
                                background:rgba(150,150,150,0.1);
                                border:1px dashed #888;">
                        <div style="font-size:1.1rem;font-weight:700;">{station}</div>
                        <div style="font-size:0.78rem;color:#999;margin-bottom:8px;">
                            {STATION_DESC[station]}
                        </div>
                        <div style="font-size:1.5rem;color:#888;">데이터 없음</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
                continue

        sub_sorted = sub.sort_values("data_time")
        newest = sub_sorted.iloc[-1]
        # 최신 레코드의 모든 오염물질이 결측(통신장애 등)이면 직전 실측 행을 대신 표시.
        # (복대동은 khai만 null이고 PM 값은 있는 경우가 많아 개별 지표 기준으로 판단)
        _pol_cols = ["pm10", "pm25", "o3", "no2", "so2", "co"]
        has_data = sub_sorted[_pol_cols].notna().any(axis=1)
        valid = sub_sorted[has_data]
        latest = valid.iloc[-1] if not valid.empty else newest
        # 표시 실측값이 최신 시각보다 오래됐으면 지연 시간(시간) 계산.
        stale_hours = 0
        if pd.notna(latest["data_time"]) and pd.notna(newest["data_time"]):
            stale_hours = int(
                (newest["data_time"] - latest["data_time"]).total_seconds() // 3600
            )
        grade = latest.get("khai_grade")
        grade_label = (
            GRADE_LABELS.get(int(grade), "—") if pd.notna(grade) else "—"
        )
        grade_color = (
            GRADE_COLORS.get(int(grade), "#888") if pd.notna(grade) else "#888"
        )
        bg = (
            GRADE_BG_GRADIENT.get(int(grade), "rgba(150,150,150,0.05)")
            if pd.notna(grade)
            else "rgba(150,150,150,0.05)"
        )

        with col:
            st.markdown(
                f"""
                <div style="padding:14px;border-radius:8px;
                            background:{bg};
                            border-left:6px solid {grade_color};">
                    <div style="font-size:1.1rem;font-weight:700;">{station}</div>
                    <div style="font-size:0.78rem;color:#888;margin-bottom:6px;">
                        {STATION_DESC[station]}
                    </div>
                    <div style="font-size:2rem;font-weight:800;color:{grade_color};line-height:1.1;">
                        {grade_label}
                    </div>
                    <div style="font-size:0.85rem;color:#999;margin-top:4px;">
                        KHAI {latest['khai'] if pd.notna(latest['khai']) else '—'}
                    </div>
                    <div style="font-size:0.72rem;color:#aaa;margin-top:8px;">
                        🕐 {fmt_kst(latest['data_time'])}
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            display_rows = []
            for key, label in [
                ("pm10", "PM10"),
                ("pm25", "PM2.5"),
                ("o3", "O3"),
                ("no2", "NO2"),
                ("so2", "SO2"),
                ("co", "CO"),
            ]:
                v = latest.get(key)
                display_rows.append(
                    {"항목": label, "값": "—" if pd.isna(v) else v}
                )
            st.dataframe(
                pd.DataFrame(display_rows),
                hide_index=True,
                use_container_width=True,
            )

            if stale_hours > 0:
                flag_txt = (
                    f" ({newest['flag']})"
                    if pd.notna(newest.get("flag")) and newest["flag"]
                    else ""
                )
                st.caption(
                    f"⚠️ 최신 {stale_hours}시간 결측{flag_txt} — "
                    f"직전 실측({fmt_kst(latest['data_time'], with_tz=False)}) 표시"
                )
            elif pd.notna(latest.get("flag")) and latest["flag"]:
                st.caption(f"⚠️ 결측 사유: {latest['flag']}")
            # 개별 지표는 있으나 통합지수(KHAI)만 미제공인 경우 안내 (복대동 등)
            elif pd.isna(latest.get("khai")):
                st.caption("ℹ️ 통합지수(KHAI) 미제공 — 개별 지표는 정상 수집 중")

st.divider()

# ----------------------------------------------------------------------
# 페이지 안내
# ----------------------------------------------------------------------
st.subheader("📚 페이지 안내")
col_a, col_b = st.columns(2)
with col_a:
    st.markdown(
        """
- **📊 수집 모니터링** — 시간대별 수집 카운트, 24h 성공률, GHA 이력
- **🌬️ 실시간 측정값** — 측정소·지표 시계열 + 환경기준선 표시
        """
    )
with col_b:
    st.markdown(
        """
- **📐 공정능력 분석** — Cp/Cpk 매트릭스(색상 코딩) + 게이지
- **🏭 단지 비교** — 산단 영향군 vs 베이스라인 통계 검증
        """
    )

render_footer()
