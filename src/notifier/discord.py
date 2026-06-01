"""Discord Webhook 알림 모듈.

SPC 이상 탐지(Cpk 임계 미달 / WE Rules 위반) 결과를 Discord 채널에 전송한다.

설계 원칙:
- DISCORD_WEBHOOK_URL 미설정 시 no-op (예외 발생 없이 경고 로그만 남김)
- 단순 requests.post 사용 — Prefect/외부 의존성 불필요
- Embed 메시지 형식: 색상·타이틀·필드로 가독성 확보
- 재시도 없음 (GHA step이 실패해도 수집 워크플로우 전체는 성공으로 처리)
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any

import requests
from loguru import logger

# Discord Embed 색상
_COLOR_RED = 0xE74C3C     # 이상 (위험)
_COLOR_YELLOW = 0xF39C12  # 경고 (주의)
_COLOR_GREEN = 0x2ECC71   # 정상


@dataclass
class AlertField:
    """Discord Embed 필드 하나."""
    name: str
    value: str
    inline: bool = True


@dataclass
class DiscordAlert:
    """Discord Embed 메시지 구성.

    Attributes:
        title: Embed 제목.
        description: Embed 본문 (마크다운 가능).
        color: 좌측 바 색상 (0xRRGGBB 정수).
        fields: 필드 목록.
        footer: 하단 주석 텍스트.
    """
    title: str
    description: str
    color: int = _COLOR_RED
    fields: list[AlertField] = field(default_factory=list)
    footer: str = "충북권 대기질 SPC 모니터링"

    def to_payload(self) -> dict[str, Any]:
        """Discord Webhook API payload dict로 변환."""
        embed: dict[str, Any] = {
            "title": self.title,
            "description": self.description,
            "color": self.color,
            "fields": [
                {"name": f.name, "value": f.value, "inline": f.inline}
                for f in self.fields
            ],
            "footer": {"text": self.footer},
        }
        return {"embeds": [embed]}


def send_alert(
    alert: DiscordAlert,
    webhook_url: str | None = None,
) -> bool:
    """Discord Webhook으로 알림을 전송한다.

    Args:
        alert: 전송할 DiscordAlert 인스턴스.
        webhook_url: Webhook URL. None이면 환경변수 DISCORD_WEBHOOK_URL 사용.

    Returns:
        성공 여부(True/False). URL 미설정 시 False.
    """
    url = webhook_url or os.getenv("DISCORD_WEBHOOK_URL", "").strip()
    if not url:
        logger.warning(
            "DISCORD_WEBHOOK_URL이 설정되지 않아 Discord 알림을 건너뜁니다. "
            ".env에 추가하거나 GitHub Secret을 확인하세요."
        )
        return False

    payload = alert.to_payload()
    try:
        resp = requests.post(url, json=payload, timeout=10)
        resp.raise_for_status()
        logger.info(f"Discord 알림 전송 성공 (status={resp.status_code}): {alert.title}")
        return True
    except requests.RequestException as e:
        logger.error(f"Discord 알림 전송 실패: {e}")
        return False


# ---------------------------------------------------------------------------
# 고수준 알림 빌더
# ---------------------------------------------------------------------------

def build_spc_alert(
    cpk_violations: list[dict],
    we_violations: list[dict],
    total_checked: int,
) -> DiscordAlert:
    """SPC 이상 탐지 결과로 DiscordAlert를 생성한다.

    Args:
        cpk_violations: Cpk 임계 미달 항목 리스트.
            각 항목: {'station': str, 'pollutant': str, 'cpk': float, 'threshold': float}
        we_violations: WE Rules 위반 항목 리스트.
            각 항목: {'station': str, 'pollutant': str, 'rules': list[int]}
        total_checked: 전체 점검 측정소×지표 조합 수.

    Returns:
        DiscordAlert 인스턴스.
    """
    has_alert = bool(cpk_violations or we_violations)

    if not has_alert:
        return DiscordAlert(
            title="✅ 대기질 SPC 정상",
            description=(
                f"전체 {total_checked}개 측정소×지표 조합에서 "
                "이상 패턴이 탐지되지 않았습니다."
            ),
            color=_COLOR_GREEN,
        )

    # 알림 있음
    fields: list[AlertField] = []

    if cpk_violations:
        cpk_lines = []
        for v in cpk_violations:
            cpk_lines.append(
                f"**{v['station']}** · {v['pollutant'].upper()}  "
                f"Cpk={v['cpk']:.3f} < {v['threshold']:.2f}"
            )
        fields.append(AlertField(
            name=f"📐 Cpk 임계 미달 ({len(cpk_violations)}건)",
            value="\n".join(cpk_lines),
            inline=False,
        ))

    if we_violations:
        we_lines = []
        for v in we_violations:
            rules_str = ", ".join(f"Rule {r}" for r in sorted(v["rules"]))
            we_lines.append(
                f"**{v['station']}** · {v['pollutant'].upper()}  [{rules_str}]"
            )
        fields.append(AlertField(
            name=f"📋 WE Rules 위반 ({len(we_violations)}건)",
            value="\n".join(we_lines),
            inline=False,
        ))

    n_alerts = len(cpk_violations) + len(we_violations)
    color = _COLOR_RED if cpk_violations else _COLOR_YELLOW

    return DiscordAlert(
        title=f"🚨 대기질 SPC 이상 탐지 ({n_alerts}건)",
        description=(
            f"충북 측정소 {total_checked}개 조합 점검 중 "
            f"**{n_alerts}건** 이상 패턴 발견."
        ),
        color=color,
        fields=fields,
    )
