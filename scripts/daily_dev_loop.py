"""매일 KST 09:15 자율 개발 루프 (EPL 프로젝트 daily_dev_loop 패턴 차용).

GitHub Actions가 매일 한 번 호출. Claude API 호출 없이 다음을 수행:
  1. pytest 회귀 테스트 실행
  2. 누적 데이터 통계 산출
  3. 최근 24시간 수집 성공률 평가
  4. 가능한 모든 측정소 × 지표 조합 Cp/Cpk 계산
  5. 데이터 마일스톤 진행률 (DATA_30_PER_STATION 등)
  6. PHASE_QUEUE.yml에서 다음 후보 작업 안내
  7. 결과를 reports/daily/YYYY-MM-DD.md로 저장

실행:
    uv run python scripts/daily_dev_loop.py
"""

from __future__ import annotations

import subprocess
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import pandas as pd  # noqa: E402
import yaml  # noqa: E402 - prefect/pydantic 의존성에 포함됨

from src.analysis.capability import (  # noqa: E402
    InsufficientSampleError,
    MIN_SAMPLE_SIZE,
    compute_capability,
)
from src.analysis.usl_lsl import SPEC_LIMITS  # noqa: E402
from src.config import TARGET_STATIONS  # noqa: E402
from src.storage.database import query_all  # noqa: E402

KST = timezone(timedelta(hours=9))
REPORTS_DIR = _PROJECT_ROOT / "reports" / "daily"
QUEUE_FILE = _PROJECT_ROOT / "docs" / "PHASE_QUEUE.yml"


# ---------------------------------------------------------------------------
# 데이터 로드
# ---------------------------------------------------------------------------
def _load_df() -> pd.DataFrame:
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
            "flag": r.flag,
        }
        for r in rows
    ]
    return pd.DataFrame.from_records(records)


# ---------------------------------------------------------------------------
# 1. pytest 실행
# ---------------------------------------------------------------------------
def run_pytest() -> tuple[bool, str]:
    """pytest 실행. (성공여부, 마지막 라인 요약)."""
    try:
        result = subprocess.run(
            ["uv", "run", "pytest", "-q", "--no-header"],
            cwd=_PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=300,
        )
        last_line = (result.stdout.strip().splitlines() or ["(no output)"])[-1]
        return result.returncode == 0, last_line
    except (subprocess.TimeoutExpired, FileNotFoundError) as exc:
        return False, f"pytest 실행 실패: {exc}"


# ---------------------------------------------------------------------------
# 2. 누적 통계
# ---------------------------------------------------------------------------
def accumulation_stats(df: pd.DataFrame) -> dict[str, Any]:
    if df.empty:
        return {"total": 0, "per_station": {}, "first_time": None, "last_time": None}
    return {
        "total": len(df),
        "per_station": dict(Counter(df["station_name"])),
        "first_time": df["data_time"].min(),
        "last_time": df["data_time"].max(),
        "unique_times": df["data_time"].nunique(),
    }


# ---------------------------------------------------------------------------
# 3. 24h 수집 성공률
# ---------------------------------------------------------------------------
def health_24h(df: pd.DataFrame) -> dict[str, Any]:
    if df.empty:
        return {"received": 0, "expected": 96, "rate": 0.0, "missing_hours": []}
    now = datetime.now(tz=KST).replace(tzinfo=None)
    since = now - timedelta(hours=24)
    df_24h = df[df["data_time"] >= since]
    received = len(df_24h)
    expected = 24 * 4

    # 시각 누락 hours 찾기
    expected_hours = {
        (since + timedelta(hours=i)).replace(minute=0, second=0, microsecond=0)
        for i in range(24)
    }
    got_hours = {pd.Timestamp(t).floor("h").to_pydatetime() for t in df_24h["data_time"]}
    missing = sorted(expected_hours - got_hours)
    return {
        "received": received,
        "expected": expected,
        "rate": received / expected if expected else 0.0,
        "missing_hours": [h.strftime("%Y-%m-%d %H:%M") for h in missing[:5]],
    }


