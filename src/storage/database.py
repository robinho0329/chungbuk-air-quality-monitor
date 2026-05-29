"""SQLite 데이터베이스 초기화 및 CRUD 헬퍼.

엔진/세션은 모듈 레벨에서 lazy하게 생성된다.
insert_measurements는 (station_name, data_time) 중복은 무시(SQLite INSERT OR IGNORE).
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime
from pathlib import Path
from typing import Optional

from loguru import logger
from sqlalchemy import Engine, text
from sqlmodel import Session, SQLModel, create_engine, select

from src.config import DATABASE_URL
from src.storage.models import AirQualityMeasurement

# 모듈 전역 엔진. 첫 호출 시 생성.
_engine: Optional[Engine] = None


def get_engine() -> Engine:
    """SQLAlchemy 엔진을 반환한다. 최초 호출 시 생성, 이후 재사용."""
    global _engine
    if _engine is None:
        # SQLite 파일 디렉토리 보장
        if DATABASE_URL.startswith("sqlite:///"):
            db_path = Path(DATABASE_URL.replace("sqlite:///", ""))
            db_path.parent.mkdir(parents=True, exist_ok=True)
        _engine = create_engine(DATABASE_URL, echo=False)
        logger.debug(f"DB engine 생성: {DATABASE_URL}")
    return _engine


def init_db() -> None:
    """모든 SQLModel 테이블을 생성한다 (멱등)."""
    engine = get_engine()
    SQLModel.metadata.create_all(engine)
    logger.info("DB 초기화 완료")


def insert_measurements(
    records: Iterable[AirQualityMeasurement],
) -> tuple[int, int]:
    """측정 데이터를 일괄 저장한다. 중복(station_name, data_time)은 무시.

    SQLite의 INSERT OR IGNORE를 사용해 UNIQUE 제약 충돌을 silent하게 처리한다.

    Args:
        records: 저장할 AirQualityMeasurement 인스턴스 iterable.

    Returns:
        (시도 건수, 실제 삽입 건수).
    """
    engine = get_engine()
    records_list = list(records)
    attempted = len(records_list)
    inserted = 0

    if attempted == 0:
        logger.warning("insert_measurements: 입력 레코드가 비어있습니다.")
        return 0, 0

    # SQLModel 인스턴스를 dict로 변환 후 INSERT OR IGNORE 사용
    with engine.begin() as conn:
        stmt = text(
            """
            INSERT OR IGNORE INTO air_quality_measurement
                (station_name, data_time,
                 pm10, pm25, o3, no2, so2, co, khai,
                 pm10_grade, pm25_grade, o3_grade, no2_grade,
                 so2_grade, co_grade, khai_grade,
                 flag, created_at)
            VALUES
                (:station_name, :data_time,
                 :pm10, :pm25, :o3, :no2, :so2, :co, :khai,
                 :pm10_grade, :pm25_grade, :o3_grade, :no2_grade,
                 :so2_grade, :co_grade, :khai_grade,
                 :flag, :created_at)
            """
        )
        for r in records_list:
            payload = r.model_dump(exclude={"id"})
            result = conn.execute(stmt, payload)
            inserted += result.rowcount or 0

    logger.info(
        f"insert_measurements: 시도 {attempted}건 / 삽입 {inserted}건 "
        f"(중복 스킵 {attempted - inserted}건)"
    )
    return attempted, inserted


def query_all() -> list[AirQualityMeasurement]:
    """모든 측정 데이터를 시간 순으로 반환한다."""
    engine = get_engine()
    with Session(engine) as session:
        stmt = select(AirQualityMeasurement).order_by(
            AirQualityMeasurement.data_time,
            AirQualityMeasurement.station_name,
        )
        return list(session.exec(stmt).all())


def query_pairs_since(since: datetime) -> set[tuple[str, datetime]]:
    """since 이후의 (station_name, data_time) 쌍 집합을 반환한다.

    self-healing 갭 탐지용. 전체 로우 적재 없이 키만 가져온다.
    """
    engine = get_engine()
    with Session(engine) as session:
        stmt = (
            select(
                AirQualityMeasurement.station_name,
                AirQualityMeasurement.data_time,
            )
            .where(AirQualityMeasurement.data_time >= since)
        )
        return {(name, dt) for name, dt in session.exec(stmt).all()}


def query_by_station(station_name: str) -> list[AirQualityMeasurement]:
    """특정 측정소의 모든 측정 데이터를 시간 순으로 반환한다."""
    engine = get_engine()
    with Session(engine) as session:
        stmt = (
            select(AirQualityMeasurement)
            .where(AirQualityMeasurement.station_name == station_name)
            .order_by(AirQualityMeasurement.data_time)
        )
        return list(session.exec(stmt).all())
