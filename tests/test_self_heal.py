"""Self-healing 백필 단위 테스트.

DB·API를 모킹해 갭 탐지/복구 로직만 순수 검증.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from src.collectors import self_heal as sh
from src.collectors.self_heal import HealResult, find_missing_hours, self_heal

NOW = datetime(2026, 5, 29, 19, 0, 0)  # 고정 기준시각 (tz-naive)
STATIONS = ("A", "B")


def _present(pairs: set[tuple[str, datetime]]):
    """query_pairs_since 모킹 팩토리."""
    return lambda since: {p for p in pairs if p[1] >= since}


# ----------------------------------------------------------------------
# find_missing_hours
# ----------------------------------------------------------------------
class TestFindMissingHours:
    def test_no_gap_when_all_present(self, monkeypatch) -> None:
        # 최근 3h 모든 측정소 완비
        window = 3
        hours = [NOW - timedelta(hours=i) for i in range(window + 1)]
        full = {(st, h) for st in STATIONS for h in hours}
        monkeypatch.setattr(sh, "query_pairs_since", _present(full))
        missing = find_missing_hours(window, STATIONS, now=NOW)
        assert missing == {}

    def test_detects_single_gap(self, monkeypatch) -> None:
        window = 3
        hours = [NOW - timedelta(hours=i) for i in range(window + 1)]
        full = {(st, h) for st in STATIONS for h in hours}
        # A의 18:00 한 건 제거
        gap_hour = NOW - timedelta(hours=1)
        full.discard(("A", gap_hour))
        monkeypatch.setattr(sh, "query_pairs_since", _present(full))
        missing = find_missing_hours(window, STATIONS, now=NOW)
        assert missing == {"A": [gap_hour]}

    def test_detects_all_missing(self, monkeypatch) -> None:
        monkeypatch.setattr(sh, "query_pairs_since", _present(set()))
        missing = find_missing_hours(2, STATIONS, now=NOW)
        # 각 측정소 3개 시각(현재+과거2) 전부 누락
        assert len(missing["A"]) == 3
        assert len(missing["B"]) == 3


# ----------------------------------------------------------------------
# HealResult
# ----------------------------------------------------------------------
class TestHealResult:
    def test_healed_property(self) -> None:
        r = HealResult(missing_before=10, missing_after=3, inserted=7, term_used="DAILY")
        assert r.healed == 7


# ----------------------------------------------------------------------
# self_heal (가짜 클라이언트)
# ----------------------------------------------------------------------
class _FakeClient:
    """get_station_period가 호출되면 호출 측정소·term을 기록."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def get_station_period(self, station_name, data_term="DAILY", num_of_rows=100):
        self.calls.append((station_name, data_term))
        return [{"stationName": station_name, "dataTime": "2026-05-29 18:00"}]


class TestSelfHeal:
    def test_noop_when_no_missing(self, monkeypatch) -> None:
        window = 2
        hours = [NOW - timedelta(hours=i) for i in range(window + 1)]
        full = {(st, h) for st in STATIONS for h in hours}
        monkeypatch.setattr(sh, "query_pairs_since", _present(full))
        res = self_heal(window, STATIONS, client=_FakeClient(), now=NOW)
        assert res.missing_before == 0
        assert res.term_used is None
        assert res.inserted == 0

    def test_recent_gap_uses_daily(self, monkeypatch) -> None:
        # 최근(1h 전) 갭만 있음 → DAILY term 선택
        window = 3
        hours = [NOW - timedelta(hours=i) for i in range(window + 1)]
        full = {(st, h) for st in STATIONS for h in hours}
        full.discard(("A", NOW - timedelta(hours=1)))
        monkeypatch.setattr(sh, "query_pairs_since", _present(full))
        monkeypatch.setattr(sh, "insert_measurements", lambda m: (len(m), len(m)))
        client = _FakeClient()
        res = self_heal(window, STATIONS, client=client, now=NOW)
        assert res.term_used == "DAILY"
        # 누락 있는 측정소(A)만 조회
        assert client.calls == [("A", "DAILY")]

    def test_old_gap_escalates_to_month(self, monkeypatch) -> None:
        # 40h 전 갭 → DAILY 커버리지(24h) 초과 → MONTH
        window = 48
        hours = [NOW - timedelta(hours=i) for i in range(window + 1)]
        full = {(st, h) for st in STATIONS for h in hours}
        full.discard(("B", NOW - timedelta(hours=40)))
        monkeypatch.setattr(sh, "query_pairs_since", _present(full))
        monkeypatch.setattr(sh, "insert_measurements", lambda m: (len(m), len(m)))
        client = _FakeClient()
        res = self_heal(window, STATIONS, client=client, now=NOW)
        assert res.term_used == "MONTH"
        assert client.calls == [("B", "MONTH")]
