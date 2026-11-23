"""풍향·기상 결합 분석 리포트 자동 생성 (Phase 4 실분석 산출).

대기질(에어코리아)과 기상(ASOS 청주)을 시간 단위로 조인해:
  1. 오염장미 — 풍향 8방위별 평균 농도
  2. 산단 방위 검정 — 측정소×산단 조합 Welch t-test (H4 정량 검증)
  3. 기상 회귀 — 농도 ~ 풍속·기온·습도 OLS (분산분해 '기상' 내역 실증)

결과는 reports/wind/YYYY-MM-DD.md (+ latest.md)에 남긴다.
조인 표본 부족 시: 건너뛰고 진행 상황만 출력 (exit 0).
→ daily_dev_loop 워크플로우에 물려 매일 자동 실행.

실행:
    uv run python scripts/generate_wind_report.py
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import pandas as pd  # noqa: E402

from src.analysis.usl_lsl import SPEC_LIMITS  # noqa: E402
from src.analysis.wind_regression import (  # noqa: E402
    SECTORS_8,
    DirectionalResult,
    InsufficientSampleError,
    WeatherRegressionResult,
    bearing,
    directional_test,
    join_air_weather,
    pollution_rose,
    weather_regression,
)
from src.config import INDUSTRIAL_SOURCES, STATION_COORDS  # noqa: E402
from src.storage.database import query_all, query_weather  # noqa: E402

KST = timezone(timedelta(hours=9))
REPORTS_DIR = _PROJECT_ROOT / "reports" / "wind"
POLLUTANTS = list(SPEC_LIMITS.keys())  # pm10, pm25, o3, no2, so2, co
POLLUTANT_KR = {p: SPEC_LIMITS[p].description for p in POLLUTANTS}
# 방위 검정은 입자상 오염물질(산단 배출 지표)에 집중
DIRECTIONAL_POLLUTANTS = ("pm25", "pm10")
REGRESSION_PREDICTORS = ("ws", "ta", "hm")
PREDICTOR_KR = {"ws": "풍속", "ta": "기온", "hm": "습도"}
# 측정소당 조인 표본 최소 요건 (방위 검정의 섹터 내 표본 확보 여지 포함)
MIN_JOINED_PER_STATION = 100


def _load_joined() -> pd.DataFrame:
    """대기질·기상을 로드해 시간 단위로 조인한 DataFrame을 반환."""
    air_rows = query_all()
    wx_rows = query_weather()
    if not air_rows or not wx_rows:
        return pd.DataFrame()
    df_air = pd.DataFrame.from_records(
        [
            {
                "station_name": r.station_name,
                "data_time": r.data_time,
                **{p: getattr(r, p) for p in POLLUTANTS},
            }
            for r in air_rows
        ]
    )
    df_wx = pd.DataFrame.from_records(
        [
            {
                "obs_time": r.obs_time,
                "ta": r.ta,
                "hm": r.hm,
                "ws": r.ws,
                "wd": r.wd,
                "rn": r.rn,
            }
            for r in wx_rows
        ]
    )
    return join_air_weather(df_air, df_wx)


def run_directional_tests(
    df: pd.DataFrame,
) -> list[tuple[str, str, DirectionalResult]]:
    """측정소 × 산단 × 오염물질 방위 검정. (측정소, 산단, 결과) 리스트."""
    out: list[tuple[str, str, DirectionalResult]] = []
    for station, coord in STATION_COORDS.items():
        sub = df[df["station_name"] == station]
        for source, s_coord in INDUSTRIAL_SOURCES.items():
            b = bearing(coord[0], coord[1], s_coord[0], s_coord[1])
            for pol in DIRECTIONAL_POLLUTANTS:
                try:
                    out.append((station, source, directional_test(sub, pol, b)))
                except (InsufficientSampleError, ValueError):
                    pass
    return out


def run_regressions(df: pd.DataFrame) -> dict[str, dict[str, WeatherRegressionResult]]:
    """측정소별 × 오염물질별 기상 회귀. {측정소: {오염물질: 결과}}."""
    out: dict[str, dict[str, WeatherRegressionResult]] = {}
    for station in STATION_COORDS:
        sub = df[df["station_name"] == station]
        per: dict[str, WeatherRegressionResult] = {}
        for pol in POLLUTANTS:
            try:
                per[pol] = weather_regression(
                    sub, pol, predictors=REGRESSION_PREDICTORS
                )
            except (InsufficientSampleError, ValueError):
                pass
        if per:
            out[station] = per
    return out


# ---------------------------------------------------------------------------
# Markdown 렌더
# ---------------------------------------------------------------------------
def render_markdown(
    today: datetime,
    df: pd.DataFrame,
    dir_results: list[tuple[str, str, DirectionalResult]],
    reg_results: dict[str, dict[str, WeatherRegressionResult]],
) -> str:
    L: list[str] = []
    L.append(f"# 🌦️ 풍향·기상 결합 분석 리포트 — {today.strftime('%Y-%m-%d')} (KST)")
    L.append("")
    period = (
        f"{df['data_time'].min().strftime('%Y-%m-%d %H시')} ~ "
        f"{df['data_time'].max().strftime('%Y-%m-%d %H시')}"
    )
    L.append(
        f"> 자동 생성: {today.strftime('%Y-%m-%d %H:%M KST')} · "
        f"대기질·기상(ASOS 청주) 조인 {len(df):,}건 · 기간 {period}"
    )
    L.append("")
    L.append(
        "**분석 설계**: 풍향(wd)은 '바람이 불어오는 방향'(기상 관례). "
        "측정소 기준 산단 방위 ±22.5° 섹터에서 부는 바람일 때 vs 그 외의 농도를 "
        "Welch t-test로 비교(H4), 기상 변수 설명력은 OLS R²로 평가. "
        "가설 정의는 `docs/ANALYSIS_HYPOTHESES.md` 참조."
    )
    L.append("")

    # 1. 오염장미
    L.append("## 1. 오염장미 (풍향 8방위별 평균 농도, 전체 측정소)")
    L.append("")
    L.append("| 오염물질 | " + " | ".join(SECTORS_8) + " | 최고 방위 |")
    L.append("|---|" + "---|" * (len(SECTORS_8) + 1))
    for pol in DIRECTIONAL_POLLUTANTS:
        rose = pollution_rose(df, pol)
        if not rose:
            continue
        max_s = max(rose, key=rose.get)
        cells = " | ".join(
            f"**{rose[s]:.1f}**" if s == max_s else (f"{rose[s]:.1f}" if s in rose else "—")
            for s in SECTORS_8
        )
        L.append(f"| {POLLUTANT_KR[pol]} | {cells} | {max_s} |")
    L.append("")

    # 2. 산단 방위 검정
    L.append("## 2. 산단 방위 검정 (Welch t-test, H4)")
    L.append("")
    L.append(
        "| 측정소 | 산단 (방위) | 오염물질 | 산단방위 평균 (n) | 그 외 평균 | 차이 | p-value | 유의 | d |"
    )
    L.append("|---|---|---|---|---|---|---|---|---|")
    for station, source, r in dir_results:
        sig = "✅" if r.significant else "✖"
        L.append(
            f"| {station} | {source} ({r.source_bearing:.0f}°) | {POLLUTANT_KR[r.pollutant]} | "
            f"{r.mean_in:.1f} ({r.n_in}) | {r.mean_out:.1f} | {r.diff:+.1f} | "
            f"{r.p_value:.4f} | {sig} | {r.cohens_d:+.2f} |"
        )
    L.append("")

    # 유의한 양(+)의 효과 해석
    positive = [
        (st, src, r)
        for st, src, r in dir_results
        if r.significant and r.diff > 0
    ]
    positive.sort(key=lambda x: x[2].cohens_d, reverse=True)
    if positive:
        L.append("**산단 방위 바람일 때 농도가 유의하게 높은 조합 (효과크기 순):**")
        L.append("")
        for st, src, r in positive:
            L.append(f"- **{st} ← {src}**: {r.interpret()}")
        L.append("")
    negative = [
        (st, src, r) for st, src, r in dir_results if r.significant and r.diff < 0
    ]
    if negative:
        L.append(
            "**주의(교란 가능성)**: 일부 조합은 산단 방위 바람일 때 오히려 낮다. "
            "해당 방위가 광역적으로 '깨끗한 바람'(예: 남서풍 해양성 기류)과 겹치면 "
            "산단 효과가 기단 효과에 가려질 수 있다 — 방위 검정은 오염장미와 함께 해석할 것."
        )
        L.append("")

    # 3. 기상 회귀
    L.append("## 3. 기상 회귀 (농도 ~ 풍속·기온·습도, OLS R²)")
    L.append("")
    L.append("| 측정소 | " + " | ".join(POLLUTANT_KR[p] for p in POLLUTANTS) + " |")
    L.append("|---|" + "---|" * len(POLLUTANTS))
    for station, per in reg_results.items():
        cells = " | ".join(
            f"{per[p].r2:.3f}" if p in per else "—" for p in POLLUTANTS
        )
        L.append(f"| {station} | {cells} |")
    L.append("")

    # O3 계수 예시 (기상 설명력이 가장 높은 지표)
    best = None
    for station, per in reg_results.items():
        for pol, r in per.items():
            if best is None or r.r2 > best[2].r2:
                best = (station, pol, r)
    if best is not None:
        station, pol, r = best
        coef_txt = ", ".join(
            f"{PREDICTOR_KR.get(k, k)} {v:+.3f}" for k, v in r.coef.items()
        )
        L.append(
            f"가장 설명력 높은 조합: **{station} · {POLLUTANT_KR[pol]}** "
            f"R²={r.r2:.3f} (n={r.n:,}) — 계수: {coef_txt}"
        )
        L.append("")

    # 4. 종합 해석
    L.append("## 4. 종합 해석 (DMAIC Analyze → 실증)")
    L.append("")
    if positive:
        st, src, r = positive[0]
        L.append(
            f"- **H4 지지**: 산단 방위 검정에서 유의한 양의 효과 {len(positive)}건 확인. "
            f"최대 효과는 {st}←{src} {POLLUTANT_KR[r.pollutant]} "
            f"(+{r.diff:.1f}, d={r.cohens_d:.2f}) — 배출원 방향 바람이 실제로 "
            "농도를 끌어올린다는 가설을 실데이터로 실증."
        )
    else:
        L.append(
            "- **H4 판단 보류**: 유의한 양의 방위 효과가 관찰되지 않음. "
            "계절·기단 다양성이 누적되면 재검정."
        )
    r2_o3 = [per["o3"].r2 for per in reg_results.values() if "o3" in per]
    r2_pm = [per["pm25"].r2 for per in reg_results.values() if "pm25" in per]
    if r2_o3 and r2_pm:
        L.append(
            f"- **분산분해 '기상' 내역 실증**: 기상 3변수만으로 O3 분산의 "
            f"{min(r2_o3)*100:.0f}~{max(r2_o3)*100:.0f}%를 설명(광화학 생성 — 기온·일사 주도). "
            f"반면 PM2.5는 {min(r2_pm)*100:.0f}~{max(r2_pm)*100:.0f}%에 그침 → "
            "PM2.5 변동은 기상 직접효과보다 배출·수송(풍향)·2차 생성의 몫이 크다. "
            "잔차 관리도(자기상관 보정)가 PM2.5에 특히 유효했던 이유와 일치."
        )
    L.append(
        "- ⚠️ 단일 계절(여름) 데이터 기준. 겨울(난방·북서 계절풍) 데이터가 누적되면 "
        "오염장미·방위 효과의 계절 대비 분석이 가능해진다."
    )
    L.append("")
    L.append("---")
    L.append("🤖 *기상 데이터가 누적될수록 매일 자동 재분석됩니다.*")
    return "\n".join(L)


# ---------------------------------------------------------------------------
# 메인
# ---------------------------------------------------------------------------
def main() -> int:
    today = datetime.now(tz=KST)
    df = _load_joined()
    print(f"=== 풍향·기상 분석 리포트 @ {today.strftime('%Y-%m-%d %H:%M KST')} ===")
    if df.empty:
        print("⏳ 조인 가능한 대기질·기상 데이터 없음 — 건너뜁니다.")
        return 0

    per_station = df.groupby("station_name").size()
    min_joined = int(per_station.min()) if not per_station.empty else 0
    print(f"조인 {len(df):,}건 / 측정소당 최소 {min_joined}건 (요건 {MIN_JOINED_PER_STATION})")
    if min_joined < MIN_JOINED_PER_STATION:
        print(
            f"⏳ 조인 표본 부족 — 측정소당 {MIN_JOINED_PER_STATION - min_joined}건 더 필요. "
            "리포트 생성을 건너뜁니다 (기상 데이터 누적 후 자동 실행)."
        )
        return 0

    dir_results = run_directional_tests(df)
    reg_results = run_regressions(df)

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = today.strftime("%Y-%m-%d")
    md = render_markdown(today, df, dir_results, reg_results)
    (REPORTS_DIR / f"{stamp}.md").write_text(md, encoding="utf-8")
    (REPORTS_DIR / "latest.md").write_text(md, encoding="utf-8")

    n_sig = sum(1 for _, _, r in dir_results if r.significant)
    print(f"✅ 리포트 생성: reports/wind/{stamp}.md")
    print(f"   방위 검정 {len(dir_results)}건(유의 {n_sig}), 회귀 {sum(len(v) for v in reg_results.values())}건")
    return 0


if __name__ == "__main__":
    sys.exit(main())
