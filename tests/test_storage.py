"""저장소 모델·제약 검증.

in-memory SQLite로 별도 엔진을 생성해 모듈 전역 _engine과 독립 실행.
"""

from __future__ import annotations

from datetime import datetime

import pytest
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, SQLModel, create_engine, select

from src.storage.models import AirQualityMeasurement


def _make_memory_engine():
    """테스트용 in-memory SQLite 엔진 + 스키마 생성."""
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    return engine


class TestAirQualityMeasurementSchema:
    def test_insert_and_query_roundtrip(self) -> None:
        engine = _make_memory_engine()
        with Session(engine) as s:
            s.add(
                AirQualityMeasurement(
                    station_name="오창읍",
                    data_time=datetime(2026, 5, 27, 14, 0),
                    pm10=35.0,
                    pm25=18.0,
                    o3=0.025,
                    pm10_grade=1,
                )
            )
            s.commit()

        with Session(engine) as s:
            rows = list(s.exec(select(AirQualityMeasurement)).all())

        assert len(rows) == 1
        assert rows[0].station_name == "오창읍"
        assert rows[0].pm10 == 35.0
        assert rows[0].pm25_grade is None  # 미설정 컬럼은 NULL
        assert rows[0].created_at is not None  # default_factory로 자동 설정

    def test_unique_constraint_blocks_duplicate_station_datatime(self) -> None:
        """동일 (station_name, data_time) 두 번째 insert는 IntegrityError."""
        engine = _make_memory_engine()

        # 첫 번째 삽입은 정상
        with Session(engine) as s:
            s.add(
                AirQualityMeasurement(
                    station_name="오창읍",
                    data_time=datetime(2026, 5, 27, 14, 0),
                    pm10=35.0,
                )
            )
            s.commit()

        # 같은 (station, time) 다른 측정값 → UNIQUE 위반
        with Session(engine) as s:
            s.add(
                AirQualityMeasurement(
                    station_name="오창읍",
                    data_time=datetime(2026, 5, 27, 14, 0),
                    pm10=99.0,
                )
            )
            with pytest.raises(IntegrityError):
                s.commit()

    def test_different_stations_same_time_allowed(self) -> None:
        """다른 측정소는 같은 시각이어도 OK."""
        engine = _make_memory_engine()
        ts = datetime(2026, 5, 27, 14, 0)
        with Session(engine) as s:
            s.add(AirQualityMeasurement(station_name="오창읍", data_time=ts, pm10=35))
            s.add(AirQualityMeasurement(station_name="복대동", data_time=ts, pm10=42))
            s.add(AirQualityMeasurement(station_name="오송읍", data_time=ts, pm10=28))
            s.add(AirQualityMeasurement(station_name="용암동", data_time=ts, pm10=22))
            s.commit()

        with Session(engine) as s:
            rows = list(s.exec(select(AirQualityMeasurement)).all())
        assert len(rows) == 4
        assert {r.station_name for r in rows} == {"오창읍", "복대동", "오송읍", "용암동"}

    def test_same_station_different_time_allowed(self) -> None:
        """같은 측정소 다른 시각은 OK (시계열 누적의 기본 조건)."""
        engine = _make_memory_engine()
        with Session(engine) as s:
            for hour in (10, 11, 12, 13, 14):
                s.add(
                    AirQualityMeasurement(
                        station_name="오창읍",
                        data_time=datetime(2026, 5, 27, hour, 0),
                        pm10=30.0 + hour,
                    )
                )
            s.commit()

        with Session(engine) as s:
            rows = list(
                s.exec(
                    select(AirQualityMeasurement).order_by(
                        AirQualityMeasurement.data_time
                    )
                ).all()
            )
        assert len(rows) == 5
        assert rows[0].pm10 == 40.0
        assert rows[-1].pm10 == 44.0
