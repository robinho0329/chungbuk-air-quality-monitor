"""대시보드 공통 헬퍼.

여러 페이지에서 재사용하는 데이터 로드·캐싱·스타일 유틸 + 사이드바·푸터 컴포넌트.
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# 프로젝트 루트를 sys.path에 추가 (streamlit run dashboard/app.py 대응)
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

from src.config import STATION_GROUPS, TARGET_STATIONS  # noqa: E402
from src.storage.database import query_all  # noqa: E402

# ----------------------------------------------------------------------
# 시간대 / 라벨 상수
# ----------------------------------------------------------------------
KST = timezone(timedelta(hours=9))
LIVE_DEMO_URL = "https://chungbuk-air-quality-monitor-dfusndrdtukcwk9rog6wzt.streamlit.app/"
GITHUB_URL = "https://github.com/robinho0329/chungbuk-air-quality-monitor"

# 등급별 색상 (대기환경 표준)
GRADE_COLORS: dict[int, str] = {
    1: "#1f77b4",  # 좋음 (파랑)
    2: "#2ca02c",  # 보통 (초록)
    3: "#ff7f0e",  # 나쁨 (주황)
    4: "#d62728",  # 매우나쁨 (빨강)
}

# 등급별 배경 그라데이션 (홈 카드용)
GRADE_BG_GRADIENT: dict[int, str] = {
    1: "linear-gradient(135deg, rgba(31,119,180,0.25), rgba(31,119,180,0.05))",
    2: "linear-gradient(135deg, rgba(44,160,44,0.25), rgba(44,160,44,0.05))",
    3: "linear-gradient(135deg, rgba(255,127,14,0.25), rgba(255,127,14,0.05))",
    4: "linear-gradient(135deg, rgba(214,39,40,0.25), rgba(214,39,40,0.05))",
}

GRADE_LABELS: dict[int, str] = {
    1: "좋음",
    2: "보통",
    3: "나쁨",
    4: "매우나쁨",
}

POLLUTANT_DISPLAY: dict[str, str] = {
    "pm10": "PM10 (㎍/㎥)",
    "pm25": "PM2.5 (㎍/㎥)",
    "o3": "오존 O3 (ppm)",
    "no2": "이산화질소 NO2 (ppm)",
    "so2": "아황산가스 SO2 (ppm)",
    "co": "일산화탄소 CO (ppm)",
}

# 단지 그룹화 (가설 검증용)
# STATION_GROUPS는 src.config에서 import (단일 진실원천). 위 import 참조.

STATION_DESC: dict[str, str] = {
    "오창읍": "오창과학단지 (이차전지·반도체)",
    "복대동": "청주산업단지 산단육거리 (SK하이닉스 권역, 통신장애 잦음)",
    "봉명동": "청주산업단지 봉명동 (SK하이닉스 권역, 복대동 대체 커버)",
    "오송읍": "오송생명과학단지 (바이오·제약)",
    "용암동": "도시 베이스라인 (거주지)",
}


# ----------------------------------------------------------------------
# 시간 포맷
# ----------------------------------------------------------------------
def fmt_kst(dt: datetime | pd.Timestamp | None, with_tz: bool = True) -> str:
    """datetime을 KST 문자열로 변환.

    DB의 data_time/created_at은 모두 KST 기반(에어코리아 응답이 KST이고
    GHA runner가 보낸 시각도 우리는 KST로 가정)이지만 tzinfo가 None이라
    여기서 명시적으로 KST 라벨을 붙인다.
    """
    if dt is None or (isinstance(dt, float) and pd.isna(dt)):
        return "—"
    if isinstance(dt, pd.Timestamp):
        dt = dt.to_pydatetime()
    s = dt.strftime("%Y-%m-%d %H:%M")
    return f"{s} KST" if with_tz else s


def now_kst() -> datetime:
    """현재 KST 시각."""
    return datetime.now(tz=KST)


# 외부 스케줄러(cron-job.org)가 트리거하는 분(分). 에어코리아가 정각 데이터를
# 몇~십몇 분 늦게(가변) 공개하므로, 시간당 3회(:15/:35/:55) 폴링해 지연 공개분을 잡는다.
# ※ 폴링 빈도일 뿐 데이터 해상도(1시간)와는 무관 — 같은 시각은 UNIQUE+INSERT OR IGNORE로 1건만 유지.
_COLLECT_MINUTES = (15, 35, 55)
# 트리거 → Actions 실행·커밋·재배포까지 걸리는 여유(분).
_COLLECT_BUFFER_MIN = 5


def next_cron_eta_kst() -> str:
    """다음 자동 수집 반영 예정 시각 (KST). cron-job.org가 매시 :15/:35/:55 트리거."""
    now = now_kst()
    buffered = [m + _COLLECT_BUFFER_MIN for m in _COLLECT_MINUTES]
    for minute in buffered:
        if now.minute < minute:
            eta = now.replace(minute=minute, second=0, microsecond=0)
            break
    else:
        eta = (now + timedelta(hours=1)).replace(
            minute=buffered[0], second=0, microsecond=0
        )
    return eta.strftime("%H:%M KST")


# ----------------------------------------------------------------------
# 데이터 로드 (캐시)
# ----------------------------------------------------------------------
@st.cache_data(ttl=60, show_spinner=False)
def load_dataframe() -> pd.DataFrame:
    """전체 측정 데이터를 DataFrame으로 로드한다 (60초 캐시)."""
    rows = query_all()
    if not rows:
        return pd.DataFrame()
    records = [
        {
            "station_name": r.station_name,
            "data_time": r.data_time,
            "created_at": r.created_at,
            "pm10": r.pm10,
            "pm25": r.pm25,
            "o3": r.o3,
            "no2": r.no2,
            "so2": r.so2,
            "co": r.co,
            "khai": r.khai,
            "pm10_grade": r.pm10_grade,
            "pm25_grade": r.pm25_grade,
            "khai_grade": r.khai_grade,
            "flag": r.flag,
        }
        for r in rows
    ]
    df = pd.DataFrame.from_records(records)
    df["data_time"] = pd.to_datetime(df["data_time"])
    df["station_group"] = df["station_name"].map(STATION_GROUPS)
    return df


def date_range_filter(df: pd.DataFrame, *, key: str = "dr") -> pd.DataFrame:
    """기간 선택 UI를 그리고 선택 구간으로 필터링한 DataFrame을 반환한다.

    프리셋(최근 7/30일·전체) + 시작/종료일 직접 선택. 계절성 등 기간 분석용.

    Args:
        df: data_time(datetime) 컬럼을 가진 DataFrame.
        key: 위젯 중복 방지용 고유 키(페이지별로 다르게).
    """
    if df.empty:
        return df
    dmin = df["data_time"].min().date()
    dmax = df["data_time"].max().date()

    preset = st.radio(
        "기간",
        ["전체", "최근 7일", "최근 30일", "직접 설정"],
        horizontal=True,
        key=f"{key}_preset",
    )
    if preset == "전체":
        start, end = dmin, dmax
    elif preset == "최근 7일":
        start, end = max(dmin, dmax - timedelta(days=6)), dmax
    elif preset == "최근 30일":
        start, end = max(dmin, dmax - timedelta(days=29)), dmax
    else:  # 직접 설정
        c1, c2 = st.columns(2)
        start = c1.date_input(
            "시작일", value=dmin, min_value=dmin, max_value=dmax, key=f"{key}_s"
        )
        end = c2.date_input(
            "종료일", value=dmax, min_value=dmin, max_value=dmax, key=f"{key}_e"
        )
        if start > end:
            start, end = end, start

    mask = (df["data_time"].dt.date >= start) & (df["data_time"].dt.date <= end)
    out = df[mask]
    n_days = (end - start).days + 1
    st.caption(
        f"📅 {start} ~ {end} ({n_days}일) · {len(out):,}건 "
        f"· 측정소당 평균 {len(out) // max(df['station_name'].nunique(), 1):,}건"
    )
    return out


# ----------------------------------------------------------------------
# 사이드바 & 푸터 (모든 페이지 공통)
# ----------------------------------------------------------------------
def render_sidebar(df: pd.DataFrame | None = None) -> None:
    """모든 페이지가 공유하는 사이드바 정보."""
    with st.sidebar:
        st.markdown("### 🌬️ 충북 대기질 모니터")
        st.caption("산단 영향 SPC 분석 시스템")
        st.divider()

        if df is not None and not df.empty:
            last_time = df["data_time"].max()
            last_created = df["created_at"].max()
            st.markdown("**📡 자동 수집 상태**")
            st.write(f"마지막 측정: `{fmt_kst(last_time)}`")
            st.write(f"마지막 DB 저장: `{fmt_kst(last_created)}`")
            st.write(f"다음 자동 수집: `{next_cron_eta_kst()}`")
            st.divider()

        st.markdown("**🔗 링크**")
        st.markdown(f"[📂 GitHub 레포]({GITHUB_URL})")
        st.markdown(f"[🤖 Actions]({GITHUB_URL}/actions)")
        st.divider()
        st.caption("매시 GitHub Actions가 자동 수집합니다.\nPC 꺼져 있어도 누적됩니다.")


def render_footer() -> None:
    """모든 페이지 하단 공통 푸터."""
    st.divider()
    st.caption(
        f"⚙️ 매시 :15 UTC ({next_cron_eta_kst()} 예정) GitHub Actions 자동 수집 · "
        f"[코드]({GITHUB_URL}) · "
        f"QC/API 직무 포트폴리오 (SPC + 6시그마 DMAIC)"
    )


# ----------------------------------------------------------------------
# 페이지 헤더 + 데이터 현황
# ----------------------------------------------------------------------
def render_data_status(df: pd.DataFrame) -> None:
    """페이지 상단에 누적 데이터 현황을 안내한다."""
    if df.empty:
        st.warning(
            "🌬️ 누적 데이터가 없습니다. GitHub Actions 첫 수집이 완료될 때까지 잠시 기다려주세요."
        )
        return
    total = len(df)
    stations = df["station_name"].nunique()
    last_time = df["data_time"].max()
    min_per_station = df.groupby("station_name").size().min()
    progress = min(min_per_station / 30.0, 1.0)

    cols = st.columns(4)
    cols[0].metric("총 누적", f"{total:,} 건")
    cols[1].metric("측정소", f"{stations} / {len(TARGET_STATIONS)} 곳")
    cols[2].metric("마지막 측정", fmt_kst(last_time, with_tz=False), help="KST 기준")
    cols[3].metric(
        "Cp/Cpk 준비",
        f"{int(progress * 100)}%",
        help=f"가장 적은 측정소 기준 {min_per_station}/30건",
    )

    if min_per_station < 30:
        st.info(
            f"📈 Cp/Cpk 분석은 측정소당 30건 이상에서 의미가 있습니다 "
            f"(현재 최소 {min_per_station}건). GitHub Actions가 매시 자동 누적 중."
        )


def page_header(emoji: str, title: str, description: str = "") -> None:
    """페이지 상단 헤더 일관 적용."""
    st.title(f"{emoji} {title}")
    if description:
        st.caption(description)


# ----------------------------------------------------------------------
# 24h 수집 성공률 KPI
# ----------------------------------------------------------------------
def compute_24h_success_rate(df: pd.DataFrame) -> tuple[int, int, float]:
    """최근 24시간 측정소별 수집 성공률.

    Returns:
        (받은 시각 수, 기대 시각 수, 성공률).
        기대 시각 수 = 24 × 측정소 수. 복대동은 통신장애여도 행(결측)이 삽입되므로
        received에 포함된다(즉 통신장애 자체가 수집 누락이 아니라 데이터 결측으로 집계).
    """
    n_stations = len(TARGET_STATIONS)
    if df.empty:
        return 0, 24 * n_stations, 0.0
    now = now_kst().replace(tzinfo=None)  # df의 datetime은 naive
    since = now - timedelta(hours=24)
    df_24h = df[df["data_time"] >= since]
    received = len(df_24h)
    expected = 24 * n_stations
    rate = received / expected if expected > 0 else 0.0
    return received, expected, rate


# ----------------------------------------------------------------------
# Cpk 셀 색상 (Pandas Styler)
# ----------------------------------------------------------------------
def color_cpk_cell(val: str) -> str:
    """Cpk 매트릭스 셀 배경색.

    'n=N' 또는 '기준없음' 같은 비-수치 값은 회색.
    수치는 5단계 색상 매핑.
    """
    try:
        cpk = float(val)
    except (TypeError, ValueError):
        return "background-color: #2b2b2b; color: #999;"

    if cpk < 0:
        return "background-color: rgba(214,39,40,0.6); color: white; font-weight:700;"
    if cpk < 1.0:
        return "background-color: rgba(255,127,14,0.6); color: white; font-weight:700;"
    if cpk < 1.33:
        return "background-color: rgba(255,215,0,0.5); color: black;"
    if cpk < 1.67:
        return "background-color: rgba(144,238,144,0.5); color: black;"
    return "background-color: rgba(44,160,44,0.6); color: white; font-weight:700;"
