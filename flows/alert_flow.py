"""SPC 이상 탐지 알림 플로우.

매 수집 실행 후 GHA에서 호출 — 최근 데이터를 기반으로
Cpk 임계 미달 + WE Rules 위반을 점검하고 Discord로 알림을 전송한다.

실행 방법:
    uv run python flows/alert_flow.py          # 직접 실행 (로컬 테스트)
    uv run python flows/alert_flow.py --dry-run  # 실제 전송 없이 결과만 출력
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import pandas as pd
from loguru import logger

from src.analysis.capability import InsufficientSampleError, compute_capability
from src.analysis.usl_lsl import SPEC_LIMITS
from src.analysis.western_electric import we_rules
from src.notifier.discord import build_spc_alert, send_alert
from src.storage.database import query_all

# ---------------------------------------------------------------------------
# 설정
# ---------------------------------------------------------------------------

# Cpk 경보 임계: 1.0 미만이면 '불량 위험' 수준
CPK_ALERT_THRESHOLD: float = 1.0

# 점검 대상 오염물질 (USL이 있는 것만 → 24h 기준 우선)
POLLUTANTS: list[str] = ["pm10", "pm25", "o3", "no2", "so2", "co"]

# WE Rules: 심각도 높은 룰만 경보 (허깅·지그재그는 환경 데이터 특성상 제외)
WE_ALERT_RULES: list[int] = [1, 2, 3, 4, 5, 8]

# Cpk 계산에 사용할 최소 표본
CPK_MIN_N: int = 30

# WE Rules 계산에 사용할 최근 N건 (너무 긴 히스토리는 노이즈)
WE_WINDOW: int = 168  # 최근 7일 (시간당 1건 × 24h × 7)


# ---------------------------------------------------------------------------
# 핵심 로직
# ---------------------------------------------------------------------------

def _load_dataframe() -> pd.DataFrame:
    """DB에서 전체 데이터를 pandas DataFrame으로 로드한다."""
    records = query_all()
    if not records:
        return pd.DataFrame()
    rows = [r.model_dump() for r in records]
    df = pd.DataFrame(rows)
    df["data_time"] = pd.to_datetime(df["data_time"])
    return df


def _get_usl(pollutant: str) -> float | None:
    """오염물질의 USL을 반환한다 (일평균 우선, 없으면 시간 기준)."""
    spec = SPEC_LIMITS.get(pollutant)
    if spec is None:
        return None
    return spec.usl_daily if spec.usl_daily is not None else spec.usl_hourly


def run_alert_check(dry_run: bool = False) -> dict:
    """SPC 이상 탐지 점검 전체를 실행한다.

    Args:
        dry_run: True면 Discord 전송 없이 결과만 반환.

    Returns:
        {
            'cpk_violations': [...],
            'we_violations': [...],
            'total_checked': int,
            'sent': bool,
        }
    """
    logger.info("SPC 알림 점검 시작")

    df = _load_dataframe()
    if df.empty:
        logger.warning("데이터 없음 — 알림 점검 스킵")
        return {"cpk_violations": [], "we_violations": [], "total_checked": 0, "sent": False}

    stations = sorted(df["station_name"].unique())
    cpk_violations: list[dict] = []
    we_violations: list[dict] = []
    total_checked = 0

    for station in stations:
        sub = (
            df[df["station_name"] == station]
            .sort_values("data_time")
            .reset_index(drop=True)
        )

        for pollutant in POLLUTANTS:
            if pollutant not in sub.columns:
                continue

            series = sub[pollutant].dropna()
            if len(series) < 2:
                continue

            total_checked += 1
            usl = _get_usl(pollutant)

            # --- Cpk 점검 ---
            if usl is not None and len(series) >= CPK_MIN_N:
                try:
                    cap = compute_capability(series, usl=usl, lsl=0.0, min_n=CPK_MIN_N)
                    if cap.cpk < CPK_ALERT_THRESHOLD:
                        cpk_violations.append({
                            "station": station,
                            "pollutant": pollutant,
                            "cpk": cap.cpk,
                            "threshold": CPK_ALERT_THRESHOLD,
                        })
                        logger.warning(
                            f"Cpk 미달: {station}/{pollutant} Cpk={cap.cpk:.3f}"
                        )
                except (InsufficientSampleError, ValueError):
                    pass

            # --- WE Rules 점검 (최근 WE_WINDOW건) ---
            recent = series.iloc[-WE_WINDOW:]
            if len(recent) >= 2:
                try:
                    we_res = we_rules(recent, rules=WE_ALERT_RULES)
                    if we_res.active_rules:
                        we_violations.append({
                            "station": station,
                            "pollutant": pollutant,
                            "rules": sorted(we_res.active_rules),
                        })
                        logger.warning(
                            f"WE Rules 위반: {station}/{pollutant} "
                            f"Rules={sorted(we_res.active_rules)}"
                        )
                except ValueError:
                    pass

    logger.info(
        f"점검 완료: {total_checked}개 조합 | "
        f"Cpk 미달 {len(cpk_violations)}건 | WE Rules {len(we_violations)}건"
    )

    # --- Discord 전송 ---
    alert = build_spc_alert(cpk_violations, we_violations, total_checked)
    sent = False
    if not dry_run:
        sent = send_alert(alert)
    else:
        logger.info(f"[dry-run] 전송 스킵. 알림 내용:\n{alert.title}\n{alert.description}")
        for f in alert.fields:
            logger.info(f"  [{f.name}]\n{f.value}")

    return {
        "cpk_violations": cpk_violations,
        "we_violations": we_violations,
        "total_checked": total_checked,
        "sent": sent,
    }


# ---------------------------------------------------------------------------
# CLI 진입점
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SPC 이상 탐지 알림 플로우")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Discord 전송 없이 결과만 출력",
    )
    args = parser.parse_args()

    result = run_alert_check(dry_run=args.dry_run)

    print(f"\n점검 결과:")
    print(f"  총 점검: {result['total_checked']}개 조합")
    print(f"  Cpk 미달: {len(result['cpk_violations'])}건")
    print(f"  WE Rules 위반: {len(result['we_violations'])}건")
    print(f"  Discord 전송: {'완료' if result['sent'] else '스킵'}")
