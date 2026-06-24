"""SQLModel 기반 데이터 스키마.

에어코리아 시도별 실시간 측정정보 응답을 그대로 보존하는 와이드 테이블 구조.
측정값과 등급을 모두 저장한다. 결측은 NULL로 처리한다.
중복 키는 (station_name, data_time).
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel, UniqueConstraint


class AirQualityMeasurement(SQLModel, table=True):
    """대기질 측정 데이터 1행.

    에어코리아 응답 1건 = 측정소 1곳의 특정 시각 측정값.
    """

    __tablename__ = "air_quality_measurement"
    __table_args__ = (
        UniqueConstraint(
            "station_name", "data_time", name="uq_station_datatime"
        ),
    )

    id: Optional[int] = Field(default=None, primary_key=True)

    # 식별자
    station_name: str = Field(index=True, description="측정소명 (예: 오창읍)")
    data_time: datetime = Field(index=True, description="측정 시각")

    # 측정값 (단위: PM은 ㎍/㎥, 그 외는 ppm)
    pm10: Optional[float] = Field(default=None, description="PM10 (㎍/㎥)")
    pm25: Optional[float] = Field(default=None, description="PM2.5 (㎍/㎥)")
    o3: Optional[float] = Field(default=None, description="오존 O3 (ppm)")
    no2: Optional[float] = Field(default=None, description="이산화질소 NO2 (ppm)")
    so2: Optional[float] = Field(default=None, description="아황산가스 SO2 (ppm)")
    co: Optional[float] = Field(default=None, description="일산화탄소 CO (ppm)")
    khai: Optional[float] = Field(default=None, description="통합대기환경지수 KHAI")

    # 등급 (1=좋음, 2=보통, 3=나쁨, 4=매우나쁨)
    pm10_grade: Optional[int] = Field(default=None)
    pm25_grade: Optional[int] = Field(default=None)
    o3_grade: Optional[int] = Field(default=None)
    no2_grade: Optional[int] = Field(default=None)
    so2_grade: Optional[int] = Field(default=None)
    co_grade: Optional[int] = Field(default=None)
    khai_grade: Optional[int] = Field(default=None)

    # 결측 플래그 (API 응답의 *Flag 필드. 점검/장비점검/통신장애 등)
    flag: Optional[str] = Field(default=None, description="결측 사유 플래그")

    # 메타
    created_at: datetime = Field(
        default_factory=datetime.now,
        description="DB 저장 시각",
    )


class WeatherObservation(SQLModel, table=True):
    """기상청 ASOS 시간자료 1행 (청주 종관기상관측소).

    대기질 측정소들(반경 ~15km)이 공유하는 단일 기상관측. obs_time으로 대기질
    data_time과 시간 단위 조인해 풍향 회귀·기상 보정 SPC에 사용한다.
    중복 키는 (station_id, obs_time).
    """

    __tablename__ = "weather_observation"
    __table_args__ = (
        UniqueConstraint("station_id", "obs_time", name="uq_wxstation_obstime"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)

    # 식별자
    station_id: int = Field(index=True, description="ASOS 지점번호 (청주=131)")
    obs_time: datetime = Field(index=True, description="관측 시각 (정시)")

    # 관측값
    ta: Optional[float] = Field(default=None, description="기온 (℃)")
    hm: Optional[float] = Field(default=None, description="상대습도 (%)")
    ws: Optional[float] = Field(default=None, description="풍속 (m/s)")
    wd: Optional[float] = Field(default=None, description="풍향 (deg, 0=북·시계방향)")
    rn: Optional[float] = Field(default=None, description="강수량 (mm, 무강수=0)")

    created_at: datetime = Field(
        default_factory=datetime.now, description="DB 저장 시각"
    )
