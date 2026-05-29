"""DMAIC 분석 보고서 자동 생성 (PDF).

지금까지 산출물(수집 자동화·Cp/Cpk·관리도·가설검정·자기상관 보정)을
6시그마 DMAIC(Define-Measure-Analyze-Improve-Control) 한 편으로 묶어 PDF로 출력한다.

한글 폰트: 시스템 TTF(맑은 고딕 등)를 임베드. 후보 경로 중 첫 발견분 사용.
  환경변수 DMAIC_FONT로 직접 지정 가능.

실행:
    uv run python scripts/generate_dmaic_report.py
출력:
    reports/dmaic/YYYY-MM-DD.pdf
"""

from __future__ import annotations

import os
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from fpdf import FPDF  # noqa: E402

from src.analysis.capability import (  # noqa: E402
    InsufficientSampleError,
    compute_capability,
)
from src.analysis.hypothesis_test import (  # noqa: E402
    anova_across_stations,
    industrial_vs_baseline,
)
from src.analysis.residual_chart import residual_i_chart  # noqa: E402
from src.analysis.usl_lsl import SPEC_LIMITS  # noqa: E402
from src.config import (  # noqa: E402
    BASELINE_GROUP,
    INDUSTRIAL_GROUP,
    STATION_GROUPS,
    TARGET_STATIONS,
)
from src.storage.database import query_all  # noqa: E402

KST = timezone(timedelta(hours=9))
REPORTS_DIR = _PROJECT_ROOT / "reports" / "dmaic"
POLLUTANTS = list(SPEC_LIMITS.keys())
POLLUTANT_KR = {p: SPEC_LIMITS[p].description for p in POLLUTANTS}

# 한글 폰트 후보 (첫 발견분 사용)
_FONT_CANDIDATES = [
    os.environ.get("DMAIC_FONT", ""),
    "C:/Windows/Fonts/malgun.ttf",
    "C:/Windows/Fonts/NanumGothic.ttf",
    "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
    "/Library/Fonts/AppleSDGothicNeo.ttc",
]


def _find_font() -> str:
    for c in _FONT_CANDIDATES:
        if c and Path(c).exists():
            return c
    raise FileNotFoundError(
        "한글 TTF 폰트를 찾지 못했습니다. 환경변수 DMAIC_FONT로 경로를 지정하세요."
    )


def _load_df() -> pd.DataFrame:
    rows = query_all()
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame.from_records(
        [
            {
                "station_name": r.station_name,
                "data_time": r.data_time,
                **{p: getattr(r, p) for p in POLLUTANTS},
            }
            for r in rows
        ]
    )
    df["data_time"] = pd.to_datetime(df["data_time"])
    return df


# ---------------------------------------------------------------------------
# PDF 빌더
# ---------------------------------------------------------------------------
class DmaicPDF(FPDF):
    """한글 지원 + DMAIC 섹션 헬퍼."""

    def __init__(self, font_path: str) -> None:
        super().__init__()
        self.add_font("kr", "", font_path)
        self.add_font("kr", "B", font_path)  # 굵게 별도 파일 없으면 동일 사용
        self.set_auto_page_break(auto=True, margin=18)

    def _mc(self, h: float, text: str) -> None:
        """좌측 마진에서 전체 폭으로 multi_cell (폭 계산 안전)."""
        self.set_x(self.l_margin)
        self.multi_cell(self.epw, h, text)

    def h1(self, text: str) -> None:
        self.set_font("kr", "B", 16)
        self.set_text_color(20, 40, 80)
        self._mc(9, text)
        self.set_text_color(0, 0, 0)
        self.ln(1)

    def h2(self, text: str) -> None:
        self.set_font("kr", "B", 12.5)
        self.set_text_color(30, 60, 110)
        self._mc(7.5, text)
        self.set_text_color(0, 0, 0)
        self.ln(0.5)

    def body(self, text: str) -> None:
        self.set_font("kr", "", 10)
        self._mc(5.6, text)
        self.ln(0.5)

    def bullet(self, text: str) -> None:
        self.set_font("kr", "", 10)
        self._mc(5.6, f"  -  {text}")

    def table(self, headers: list[str], rows: list[list[str]], widths: list[float]) -> None:
        self.set_font("kr", "B", 9)
        self.set_fill_color(225, 232, 245)
        for h, w in zip(headers, widths):
            self.cell(w, 7, h, border=1, align="C", fill=True)
        self.ln()
        self.set_font("kr", "", 9)
        for row in rows:
            for val, w in zip(row, widths):
                self.cell(w, 6.5, str(val), border=1, align="C")
            self.ln()
        self.ln(2)


