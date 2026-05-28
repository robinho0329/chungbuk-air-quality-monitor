"""에어코리아 수집기의 순수 함수 단위 테스트.

API 호출은 mock 없이 진행. 변환·필터·마스킹 로직만 검증.
실제 API 응답 구조를 그대로 모사한 dict로 입력한다.
"""

from __future__ import annotations

from datetime import datetime

import pytest

from src.collectors.airkorea import (
    _mask_key,
    _parse_datetime,
    _parse_float,
    _parse_int,
    _scrub_key,
    filter_target_stations,
    to_measurement,
)


# ----------------------------------------------------------------------
# _parse_float
# ----------------------------------------------------------------------
class TestParseFloat:
    def test_numeric_string(self) -> None:
        assert _parse_float("12.3") == 12.3

    def test_integer_input(self) -> None:
        assert _parse_float(5) == 5.0

    def test_missing_dash(self) -> None:
        assert _parse_float("-") is None

    def test_empty_string(self) -> None:
        assert _parse_float("") is None

    def test_none(self) -> None:
        assert _parse_float(None) is None

    def test_invalid_string(self) -> None:
        assert _parse_float("abc") is None

    def test_nan_input(self) -> None:
        assert _parse_float(float("nan")) is None


# ----------------------------------------------------------------------
# _parse_int
# ----------------------------------------------------------------------
class TestParseInt:
    def test_basic(self) -> None:
        assert _parse_int("3") == 3

    def test_float_string_truncates(self) -> None:
        assert _parse_int("3.7") == 3

    def test_missing_dash(self) -> None:
        assert _parse_int("-") is None

    def test_none(self) -> None:
        assert _parse_int(None) is None

    def test_invalid(self) -> None:
        assert _parse_int("xyz") is None


# ----------------------------------------------------------------------
# _parse_datetime
# ----------------------------------------------------------------------
class TestParseDatetime:
    def test_standard_format(self) -> None:
        assert _parse_datetime("2026-05-27 14:00") == datetime(2026, 5, 27, 14, 0)

    def test_missing_dash(self) -> None:
        assert _parse_datetime("-") is None

    def test_none(self) -> None:
        assert _parse_datetime(None) is None

    def test_invalid_format(self) -> None:
        # 슬래시 구분자는 비표준이므로 None 반환
        assert _parse_datetime("2026/05/27 14:00") is None


# ----------------------------------------------------------------------
# _scrub_key (보안: serviceKey 마스킹)
# ----------------------------------------------------------------------
class TestScrubKey:
    SAMPLE_KEY = "c17112965c3cb4c87aa9f8d06feec7e5640981403d6ecfa0915e1d6b7e2e839d"

    def test_replaces_service_key_param(self) -> None:
        masked = _scrub_key(f"https://x?serviceKey={self.SAMPLE_KEY}&other=v")
        assert self.SAMPLE_KEY not in masked
        assert "***MASKED***" in masked

    def test_case_insensitive(self) -> None:
        masked = _scrub_key(f"https://x?SERVICEKEY={self.SAMPLE_KEY}")
        assert self.SAMPLE_KEY not in masked

    def test_preserves_other_params(self) -> None:
        masked = _scrub_key(
            f"https://x?serviceKey={self.SAMPLE_KEY}&ver=1.3&sidoName=충북"
        )
        assert "ver=1.3" in masked
        assert "sidoName=충북" in masked

    def test_no_key_in_text(self) -> None:
        text = "no key here"
        assert _scrub_key(text) == text

    def test_multiple_occurrences(self) -> None:
        text = f"a?serviceKey={self.SAMPLE_KEY} and b?serviceKey={self.SAMPLE_KEY}"
        masked = _scrub_key(text)
        assert self.SAMPLE_KEY not in masked
        assert masked.count("***MASKED***") == 2


