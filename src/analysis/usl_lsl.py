"""대기환경보전법 환경기준 (USL/LSL) 상수 모듈.

출처: 대기환경보전법 시행규칙 별표 (한국).
6개 주요 오염물질에 대한 시간/24시간/연평균 USL을 제공한다.
LSL은 모두 0으로 고정 (대기질은 낮을수록 좋음).

단위:
- PM10, PM2.5: ㎍/㎥
- O3, NO2, SO2, CO: ppm
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SpecLimits:
    """오염물질의 명세 한계(Specification Limits) 정의.

    Attributes:
        pollutant: 오염물질 식별자 (소문자, 예: 'pm10').
        lsl: 하한 명세 한계. 대기질은 모두 0.
        usl_hourly: 1시간 평균 USL. 미정의면 None.
        usl_daily: 24시간 평균 USL. 미정의면 None.
        usl_annual: 연평균 USL. 미정의면 None.
        unit: 단위 문자열.
        description: 한국어 설명.
    """

    pollutant: str
    lsl: float
    usl_hourly: float | None
    usl_daily: float | None
    usl_annual: float | None
    unit: str
    description: str

    def usl_for(self, basis: str) -> float | None:
        """기준 시간(basis)에 해당하는 USL을 반환.

        Args:
            basis: 'hourly', 'daily', 'annual' 중 하나.

        Returns:
            해당 USL. 정의되지 않은 경우 None.

        Raises:
            ValueError: basis가 허용된 값이 아닐 때.
        """
        if basis == "hourly":
            return self.usl_hourly
        if basis == "daily":
            return self.usl_daily
        if basis == "annual":
            return self.usl_annual
        raise ValueError(
            f"basis는 'hourly'/'daily'/'annual' 중 하나여야 합니다. 받은 값: {basis!r}"
        )


# 대기환경보전법 환경기준 (대한민국)
SPEC_LIMITS: dict[str, SpecLimits] = {
    "pm10": SpecLimits(
        pollutant="pm10",
        lsl=0.0,
        usl_hourly=None,  # PM10은 1시간 기준치 없음
        usl_daily=100.0,
        usl_annual=50.0,
        unit="㎍/㎥",
        description="미세먼지 (PM10)",
    ),
    "pm25": SpecLimits(
        pollutant="pm25",
        lsl=0.0,
        usl_hourly=None,
        usl_daily=35.0,
        usl_annual=15.0,
        unit="㎍/㎥",
        description="초미세먼지 (PM2.5)",
    ),
    "o3": SpecLimits(
        pollutant="o3",
        lsl=0.0,
        usl_hourly=0.1,
        usl_daily=None,
        usl_annual=None,
        unit="ppm",
        description="오존 (O3)",
    ),
    "no2": SpecLimits(
        pollutant="no2",
        lsl=0.0,
        usl_hourly=0.1,
        usl_daily=0.06,
        usl_annual=0.03,
        unit="ppm",
        description="이산화질소 (NO2)",
    ),
    "so2": SpecLimits(
        pollutant="so2",
        lsl=0.0,
        usl_hourly=0.15,
        usl_daily=0.05,
        usl_annual=0.02,
        unit="ppm",
        description="아황산가스 (SO2)",
    ),
    "co": SpecLimits(
        pollutant="co",
        lsl=0.0,
        usl_hourly=25.0,
        usl_daily=None,
        usl_annual=None,
        unit="ppm",
        description="일산화탄소 (CO)",
    ),
}


def get_spec(pollutant: str) -> SpecLimits:
    """오염물질 식별자로 SpecLimits를 조회한다.

    Args:
        pollutant: 'pm10', 'pm25', 'o3', 'no2', 'so2', 'co' 중 하나.

    Returns:
        SpecLimits 인스턴스.

    Raises:
        KeyError: 알 수 없는 오염물질명.
    """
    key = pollutant.lower()
    if key not in SPEC_LIMITS:
        raise KeyError(
            f"알 수 없는 오염물질: {pollutant!r}. "
            f"허용: {sorted(SPEC_LIMITS.keys())}"
        )
    return SPEC_LIMITS[key]
