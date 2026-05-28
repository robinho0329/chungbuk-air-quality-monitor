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
    GRADE_COLORS,
    GRADE_LABELS,
    load_dataframe,
    page_header,
    render_data_status,
)

# 페이지 설정 (반드시 첫 streamlit 호출이어야 함)
st.set_page_config(
    page_title="충북권 대기질 모니터",
    page_icon="🌬️",
    layout="wide",
    initial_sidebar_state="expanded",
)

page_header(
    "🌬️",
    "충북권 산업단지 대기질 모니터링",
    "오창과학·청주산업·오송바이오 + 용암동 베이스라인 — SPC 기반 자동 수집·분석",
)

df = load_dataframe()
render_data_status(df)
st.divider()

# ----------------------------------------------------------------------
# 측정소별 최신 카드
# ----------------------------------------------------------------------
st.subheader("📍 측정소별 최신 측정값")

TARGET_STATIONS = ("오창읍", "복대동", "오송읍", "용암동")
STATION_DESC = {
    "오창읍": "오창과학산업단지 (이차전지·반도체)",
    "복대동": "청주산업단지 (전자·화학)",
    "오송읍": "오송생명과학단지 (바이오·제약)",
    "용암동": "도시 베이스라인 (거주지)",
}

if df.empty:
    st.warning("아직 데이터가 없습니다.")
else:
    cols = st.columns(4)
    for col, station in zip(cols, TARGET_STATIONS, strict=False):
        sub = df[df["station_name"] == station]
        if sub.empty:
            with col:
                st.metric(station, "데이터 없음")
                continue
        latest = sub.sort_values("data_time").iloc[-1]
        grade = latest.get("khai_grade")
        grade_label = (
            GRADE_LABELS.get(int(grade), "—")
            if pd.notna(grade)
            else "—"
        )
        grade_color = (
            GRADE_COLORS.get(int(grade), "#888")
            if pd.notna(grade)
            else "#888"
        )

        with col:
            st.markdown(
                f"""
                <div style="border-left:6px solid {grade_color};
                            padding:12px 16px;
                            border-radius:6px;
                            background:rgba(255,255,255,0.03);">
                    <div style="font-size:1.1rem;font-weight:700;">{station}</div>
                    <div style="font-size:0.78rem;color:#999;margin-bottom:8px;">
                        {STATION_DESC[station]}
                    </div>
                    <div style="font-size:2.2rem;font-weight:700;color:{grade_color};">
                        {grade_label}
                    </div>
                    <div style="font-size:0.85rem;color:#bbb;">
                        통합대기지수 KHAI = {latest['khai'] if pd.notna(latest['khai']) else '—'}
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            # 표시용 측정값 표
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
                st.caption(f"⚠️ flag: {latest['flag']}")

st.divider()

# ----------------------------------------------------------------------
# 사용 안내
# ----------------------------------------------------------------------
st.subheader("📚 페이지 안내")
st.markdown(
    """
좌측 사이드바에서 다음 페이지로 이동할 수 있습니다.

- **📊 수집 모니터링** — 시간대별 수집 카운트, GitHub Actions 누적 추이
- **🌬️ 실시간 측정값** — 측정소·지표별 시계열 차트 (Plotly)
- **📐 공정능력 분석** — Cp/Cpk 게이지 (표본 ≥30 충족 시)
- **🏭 단지 비교** — 4개 측정소 통계 비교 (Boxplot, 평균·표준편차 표)

데이터는 매시 GitHub Actions가 자동 수집합니다. 컴퓨터를 꺼도 누적됩니다.
"""
)
