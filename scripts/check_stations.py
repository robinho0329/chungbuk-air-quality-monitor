"""대상 4개 측정소의 정확한 stationName과 좌표를 확인하는 스크립트.

에어코리아 측정소정보 API로 충북 측정소 목록을 받아와,
TARGET_STATIONS와 매칭되는 항목을 출력한다.
결과를 보고 docs/stations.md를 업데이트한다.

실행 예:
    uv run python scripts/check_stations.py
"""

from __future__ import annotations

import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from loguru import logger  # noqa: E402

from src.collectors.airkorea import AirkoreaClient  # noqa: E402
from src.config import LOG_LEVEL, TARGET_STATIONS  # noqa: E402


def configure_logging() -> None:
    logger.remove()
    logger.add(sys.stderr, level=LOG_LEVEL, format="{time:HH:mm:ss} | {level} | {message}")


def main() -> int:
    configure_logging()
    logger.info(f"충북 측정소 정보 조회 (대상: {TARGET_STATIONS})")

    with AirkoreaClient() as client:
        stations = client.get_stations(addr="충북", num_of_rows=200)

    if not stations:
        logger.error("측정소 정보 조회 결과가 비어있습니다.")
        return 1

    target_set = set(TARGET_STATIONS)
    matched: dict[str, dict] = {}
    for s in stations:
        name = (s.get("stationName") or "").strip()
        if name in target_set:
            matched[name] = s

    logger.info(f"전체 충북 측정소: {len(stations)}건")
    logger.info(f"대상 매칭: {len(matched)}/{len(TARGET_STATIONS)}건")

    print()
    print("=" * 72)
    print(f"{'측정소명':<10} {'주소':<40} {'위도':>10} {'경도':>10}")
    print("=" * 72)
    for name in TARGET_STATIONS:
        s = matched.get(name)
        if s is None:
            print(f"{name:<10} (찾지 못함)")
            continue
        addr = (s.get("addr") or "").strip()
        dm_x = s.get("dmX") or ""  # 위도
        dm_y = s.get("dmY") or ""  # 경도
        print(f"{name:<10} {addr:<40} {dm_x:>10} {dm_y:>10}")
    print("=" * 72)

    missing = [n for n in TARGET_STATIONS if n not in matched]
    if missing:
        logger.warning(
            f"매칭 실패 측정소: {missing}. "
            f"실제 충북 측정소명을 확인하세요."
        )
        # 충북 측정소 전체 목록을 보조 정보로 출력
        print("\n[참고] 충북 측정소 전체 stationName:")
        names = sorted({(s.get("stationName") or "").strip() for s in stations})
        for n in names:
            print(f"  - {n}")
        return 2

    return 0


if __name__ == "__main__":
    sys.exit(main())
