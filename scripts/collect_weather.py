"""기상청 ASOS 시간자료 1회 수집 (Phase 4).

최근 3일 구간의 청주(131) 시간자료를 조회해 SQLite에 저장한다.
INSERT OR IGNORE라 매시 재실행해도 중복 없이 누락만 채운다(멱등 + 백필).

실행:
    uv run python scripts/collect_weather.py
WEATHER_API_KEY 미설정 시 안내 후 종료(다른 워크플로에 영향 없게 exit 0).
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from loguru import logger  # noqa: E402

from src.config import KMA_ASOS_STATION_ID, WEATHER_API_KEY  # noqa: E402

KST = timezone(timedelta(hours=9))
BACKFILL_DAYS = 3


def main() -> int:
    if not WEATHER_API_KEY:
        logger.warning(
            "WEATHER_API_KEY 미설정 — 기상 수집 스킵. 공공데이터포털 "
            "'기상청 지상(ASOS) 시간자료' 활용신청 후 WEATHER_API_KEY 등록 필요."
        )
        return 0  # 다른 워크플로/스텝에 영향 없게 정상 종료

    from src.collectors.weather import KmaAsosClient
    from src.storage.database import init_db, insert_weather

    now = datetime.now(KST)
    # 기상청 ASOS는 전날 자료까지만 제공 — end를 어제 23시로 고정
    yesterday = (now - timedelta(days=1)).replace(hour=23, minute=0, second=0)
    start = now - timedelta(days=BACKFILL_DAYS)
    init_db()
    try:
        with KmaAsosClient() as client:
            obs = client.get_hourly(
                start_dt=start.strftime("%Y%m%d"), start_hh=start.strftime("%H"),
                end_dt=yesterday.strftime("%Y%m%d"), end_hh="23",
                station_id=KMA_ASOS_STATION_ID,
            )
    except Exception as e:  # noqa: BLE001 — 수집 실패가 전체 워크플로를 깨지 않게
        logger.error(f"기상 수집 실패(무시): {e}")
        return 0

    attempted, inserted = insert_weather(obs)
    logger.info(f"기상 수집 완료: 조회 {attempted}건 / 신규 {inserted}건")
    return 0


if __name__ == "__main__":
    sys.exit(main())
