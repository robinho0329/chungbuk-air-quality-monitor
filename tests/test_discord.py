"""Discord 알림 모듈 단위 테스트.

네트워크 전송은 모킹. Embed 빌더의 Discord API 제약(1024자/필드) 준수에 집중.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from src.notifier.discord import (
    AlertField,
    DiscordAlert,
    _join_capped,
    build_spc_alert,
    send_alert,
)

_FIELD_MAX = 1024


# ---------------------------------------------------------------------------
# _join_capped
# ---------------------------------------------------------------------------

class TestJoinCapped:
    def test_short_list_unchanged(self) -> None:
        lines = ["a", "b", "c"]
        out = _join_capped(lines)
        assert out == "a\nb\nc"

    def test_caps_line_count_with_remainder(self) -> None:
        lines = [f"item{i}" for i in range(30)]
        out = _join_capped(lines, max_lines=12)
        assert "…외 18건" in out
        assert out.count("\n") == 12  # 12 라인 + 요약줄

    def test_respects_char_limit(self) -> None:
        # 각 라인이 매우 긴 경우 글자 수 제한이 우선
        lines = ["x" * 200 for _ in range(30)]
        out = _join_capped(lines, max_lines=12, max_chars=_FIELD_MAX)
        assert len(out) <= _FIELD_MAX

    def test_empty_list(self) -> None:
        assert _join_capped([]) == ""


# ---------------------------------------------------------------------------
# build_spc_alert
# ---------------------------------------------------------------------------

class TestBuildSpcAlert:
    def test_no_violations_green(self) -> None:
        alert = build_spc_alert([], [], total_checked=30)
        assert alert.color == 0x2ECC71
        assert "정상" in alert.title

    def test_cpk_only_red(self) -> None:
        cpk = [{"station": "복대동", "pollutant": "pm10", "cpk": 0.5, "threshold": 1.0}]
        alert = build_spc_alert(cpk, [], total_checked=30)
        assert alert.color == 0xE74C3C
        assert any("Cpk" in f.name for f in alert.fields)

    def test_we_only_yellow(self) -> None:
        we = [{"station": "복대동", "pollutant": "pm10", "rules": [1, 2]}]
        alert = build_spc_alert([], we, total_checked=30)
        assert alert.color == 0xF39C12

    def test_large_violation_set_within_field_limits(self) -> None:
        """실제 장애 케이스 재현: 20 Cpk + 30 WE → 모든 필드 1024자 이내."""
        cpk = [
            {"station": "복대동", "pollutant": "pm10", "cpk": 0.5, "threshold": 1.0}
        ] * 20
        we = [
            {"station": "복대동", "pollutant": "pm10", "rules": [1, 2, 3, 4, 5, 8]}
        ] * 30
        alert = build_spc_alert(cpk, we, total_checked=30)
        for f in alert.fields:
            assert len(f.value) <= _FIELD_MAX, f"필드 '{f.name}' 초과: {len(f.value)}"

    def test_cpk_sorted_worst_first(self) -> None:
        cpk = [
            {"station": "A", "pollutant": "pm10", "cpk": 0.9, "threshold": 1.0},
            {"station": "B", "pollutant": "pm25", "cpk": 0.2, "threshold": 1.0},
        ]
        alert = build_spc_alert(cpk, [], total_checked=2)
        cpk_field = next(f for f in alert.fields if "Cpk" in f.name)
        # 가장 낮은 Cpk(0.2, B/PM25)가 먼저 나와야 함
        assert cpk_field.value.index("0.200") < cpk_field.value.index("0.900")

    def test_total_count_in_title(self) -> None:
        cpk = [{"station": "복대동", "pollutant": "pm10", "cpk": 0.5, "threshold": 1.0}]
        we = [{"station": "복대동", "pollutant": "pm25", "rules": [1]}]
        alert = build_spc_alert(cpk, we, total_checked=30)
        assert "2건" in alert.title


# ---------------------------------------------------------------------------
# send_alert
# ---------------------------------------------------------------------------

class TestSendAlert:
    def test_no_url_returns_false(self) -> None:
        alert = DiscordAlert(title="t", description="d")
        with patch.dict("os.environ", {"DISCORD_WEBHOOK_URL": ""}, clear=False):
            assert send_alert(alert, webhook_url="") is False

    def test_successful_send(self) -> None:
        alert = DiscordAlert(title="t", description="d")
        with patch("src.notifier.discord.requests.post") as mock_post:
            mock_post.return_value.raise_for_status.return_value = None
            mock_post.return_value.status_code = 204
            assert send_alert(alert, webhook_url="https://discord.com/api/webhooks/x") is True
            mock_post.assert_called_once()

    def test_failed_send_returns_false(self) -> None:
        import requests
        alert = DiscordAlert(title="t", description="d")
        with patch("src.notifier.discord.requests.post") as mock_post:
            mock_post.side_effect = requests.RequestException("400")
            assert send_alert(alert, webhook_url="https://discord.com/api/webhooks/x") is False

    def test_payload_structure(self) -> None:
        alert = DiscordAlert(
            title="제목", description="본문",
            fields=[AlertField(name="f1", value="v1")],
        )
        payload = alert.to_payload()
        assert "embeds" in payload
        assert payload["embeds"][0]["title"] == "제목"
        assert payload["embeds"][0]["fields"][0]["name"] == "f1"
