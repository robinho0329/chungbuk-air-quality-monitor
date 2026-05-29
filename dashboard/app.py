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

        latest = sub.sort_values("data_time").iloc[-1]
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

            if pd.notna(latest.get("flag")) and latest["flag"]:
                st.caption(f"⚠️ 결측 사유: {latest['flag']}")

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
