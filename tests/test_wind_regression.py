"""풍향·기상 결합 분석 단위 테스트. 합성 데이터로 기하·검정·회귀 검증."""

from __future__ import annotations

from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import pytest

from src.analysis.wind_regression import (
    InsufficientSampleError,
    angular_diff,
    bearing,
    directional_test,
    join_air_weather,
    pollution_rose,
    weather_regression,
    wind_sector,
)


class TestBearing:
    def test_due_north(self) -> None:
        # 같은 경도, 더 북쪽 → ~0°
        assert bearing(36.0, 127.0, 37.0, 127.0) == pytest.approx(0.0, abs=1.0)

    def test_due_east(self) -> None:
        assert bearing(36.0, 127.0, 36.0, 128.0) == pytest.approx(90.0, abs=1.0)

    def test_range(self) -> None:
        b = bearing(36.6, 127.3, 36.7, 127.5)
        assert 0.0 <= b < 360.0


class TestAngularDiff:
    def test_basic(self) -> None:
        assert angular_diff(10, 350) == pytest.approx(20.0)
        assert angular_diff(0, 180) == pytest.approx(180.0)
        assert angular_diff(90, 90) == 0.0


class TestWindSector:
    def test_sectors(self) -> None:
        assert wind_sector(0) == "N"
        assert wind_sector(90) == "E"
        assert wind_sector(180) == "S"
        assert wind_sector(270) == "W"
        assert wind_sector(45) == "NE"
        assert wind_sector(359) == "N"  # wrap


def _synth(n=400, seed=0):
    """합성: 풍향 270°(서)에서 불 때 PM2.5가 높도록 심은 데이터."""
    rng = np.random.default_rng(seed)
    wd = rng.uniform(0, 360, n)
    base = rng.normal(20, 5, n)
    # 서풍(270±22.5)일 때 +25 가산
    boost = np.where(np.abs(((wd - 270 + 180) % 360) - 180) <= 22.5, 25.0, 0.0)
    pm25 = base + boost
    ws = rng.uniform(0.5, 5, n)
    t0 = datetime(2026, 6, 1)
    times = [t0 + timedelta(hours=i) for i in range(n)]
    return pd.DataFrame({"data_time": times, "pm25": pm25, "wd": wd, "ws": ws,
                         "ta": rng.normal(22, 3, n), "hm": rng.uniform(40, 80, n),
                         "rn": np.zeros(n)})


class TestPollutionRose:
    def test_rose_keys(self) -> None:
        rose = pollution_rose(_synth(), "pm25")
        assert set(rose).issubset({"N", "NE", "E", "SE", "S", "SW", "W", "NW"})

    def test_west_highest(self) -> None:
        rose = pollution_rose(_synth(), "pm25")
        # 서풍에 농도를 심었으니 W가 최댓값
        assert max(rose, key=rose.get) == "W"


class TestDirectionalTest:
    def test_detects_planted_direction(self) -> None:
        df = _synth()
        res = directional_test(df, "pm25", source_bearing=270.0)
        assert res.significant
        assert res.diff > 0  # 서풍일 때 더 높음
        assert res.mean_in > res.mean_out

    def test_null_direction_not_significant(self) -> None:
        df = _synth()
        # 농도를 안 심은 방향(동, 90°) → 유의하지 않아야
        res = directional_test(df, "pm25", source_bearing=90.0)
        assert not res.significant or res.diff <= 0

    def test_insufficient_sample(self) -> None:
        df = _synth(n=10)
        with pytest.raises(InsufficientSampleError):
            directional_test(df, "pm25", source_bearing=270.0)


class TestWeatherRegression:
    def test_runs_and_r2_range(self) -> None:
        df = _synth()
        res = weather_regression(df, "pm25", predictors=("ws", "ta", "hm"))
        assert res.n > 0
        assert -0.01 <= res.r2 <= 1.0
        assert set(res.coef) == {"ws", "ta", "hm"}

    def test_insufficient_sample(self) -> None:
        with pytest.raises(InsufficientSampleError):
            weather_regression(_synth(n=5), "pm25")


class TestJoin:
    def test_hourly_join(self) -> None:
        air = pd.DataFrame({"data_time": [datetime(2026, 6, 1, 9, 0)], "pm25": [30.0]})
        wx = pd.DataFrame({"obs_time": [datetime(2026, 6, 1, 9, 0)], "ta": [20.0],
                           "hm": [50.0], "ws": [2.0], "wd": [180.0], "rn": [0.0]})
        m = join_air_weather(air, wx)
        assert len(m) == 1
        assert m.iloc[0]["wd"] == 180.0 and m.iloc[0]["pm25"] == 30.0
