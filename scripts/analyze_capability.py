"""공정능력지수(Cp/Cpk) 분석 스크립트.

DB에 누적된 데이터를 측정소 × 오염물질 조합으로 분석하고
표 형태로 출력한다. 표본 < 30이면 InsufficientSampleError를 잡아
사용자에게 친절히 알려준다.

실행 예:
    uv run python scripts/analyze_capability.py
    uv run python scripts/analyze_capability.py --basis hourly
    uv run python scripts/analyze_capability.py --basis daily
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import pandas as pd  # noqa: E402

from src.analysis.capability import (  # noqa: E402
    InsufficientSampleError,
    MIN_SAMPLE_SIZE,
    compute_capability,
)
from src.analysis.usl_lsl import SPEC_LIMITS  # noqa: E402
from src.config import TARGET_STATIONS  # noqa: E402
from src.storage.database import query_all  # noqa: E402

# AirQualityMeasurement 컬럼명 ↔ SPEC_LIMITS 키 매핑
_POLLUTANT_COLUMNS: dict[str, str] = {
    "pm10": "pm10",
    "pm25": "pm25",
    "o3": "o3",
    "no2": "no2",
    "so2": "so2",
    "co": "co",
}


def _load_dataframe() -> pd.DataFrame:
    """DB의 모든 측정값을 DataFrame으로 반환한다."""
    rows = query_all()
    if not rows:
        return pd.DataFrame()
    records = [
        {
            "station_name": r.station_name,
            "data_time": r.data_time,
            **{col: getattr(r, col) for col in _POLLUTANT_COLUMNS.values()},
        }
        for r in rows
    ]
    return pd.DataFrame.from_records(records)


def _select_usl(pollutant_key: str, basis: str) -> float | None:
    """오염물질 + 기준 시간으로 USL을 선택한다. 정의되지 않으면 fallback."""
    spec = SPEC_LIMITS[pollutant_key]
    usl = spec.usl_for(basis)
    if usl is None:
        # 폴백 우선순위: daily -> annual -> hourly
        for fb in ("daily", "annual", "hourly"):
            usl = spec.usl_for(fb)
            if usl is not None:
                return usl
    return usl


def analyze(basis: str = "daily") -> int:
    """측정소 × 오염물질 매트릭스로 Cp/Cpk 분석을 실행하고 표를 출력한다."""
    df = _load_dataframe()
    if df.empty:
        print("DB에 누적 데이터가 없습니다. 먼저 collect_once.py 또는 collect_flow를 실행하세요.")
        return 1

    print(f"분석 기준: {basis} USL (최소 표본 {MIN_SAMPLE_SIZE}건)")
    print(f"총 누적 레코드: {len(df)}건\n")

    # 헤더
    header = f"{'측정소':<8}" + "".join(
        f"{p.upper():>14}" for p in _POLLUTANT_COLUMNS
    )
    print(header)
    print("-" * len(header))

    for station in TARGET_STATIONS:
        sub = df[df["station_name"] == station]
        row_cells: list[str] = [f"{station:<8}"]
        for pkey, col in _POLLUTANT_COLUMNS.items():
            values = sub[col].dropna()
            usl = _select_usl(pkey, basis)
            if usl is None:
                row_cells.append(f"{'USL없음':>14}")
                continue
            try:
                result = compute_capability(values, usl=usl, lsl=0.0)
            except InsufficientSampleError:
                row_cells.append(f"{'n=' + str(len(values)):>14}")
                continue
            except ValueError as e:
                row_cells.append(f"{'err':>14}")
                continue
            row_cells.append(f"{result.cpk:>14.3f}")
        print("".join(row_cells))

    print()
    print("값 의미: Cpk (음수=규격이탈, <1.0=불량위험, <1.33=마진부족, <1.67=양호, ≥1.67=우수)")
    print(f"'n=N' 표기는 표본 부족 (N건 보유, 최소 {MIN_SAMPLE_SIZE} 필요)")
    print("'USL없음'은 해당 기준시간(basis)의 환경기준이 정의되지 않은 항목")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Cp/Cpk 분석 스크립트")
    parser.add_argument(
        "--basis",
        choices=["hourly", "daily", "annual"],
        default="daily",
        help="USL 기준 시간 (기본: daily)",
    )
    args = parser.parse_args()
    return analyze(basis=args.basis)


if __name__ == "__main__":
    sys.exit(main())
