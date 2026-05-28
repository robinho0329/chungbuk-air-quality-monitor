"""Prefect 수집 워크플로우.

매시 정각 5분 후 에어코리아 시도별 실시간 측정정보를 수집해
4개 측정소만 필터링한 뒤 SQLite에 저장한다.

task 레벨 재시도 정책:
- fetch_realtime: 재시도 3회, 60초 지연 (API 일시 장애 대응)
- save_measurements: 재시도 1회, 5초 지연 (DB는 보통 즉시 풀림)

실행 방법:
    # 1회 실행 (디버깅용)
    uv run python flows/collect_flow.py

    # 스케줄 deployment 등록 (별도 터미널에서 worker 필요)
    prefect server start            # 첫 터미널
    python -c "from flows.collect_flow import deploy; deploy()"   # 두 번째
    prefect worker start --pool default-pool                       # 세 번째
"""

from __future__ import annotations

import sys
from pathlib import Path

# 프로젝트 루트를 sys.path에 추가
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from prefect import flow, get_run_logger, task  # noqa: E402
from prefect.schedules import Cron  # noqa: E402

from src.collectors.airkorea import (  # noqa: E402
    AirkoreaClient,
    filter_target_stations,
    to_measurement,
)
from src.config import TARGET_SIDO, TARGET_STATIONS  # noqa: E402
from src.storage.database import init_db, insert_measurements  # noqa: E402
from src.storage.models import AirQualityMeasurement  # noqa: E402


@task(retries=3, retry_delay_seconds=60, log_prints=False)
def fetch_realtime(sido_name: str) -> list[dict]:
    """에어코리아 시도별 실시간 측정정보를 호출한다.

    Args:
        sido_name: 시도명 (예: '충북').

    Returns:
        API 응답 items 리스트.
    """
    logger = get_run_logger()
    with AirkoreaClient() as client:
        items = client.get_sido_realtime(sido_name=sido_name)
    logger.info(f"fetch_realtime: {sido_name} -> {len(items)}건 응답")
    return items


@task
def filter_to_targets(
    items: list[dict], targets: tuple[str, ...]
) -> list[dict]:
    """대상 측정소만 필터링한다."""
    logger = get_run_logger()
    filtered = filter_target_stations(items, targets)
    logger.info(f"filter_to_targets: 전체 {len(items)} -> 대상 {len(filtered)}")
    return filtered


@task
def transform(items: list[dict]) -> list[AirQualityMeasurement]:
    """API dict를 AirQualityMeasurement 인스턴스로 변환."""
    logger = get_run_logger()
    converted: list[AirQualityMeasurement] = []
    for item in items:
        m = to_measurement(item)
        if m is not None:
            converted.append(m)
    logger.info(
        f"transform: 입력 {len(items)}건 -> 변환 성공 {len(converted)}건"
    )
    return converted


@task(retries=1, retry_delay_seconds=5)
def save_measurements(
    records: list[AirQualityMeasurement],
) -> tuple[int, int]:
    """SQLite에 저장. (시도, 삽입) 카운트 반환."""
    logger = get_run_logger()
    init_db()
    attempted, inserted = insert_measurements(records)
    logger.info(
        f"save_measurements: 시도 {attempted}건 / 신규 삽입 {inserted}건"
    )
    return attempted, inserted


@flow(name="airkorea-collect", log_prints=False)
def collect_flow(
    sido_name: str = TARGET_SIDO,
    targets: tuple[str, ...] = TARGET_STATIONS,
) -> dict[str, int]:
    """전체 수집 파이프라인.

    Returns:
        {'attempted': N, 'inserted': M} - 저장 통계.
    """
    logger = get_run_logger()
    logger.info(f"수집 시작: sido={sido_name}, targets={targets}")

    raw = fetch_realtime(sido_name=sido_name)
    filtered = filter_to_targets(raw, targets)
    records = transform(filtered)
    attempted, inserted = save_measurements(records)

    logger.info(f"수집 완료: {attempted}건 시도 / {inserted}건 삽입")
    return {"attempted": attempted, "inserted": inserted}


# ----------------------------------------------------------------------
# Deployment: 매시 정각 5분 후 실행
# ----------------------------------------------------------------------
def deploy() -> None:
    """Prefect deployment 생성. cron: 매시 5분."""
    collect_flow.serve(
        name="hourly-airkorea-collect",
        schedule=Cron("5 * * * *", timezone="Asia/Seoul"),
        description=(
            "매시 5분에 에어코리아 시도별 실시간 측정정보를 수집해 "
            "4개 측정소(오창읍/복대동/오송읍/용암동)를 SQLite에 저장."
        ),
        tags=["airkorea", "phase3-foretaste"],
    )


if __name__ == "__main__":
    # 직접 실행 시: 1회 수집 (디버깅·검증용)
    result = collect_flow()
    print(f"\n결과: {result}")
