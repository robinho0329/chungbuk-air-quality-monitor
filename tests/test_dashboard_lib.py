"""대시보드 공통 헬퍼(_lib) 회귀 테스트.

핵심: next_cron_eta_kst()가 모든 분(0~59)에서 ValueError 없이 동작해야 한다.
(과거 버그: :55 슬롯 + 5분 버퍼 = minute 60 → datetime.replace(minute=60) ValueError로
 사이드바를 쓰는 전 페이지가 다운됨.)
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

import dashboard._lib as lib

KST = timezone(timedelta(hours=9))


def _freeze(monkeypatch, h: int, m: int) -> None:
    """now_kst를 고정 시각으로 패치."""
    fixed = datetime(2026, 5, 29, h, m, tzinfo=KST)
    monkeypatch.setattr(lib, "now_kst", lambda: fixed)


class TestNextCronEtaKst:
    @pytest.mark.parametrize("m", range(60))
    def test_never_raises_any_minute(self, monkeypatch, m: int) -> None:
        # 분(分) 전수(0~59) — 버그가 분 경계에서 났으므로 분 차원만 전수면 충분.
        _freeze(monkeypatch, 21, m)
        out = lib.next_cron_eta_kst()
        assert out.endswith("KST")
        hh, mm = out.replace(" KST", "").split(":")
        assert 0 <= int(hh) <= 23
        assert 0 <= int(mm) <= 59

    def test_eta_is_in_future(self, monkeypatch) -> None:
        # 반환 시각은 항상 현재 이후(같은 날 또는 익시각)
        _freeze(monkeypatch, 21, 5)
        assert lib.next_cron_eta_kst() == "21:20 KST"  # :15 슬롯 +5분

    def test_slot_55_rolls_to_next_hour(self, monkeypatch) -> None:
        # 회귀 핵심: :40~:59 구간은 :55 슬롯(+5분=60분)이 다음 시각 :00으로 굴러가야 함
        _freeze(monkeypatch, 21, 40)
        assert lib.next_cron_eta_kst() == "22:00 KST"

    def test_after_last_slot_wraps_next_hour(self, monkeypatch) -> None:
        # :55 지난 시각이면 다음 시각 첫 슬롯(:15)+5분
        _freeze(monkeypatch, 21, 59)
        assert lib.next_cron_eta_kst() == "22:20 KST"

    def test_midnight_boundary(self, monkeypatch) -> None:
        # 23:59 → 익일 00:20 (시각 롤오버, 예외 없이)
        _freeze(monkeypatch, 23, 59)
        assert lib.next_cron_eta_kst() == "00:20 KST"