# ---------------------------------------------------------------------------
# 4. Cp/Cpk 매트릭스
# ---------------------------------------------------------------------------
def cpk_matrix(df: pd.DataFrame, basis: str = "daily") -> dict[str, dict[str, str]]:
    matrix: dict[str, dict[str, str]] = {}
    if df.empty:
        return matrix
    pollutants = list(SPEC_LIMITS.keys())
    for station in TARGET_STATIONS:
        sub = df[df["station_name"] == station]
        row: dict[str, str] = {}
        for p in pollutants:
            spec = SPEC_LIMITS[p]
            usl = spec.usl_for(basis)
            if usl is None:
                for fb in ("daily", "annual", "hourly"):
                    usl = spec.usl_for(fb)
                    if usl is not None:
                        break
            if usl is None:
                row[p] = "기준없음"
                continue
            values = sub[p].dropna()
            try:
                res = compute_capability(values, usl=usl, lsl=0.0)
                row[p] = f"{res.cpk:.3f}"
            except InsufficientSampleError:
                row[p] = f"n={len(values)}"
            except ValueError:
                row[p] = "오류"
        matrix[station] = row
    return matrix


# ---------------------------------------------------------------------------
# 5. 마일스톤 진행률
# ---------------------------------------------------------------------------
def milestone_progress(df: pd.DataFrame) -> list[dict[str, Any]]:
    if df.empty:
        return [
            {"name": "DATA_30_PER_STATION", "progress": "0/30", "pct": 0.0},
            {"name": "DATA_50_PER_STATION", "progress": "0/50", "pct": 0.0},
            {"name": "DATA_500", "progress": "0/500", "pct": 0.0},
            {"name": "DATA_1000", "progress": "0/1000", "pct": 0.0},
        ]
    per_station = Counter(df["station_name"])
    min_per = min(per_station.get(s, 0) for s in TARGET_STATIONS)
    total = len(df)
    return [
        {
            "name": "DATA_30_PER_STATION",
            "progress": f"{min_per}/30 (최소 측정소 기준)",
            "pct": min(min_per / 30.0 * 100, 100),
        },
        {
            "name": "DATA_50_PER_STATION",
            "progress": f"{min_per}/50",
            "pct": min(min_per / 50.0 * 100, 100),
        },
        {
            "name": "DATA_500",
            "progress": f"{total}/500",
            "pct": min(total / 500.0 * 100, 100),
        },
        {
            "name": "DATA_1000",
            "progress": f"{total}/1000",
            "pct": min(total / 1000.0 * 100, 100),
        },
    ]


# ---------------------------------------------------------------------------
# 6. 다음 후보 작업 (큐에서)
# ---------------------------------------------------------------------------
def next_candidates(df: pd.DataFrame) -> list[dict[str, Any]]:
    if not QUEUE_FILE.exists():
        return []
    queue = yaml.safe_load(QUEUE_FILE.read_text(encoding="utf-8"))
    milestones_met = _milestones_met(df)
    candidates: list[dict[str, Any]] = []
    for phase in queue.get("phases", []):
        for item in phase.get("items", []):
            if item.get("status") != "pending":
                continue
            deps = set(item.get("depends_on") or [])
            unmet = deps - milestones_met
            candidates.append(
                {
                    "phase": phase["phase"],
                    "id": item["id"],
                    "title": item["title"],
                    "priority": item.get("priority", 1),
                    "ready": not unmet,
                    "blocked_by": sorted(unmet),
                }
            )
    candidates.sort(
        key=lambda x: (-x["priority"], not x["ready"], x["phase"], x["id"])
    )
    return candidates[:5]


def _milestones_met(df: pd.DataFrame) -> set[str]:
    met: set[str] = set()
    if df.empty:
        return met
    per_station = Counter(df["station_name"])
    min_per = min(per_station.get(s, 0) for s in TARGET_STATIONS)
    total = len(df)
    if min_per >= 30:
        met.add("DATA_30_PER_STATION")
    if min_per >= 50:
        met.add("DATA_50_PER_STATION")
    if total >= 500:
        met.add("DATA_500")
    if total >= 1000:
        met.add("DATA_1000")
    return met


