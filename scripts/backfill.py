"""누락 시간대 백필(backfill) 스크립트.

시도별 실시간 엔드포인트는 '현재 시각' 1건만 주므로, GitHub Actions cron이
드롭한 과거 시간대는 평소엔 영영 못 채운다. 이 스크립트는 측정소별 기간조회
(getMsrstnAcctoRltmMesureDnsty, dataTerm=DAILY)로 **최근 약 24시간의 시간별 실측**을
가져와 INSERT OR IGNORE로 메운다. 더미 데이터가 아니라 전부 에어코리아 실측이다.

실행:
    uv run python scripts/backfill.py            # DAILY(최근 24h)
    uv run python scripts/backfill.py 3MONTH     # 더 긴 기간

주의:
- INSERT OR IGNORE라 이미 있는 시각은 자동 스킵 → 반복 실행 안전.
- 측정소당 1회 호출 + 매너 차원 0.5초 간격.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from loguru import logger  # noqa: E402

from src.collectors.airkorea import AirkoreaClient, to_measurement  # noqa: E402
from src.config import LOG_LEVEL, TARGET_STATIONS  # noqa: E402
from src.storage.database import (  # noqa: E402
    init_db,
    insert_measurements,
    query_all,
)


def configure_logging() -> None:
    """loguru 로깅 설정."""
    logger.remove()
    logger.add(
        sys.stderr,
        level=LOG_LEVEL,
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
            "<level>{level: <8}</level> | <level>{message}</level>"
        ),
    )


def main() -> int:
    """측정소별 기간조회로 누락 시간대를 백필한다."""
    data_term = sys.argv[1] if len(sys.argv) > 1 else "DAILY"
    configure_logging()
    logger.info("=" * 60)
    logger.info(f"백필 시작: dataTerm={data_term} / 대상 {TARGET_STATIONS}")

    before = len(query_all())
    init_db()

    all_measurements = []
    with AirkoreaClient() as client:
        for name in TARGET_STATIONS:
            try:
                items = client.get_station_period(name, data_term=data_term)
            except RuntimeError as exc:
                logger.warning(f"  {name}: 조회 실패 — 스킵 ({exc})")
                continue
            for item in items:
                m = to_measurement(item)
                if m is not None:
                    all_measurements.append(m)
            time.sleep(0.5)  # API 매너

    if not all_measurements:
        logger.error("백필할 측정 레코드가 없습니다.")
        return 1

    attempted, inserted = insert_measurements(all_measurements)
    after = len(query_all())
    logger.info(
        f"백필 결과: 변환 {attempted}건 / 신규 삽입 {inserted}건 "
        f"(중복 스킵 {attempted - inserted}건)"
    )
    logger.info(f"DB 누적: {before}건 -> {after}건 (+{after - before})")
    logger.info("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
