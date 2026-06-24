"""기상청 ASOS 수집기 순수 함수 테스트. API 호출 없이 변환·파싱·마스킹만 검증."""

from __future__ import annotations

from datetime import datetime

from src.collectors.weather import (
    _mask_key,
    _parse_tm,
    _pf,
    _scrub_key,
    to_observation,
)


class TestParse:
    def test_pf_numeric(self) -> None:
        assert _pf("12.3") == 12.3
        assert _pf("-1.5") == -1.5

    def test_pf_missing(self) -> None:
        for v in ("-", "", None, "null"):
            assert _pf(v) is None

    def test_tm_parse(self) -> None:
        assert _parse_tm("2026-06-01 13:00") == datetime(2026, 6, 1, 13, 0)

    def test_tm_missing(self) -> None:
        assert _parse_tm("") is None
        assert _parse_tm("bad") is None


class TestToObservation:
    def test_full_item(self) -> None:
        item = {"tm": "2026-06-01 09:00", "ta": "21.3", "hm": "55", "ws": "2.4", "wd": "270", "rn": "0.0"}
        obs = to_observation(item, station_id=131)
        assert obs is not None
        assert obs.station_id == 131
        assert obs.obs_time == datetime(2026, 6, 1, 9, 0)
        assert obs.ta == 21.3 and obs.hm == 55.0 and obs.ws == 2.4 and obs.wd == 270.0
        assert obs.rn == 0.0

    def test_missing_rn_becomes_zero(self) -> None:
        # 무강수 시 rn 빈 문자열 → 0.0 보정
        obs = to_observation({"tm": "2026-06-01 09:00", "rn": ""}, station_id=131)
        assert obs is not None and obs.rn == 0.0

    def test_no_time_returns_none(self) -> None:
        assert to_observation({"ta": "20"}, station_id=131) is None

    def test_partial_missing(self) -> None:
        obs = to_observation({"tm": "2026-06-01 09:00", "ta": "-", "wd": "180"}, station_id=131)
        assert obs is not None and obs.ta is None and obs.wd == 180.0


class TestSecurity:
    def test_mask_key(self) -> None:
        assert "…" in _mask_key("ABCD1234EFGH5678")
        assert _mask_key("") == "(빈 키)"

    def test_scrub_key(self) -> None:
        assert "SECRET" not in _scrub_key("https://x?serviceKey=SECRET&a=1")
        assert "***" in _scrub_key("serviceKey=SECRET")