# ---------------------------------------------------------------------------
# 리포트 작성
# ---------------------------------------------------------------------------
def render_report(
    *,
    today_kst: datetime,
    tests_ok: bool,
    tests_summary: str,
    acc: dict[str, Any],
    health: dict[str, Any],
    matrix: dict[str, dict[str, str]],
    milestones: list[dict[str, Any]],
    candidates: list[dict[str, Any]],
) -> str:
    lines: list[str] = []
    lines.append(f"# 📅 데일리 리포트 — {today_kst.strftime('%Y-%m-%d')} (KST)")
    lines.append("")
    lines.append(
        f"> 자동 생성: {today_kst.strftime('%Y-%m-%d %H:%M KST')} · "
        "GitHub Actions `daily_dev_loop.yml`"
    )
    lines.append("")

    # 1. 테스트
    lines.append("## ✅ 회귀 테스트")
    icon = "🟢" if tests_ok else "🔴"
    lines.append(f"- {icon} `{tests_summary}`")
    lines.append("")

    # 2. 누적
    lines.append("## 📦 누적 데이터")
    lines.append(f"- 총 누적: **{acc['total']:,} 건**")
    if acc["total"] > 0:
        lines.append(
            f"- 시각 범위: {acc['first_time']} ~ {acc['last_time']} "
            f"({acc['unique_times']}개 unique 시각)"
        )
        lines.append("- 측정소별:")
        for name, cnt in acc["per_station"].items():
            lines.append(f"  - {name}: {cnt}건")
    lines.append("")

    # 3. 24h 성공률
    lines.append("## ⏱️ 최근 24시간 수집 성공률")
    lines.append(
        f"- {health['received']} / {health['expected']}건 = "
        f"**{health['rate'] * 100:.1f}%**"
    )
    if health["missing_hours"]:
        lines.append(
            f"- 누락 시각(최대 5개): {', '.join(health['missing_hours'])}"
        )
    lines.append("")

    # 4. Cpk 매트릭스
    lines.append("## 📐 Cp/Cpk 매트릭스 (daily basis)")
    if matrix:
        header = "| 측정소 | " + " | ".join(p.upper() for p in SPEC_LIMITS) + " |"
        sep = "|" + "|".join(["---"] * (len(SPEC_LIMITS) + 1)) + "|"
        lines.append(header)
        lines.append(sep)
        for station, row in matrix.items():
            vals = " | ".join(row.get(p, "—") for p in SPEC_LIMITS)
            lines.append(f"| {station} | {vals} |")
        lines.append("")
        lines.append("표기: `n=N` → 표본 부족 (최소 30), `기준없음` → 해당 basis USL 미정의")
    lines.append("")

    # 5. 마일스톤
    lines.append("## 🎯 데이터 마일스톤 진행률")
    for m in milestones:
        bar = "█" * int(m["pct"] / 10) + "░" * (10 - int(m["pct"] / 10))
        lines.append(f"- `{m['name']}`: {m['progress']} {bar} {m['pct']:.0f}%")
    lines.append("")

    # 6. 다음 후보 작업
    lines.append("## 🚀 다음 후보 작업 (PHASE_QUEUE.yml 기준)")
    if not candidates:
        lines.append("_큐에 대기 중인 작업이 없습니다._")
    else:
        for c in candidates:
            stars = "★" * c["priority"]
            ready = "✅ READY" if c["ready"] else f"⛔ blocked by {c['blocked_by']}"
            lines.append(f"- **[P{c['phase']}/{c['id']}]** {c['title']} — {stars} — {ready}")
    lines.append("")

    lines.append("---")
    lines.append(
        "🤖 *이 리포트는 매일 KST 09:15에 자동 생성됩니다. "
        "Claude 세션에서 다음 작업을 결정할 때 참조하세요.*"
    )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 메인
# ---------------------------------------------------------------------------
def main() -> int:
    today_kst = datetime.now(tz=KST)
    print(f"=== Daily Dev Loop @ {today_kst.strftime('%Y-%m-%d %H:%M KST')} ===")

    df = _load_df()
    print(f"📦 누적 데이터: {len(df)}건")

    print("✅ pytest 실행...")
    tests_ok, tests_summary = run_pytest()
    print(f"   결과: {tests_summary}")

    acc = accumulation_stats(df)
    health = health_24h(df)
    matrix = cpk_matrix(df, basis="daily")
    milestones = milestone_progress(df)
    candidates = next_candidates(df)

    report = render_report(
        today_kst=today_kst,
        tests_ok=tests_ok,
        tests_summary=tests_summary,
        acc=acc,
        health=health,
        matrix=matrix,
        milestones=milestones,
        candidates=candidates,
    )

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = REPORTS_DIR / f"{today_kst.strftime('%Y-%m-%d')}.md"
    out_path.write_text(report, encoding="utf-8")
    print(f"📝 리포트 저장: {out_path.relative_to(_PROJECT_ROOT)}")
    print(f"   ({len(report.splitlines())} lines, {len(report)} chars)")

    # latest.md 심볼릭 카피 (Streamlit Cloud에서 쉽게 링크)
    latest_path = REPORTS_DIR / "latest.md"
    latest_path.write_text(report, encoding="utf-8")

    return 0


if __name__ == "__main__":
    sys.exit(main())