# ---------------------------------------------------------------------------
# 지표 계산
# ---------------------------------------------------------------------------
def _usl(spec, basis="daily"):
    u = spec.usl_for(basis)
    if u is None:
        for fb in ("daily", "annual", "hourly"):
            u = spec.usl_for(fb)
            if u is not None:
                return u
    return u


def build_report(df: pd.DataFrame, today: datetime, font_path: str) -> Path:
    pdf = DmaicPDF(font_path)
    pdf.add_page()

    # ---- 표지 ----
    pdf.h1("충북권 산업단지 대기질 SPC 모니터링")
    pdf.h2("6시그마 DMAIC 분석 보고서")
    rng = f"{df['data_time'].min():%Y-%m-%d} ~ {df['data_time'].max():%Y-%m-%d}"
    pdf.body(
        f"생성일: {today:%Y-%m-%d %H:%M KST}\n"
        f"분석 기간: {rng}\n"
        f"데이터: 총 {len(df):,}건 · 측정소 {df['station_name'].nunique()}곳 · "
        f"시간 해상도 1시간"
    )
    pdf.body(
        "본 보고서는 대기질을 제조 공정에 빗대어, 측정소=공정 라인, 오염물질=품질특성(CQA), "
        "환경기준=규격(USL)으로 매핑해 SPC·6시그마 역량을 실데이터로 입증한다. "
        "(수집 빈도는 데이터 해상도(1시간)와 무관한 재시도 메커니즘)"
    )
    pdf.ln(2)

    # ---- D: Define ----
    pdf.h2("D — Define (정의)")
    pdf.body(
        "문제: 산업단지 인근 대기질이 거주지(베이스라인)보다 나쁜가? 어느 지표·어느 위치가 "
        "가장 문제인가? 이를 통계적 공정관리로 상시 감시·검증한다."
    )
    pdf.bullet("산단 영향군: 오창(반도체)·복대/봉명(SK하이닉스 권역)·오송(바이오)")
    pdf.bullet("베이스라인(대조군): 용암동(거주지)")
    pdf.bullet("품질특성(CQA): PM10/PM2.5/O3/NO2/SO2/CO 6종, USL=대기환경보전법 환경기준")

    # ---- M: Measure ----
    pdf.add_page()
    pdf.h2("M — Measure (측정 시스템)")
    pdf.body(
        "에어코리아 OpenAPI를 시간당 자동 수집. 외부 스케줄러(cron-job.org)가 "
        "GitHub Actions를 트리거하고, self-healing 백필이 직전 24h 누락을 자동 복구해 "
        "무중단·무누락을 보장한다. 측정시각(data_time)과 수집시각(created_at)을 분리 기록."
    )
    per = Counter(df["station_name"])
    pdf.table(
        ["측정소", "그룹", "누적 건수"],
        [[s, STATION_GROUPS.get(s, "-"), f"{per.get(s, 0):,}"] for s in TARGET_STATIONS],
        [55, 70, 45],
    )

    # ---- A: Analyze ----
    pdf.h2("A — Analyze (분석)")
    pdf.body("① 산단 영향군 vs 베이스라인 — Welch t-test (효과크기 Cohen's d 병기)")
    t_rows = []
    for p in POLLUTANTS:
        try:
            r = industrial_vs_baseline(df, p, STATION_GROUPS, INDUSTRIAL_GROUP, BASELINE_GROUP)
            t_rows.append([
                POLLUTANT_KR[p].split(" ")[0], f"{r.mean_a:.3f}", f"{r.mean_b:.3f}",
                f"{r.diff:+.3f}", f"{r.p_value:.3g}", f"{r.cohens_d:+.2f}",
            ])
        except (InsufficientSampleError, ValueError):
            t_rows.append([POLLUTANT_KR[p].split(" ")[0], "-", "-", "-", "표본부족", "-"])
    pdf.table(
        ["지표", "산단μ", "베이스μ", "차이", "p", "d"],
        t_rows, [40, 28, 28, 28, 30, 26],
    )

    pdf.body("② 측정소 간 차이 — one-way ANOVA (η²=설명력)")
    a_rows = []
    for p in POLLUTANTS:
        try:
            a = anova_across_stations(df, p)
            hi = a.labels[int(np.argmax(a.group_means))]
            a_rows.append([POLLUTANT_KR[p].split(" ")[0], f"{a.f_stat:.1f}",
                           f"{a.p_value:.3g}", f"{a.eta_squared:.3f}", hi])
        except (InsufficientSampleError, ValueError):
            a_rows.append([POLLUTANT_KR[p].split(" ")[0], "-", "표본부족", "-", "-"])
    pdf.table(["지표", "F", "p", "η²", "최고 측정소"], a_rows, [40, 30, 32, 28, 50])

    pdf.body(
        "③ 자기상관 진단(핵심): PM2.5 lag-1 자기상관(ACF)이 0.9를 넘어, 전통 SPC의 "
        "독립(i.i.d.) 가정이 위배된다. 명목 표본은 측정소당 2천여 건이나 유효표본(n_eff)은 "
        "약 75에 불과 → 위 t-test p값은 과대평가된 값이며, Analyze에는 자기상관 보정이 필수다."
    )
    pdf.set_font("kr", "B", 10)
    pdf.set_text_color(150, 40, 40)
    pdf.set_x(pdf.l_margin)
    pdf.multi_cell(pdf.epw, 5.6, "[한계] 효과크기 작음(|d| 약 0.2)·위치 설명력 eta^2<5%·봄 단일계절. "
                          "변동의 대부분은 위치가 아닌 시간·기상 공통요인 → 기상 교란통제는 후속 필수과제.")
    pdf.set_text_color(0, 0, 0)
    pdf.ln(1)

    # ---- I: Improve ----
    pdf.add_page()
    pdf.h2("I — Improve (개선)")
    pdf.body(
        "개선 1) 자기상관 보정 잔차 관리도: 일주기(시간대) 제거 + AR(1) 잔차에 관리도를 "
        "적용해 거짓경보를 제거했다. PM2.5 실측 기준 개선 효과는 다음과 같다."
    )
    imp_rows = []
    for st in TARGET_STATIONS:
        sub = df[df["station_name"] == st].sort_values("data_time")
        try:
            rr = residual_i_chart(sub["pm25"], hours=sub["data_time"].dt.hour, deseasonalize=True)
            imp_rows.append([
                st, f"{rr.acf_before:.2f}->{rr.acf_after:.2f}",
                f"{rr.raw_violation_rate * 100:.1f}%",
                f"{rr.resid_violation_rate * 100:.1f}%",
            ])
        except (InsufficientSampleError, ValueError):
            imp_rows.append([st, "-", "표본부족", "-"])
    pdf.table(
        ["측정소(PM2.5)", "lag-1 ACF", "원시 이탈률", "잔차 이탈률"],
        imp_rows, [50, 50, 45, 45],
    )
    pdf.body(
        "개선 2) Cpk 우선관리 대상 식별: 공정능력이 낮은(규격 대비 산포가 큰) 측정소·지표를 "
        "우선 관리 대상으로 도출한다. (일평균 기준 USL)"
    )
    # Cpk 매트릭스 (간단)
    cpk_rows = []
    for st in TARGET_STATIONS:
        sub = df[df["station_name"] == st]
        cells = [st]
        for p in ("pm10", "pm25"):
            try:
                r = compute_capability(sub[p].dropna(), usl=_usl(SPEC_LIMITS[p]), lsl=0.0)
                cells.append(f"{r.cpk:.2f}")
            except (InsufficientSampleError, ValueError):
                cells.append("-")
        cpk_rows.append(cells)
    pdf.table(["측정소", "PM10 Cpk", "PM2.5 Cpk"], cpk_rows, [60, 45, 45])

    # ---- C: Control ----
    pdf.h2("C — Control (관리)")
    pdf.body(
        "Streamlit 대시보드로 관리도(I/EWMA/CUSUM + 자기상관 보정 잔차)·공정능력·GIS 지도를 "
        "상시 모니터링한다. 수집 자동화 + self-healing으로 데이터 완결성을 유지한다."
    )
    pdf.bullet("향후: Western Electric Rules 자동 판정 + Discord 알림(특수원인 신호)")
    pdf.bullet("향후: 기상(ASOS) 결합 교란통제 — 단 사계절 데이터 확보 후 일반화(현재 봄 한정)")
    pdf.bullet("향후: 기상+자기상관 동시 보정(ARIMAX/GLS)으로 p값 인플레 재발 방지")

    pdf.ln(3)
    pdf.set_font("kr", "", 8)
    pdf.set_text_color(120, 120, 120)
    pdf.set_x(pdf.l_margin)
    pdf.multi_cell(pdf.epw, 4.5, "자동 생성 — 데이터 누적 시 갱신. 본 분석은 봄철 단일계절 단면이며 "
                          "인과가 아닌 탐색적·연관 수준으로 해석해야 한다.")

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    out = REPORTS_DIR / f"{today:%Y-%m-%d}.pdf"
    pdf.output(str(out))
    return out


def main() -> int:
    today = datetime.now(tz=KST)
    df = _load_df()
    if df.empty:
        print("데이터가 없습니다.")
        return 1
    font = _find_font()
    print(f"폰트: {font}")
    out = build_report(df, today, font)
    size_kb = out.stat().st_size / 1024
    print(f"✅ DMAIC 보고서 생성: {out.relative_to(_PROJECT_ROOT)} ({size_kb:.0f} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