class TestMaskKey:
    def test_short_key(self) -> None:
        assert _mask_key("short") == "***"

    def test_long_key_shows_prefix_and_suffix(self) -> None:
        key = "c17112965c3cb4c87aa9f8d06feec7e5640981403d6ecfa0915e1d6b7e2e839d"
        masked = _mask_key(key)
        assert masked.startswith("c171")
        assert masked.endswith("839d")
        assert "..." in masked
        assert key not in masked  # 중간부 마스킹 확인


# ----------------------------------------------------------------------
# to_measurement (API dict -> AirQualityMeasurement)
# ----------------------------------------------------------------------
def _sample_api_item(**overrides: object) -> dict[str, object]:
    """에어코리아 시도별 실시간 응답 1건의 표본을 만든다."""
    base: dict[str, object] = {
        "stationName": "오창읍",
        "dataTime": "2026-05-27 14:00",
        "pm10Value": "35",
        "pm25Value": "18",
        "o3Value": "0.025",
        "no2Value": "0.012",
        "so2Value": "0.003",
        "coValue": "0.5",
        "khaiValue": "60",
        "pm10Grade": "1",
        "pm25Grade": "2",
        "o3Grade": "1",
        "no2Grade": "1",
        "so2Grade": "1",
        "coGrade": "1",
        "khaiGrade": "2",
    }
    base.update(overrides)
    return base


class TestToMeasurement:
    def test_full_conversion(self) -> None:
        m = to_measurement(_sample_api_item())
        assert m is not None
        assert m.station_name == "오창읍"
        assert m.data_time == datetime(2026, 5, 27, 14, 0)
        assert m.pm10 == 35.0
        assert m.pm25 == 18.0
        assert m.o3 == 0.025
        assert m.khai == 60.0
        assert m.pm10_grade == 1
        assert m.pm25_grade == 2

    def test_missing_values_become_none(self) -> None:
        m = to_measurement(_sample_api_item(pm25Value="-", o3Value="-"))
        assert m is not None
        assert m.pm25 is None
        assert m.o3 is None
        assert m.pm10 == 35.0  # 정상 값은 유지

    def test_missing_station_returns_none(self) -> None:
        # 측정소명 없으면 저장 불가 → None
        assert to_measurement(_sample_api_item(stationName="")) is None

    def test_missing_data_time_returns_none(self) -> None:
        assert to_measurement(_sample_api_item(dataTime="-")) is None

    def test_flag_aggregation(self) -> None:
        m = to_measurement(_sample_api_item(pm10Flag="장비점검"))
        assert m is not None
        assert m.flag is not None
        assert "장비점검" in m.flag

    def test_multiple_flags_joined(self) -> None:
        m = to_measurement(
            _sample_api_item(pm10Flag="장비점검", o3Flag="통신장애")
        )
        assert m is not None
        assert m.flag is not None
        assert "장비점검" in m.flag
        assert "통신장애" in m.flag

    def test_no_flag_is_none(self) -> None:
        m = to_measurement(_sample_api_item())
        assert m is not None
        assert m.flag is None


# ----------------------------------------------------------------------
# filter_target_stations
# ----------------------------------------------------------------------
class TestFilterTargetStations:
    def test_filters_to_targets_only(self) -> None:
        items = [
            {"stationName": "오창읍"},
            {"stationName": "복대동"},
            {"stationName": "충주시청"},
            {"stationName": "용암동"},
        ]
        result = filter_target_stations(items, ("오창읍", "용암동"))
        names = [r["stationName"] for r in result]
        assert names == ["오창읍", "용암동"]

    def test_empty_input(self) -> None:
        assert filter_target_stations([], ("오창읍",)) == []

    def test_no_match(self) -> None:
        items = [{"stationName": "XYZ"}]
        assert filter_target_stations(items, ("오창읍",)) == []

    def test_handles_whitespace_in_station_name(self) -> None:
        items = [{"stationName": " 오창읍 "}]
        result = filter_target_stations(items, ("오창읍",))
        assert len(result) == 1
