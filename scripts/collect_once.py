"""수집 → 저장 1회 실행 스크립트 (Phase 1 MVP 검증용).

실행 예:
    uv run python scripts/collect_once.py

동작:
1. .env에서 AIRKOREA_API_KEY 로드
2. 시도별 실시간 측정정보 API로 충북 전체 측정소 조회
3. 대상 4개 측정소(오창읍, 복대동, 오송읍, 용암동)만 필터링
4. AirQualityMeasurement 인스턴스로 변환
5. SQLite에 저장 (중복 키는 무시)
6. 저장 결과 요약 출력
"""

from __future__ import annotations

import sys
from pathlib import Path

# 프로젝트 루트를 sys.path에 추가 (스크립트 직접 실행 대응)
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from loguru import logger  # noqa: E402

from src.collectors.airkorea import (  # noqa: E402
    AirkoreaClient,
    filter_target_stations,
    to_measurement,
)
from src.config import LOG_LEVEL, TARGET_SIDO, TARGET_STATIONS  # noqa: E402
from src.storage.database import (  # noqa: E402
    init_db,
    insert_measurements,
    query_all,
)


def configure_logging() -> None:
    """loguru 로깅을 표준 포맷으로 설정한다."""
    logger.remove()
    logger.add(
        sys.stderr,
        level=LOG_LEVEL,
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
            "<level>{message}</level>"
        ),
    )


def main() -> int:
    """수집-저장 1회 사이클을 실행한다. 종료 코드 반환."""
    configure_logging()
    logger.info("=" * 60)
    logger.info("Phase 1 MVP: 수집 → 저장 1회 실행")
    logger.info(f"대상 시도: {TARGET_SIDO}")
    logger.info(f"대상 측정소: {TARGET_STATIONS}")
    logger.info("=" * 60)

    # 1. DB 초기화
    init_db()

    # 2. API 호출
    with AirkoreaClient() as client:
        items = client.get_sido_realtime(sido_name=TARGET_SIDO)

    if not items:
        logger.error("API 응답에 측정소가 없습니다. 종료합니다.")
        return 1

    # 3. 대상 4개 측정소 필터링
    filtered = filter_target_stations(items, TARGET_STATIONS)
    if not filtered:
        logger.error(
            f"대상 측정소를 찾지 못했습니다. "
            f"응답에 포함된 station 목록: "
            f"{sorted({(i.get('stationName') or '').strip() for i in items})}"
        )
        return 2

    # 4. 변환
    measurements = []
    for item in filtered:
        m = to_measurement(item)
        if m is not None:
            measurements.append(m)

    if not measurements:
        logger.error("변환 가능한 측정 레코드가 없습니다.")
        return 3

    # 5. 저장
    attempted, inserted = insert_measurements(measurements)
    logger.info(f"저장 결과: 시도 {attempted}건 / 신규 삽입 {inserted}건")

    # 6. 검증: 저장된 데이터 요약
    all_records = query_all()
    logger.info(f"DB 총 누적 레코드: {len(all_records)}건")
    if all_records:
        latest_by_station: dict[str, str] = {}
        for r in all_records:
            latest_by_station[r.station_name] = r.data_time.isoformat()
        logger.info("측정소별 최신 데이터 시각:")
        for name in TARGET_STATIONS:
            ts = latest_by_station.get(name, "(없음)")
            logger.info(f"  - {name}: {ts}")

    logger.info("=" * 60)
    logger.info("수집-저장 1회 사이클 완료")
    return 0


if __name__ == "__main__":
    sys.exit(main())
