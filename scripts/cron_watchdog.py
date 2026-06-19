"""외부 cron(cron-job.org) 가동 감시 watchdog.

내장 schedule을 제거하면서 외부 cron이 유일한 수집 트리거가 됐다. 외부 cron이
멈추면 워크플로가 아예 안 돌아 알아채기 어렵다. 이 스크립트는 독립적인 watchdog
워크플로에서 주기적으로 실행돼, 마지막 수집(created_at 최댓값)이 임계 시간보다
오래됐으면 Discord로 경보를 보낸다.

설계 원칙:
- 어떤 경우에도 비정상 종료(exit≠0)하지 않는다 → 워크플로 실패 알림 메일 0.
- DISCORD_WEBHOOK_URL 미설정/전송 실패 시에도 조용히 넘어간다(로그만).
- 임계 미만이면 아무 것도 보내지 않는다(정상은 무음).

환경변수:
- DISCORD_WEBHOOK_URL: 경보 수신 webhook
- WATCHDOG_STALE_HOURS: 경보 임계(시간). 기본 3.
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

KST = timezone(timedelta(hours=9))


def main() -> None:
    try:
        from src.notifier.discord import DiscordAlert, send_alert
        from src.storage.database import query_all

        stale_hours = float(os.getenv("WATCHDOG_STALE_HOURS", "3"))
        rows = query_all()
        if not rows:
            print("watchdog: 데이터 없음 — 점검 스킵")
            return

        # created_at은 수집 러너(GitHub=UTC)의 datetime.now() = UTC naive로 기록된다.
        # now도 UTC naive로 맞춰 비교(tz 정보 제거).
        latest = max(r.created_at for r in rows)
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        age_h = (now - latest).total_seconds() / 3600.0
        latest_kst = (latest.replace(tzinfo=timezone.utc)).astimezone(KST)

        print(f"watchdog: 마지막 수집 {latest_kst:%Y-%m-%d %H:%M KST} ({age_h:.1f}h 전), 임계 {stale_hours}h")

        if age_h < stale_hours:
            print("watchdog: 정상 — 경보 없음")
            return

        alert = DiscordAlert(
            title="🛰️ 외부 cron 점검 필요 — 수집 지연 감지",
            description=(
                f"마지막 수집이 **{age_h:.1f}시간 전**입니다 "
                f"(임계 {stale_hours}h 초과).\n"
                f"cron-job.org 작업이 멈췄는지 확인하세요. "
                f"self-heal(72h)이 복구하지만 외부 cron 복구가 우선입니다."
            ),
            color=0xF39C12,
            footer="충북권 대기질 — cron watchdog",
        )
        sent = send_alert(alert)
        print(f"watchdog: 경보 전송 {'완료' if sent else '스킵(URL 미설정/실패)'}")
    except Exception as e:  # noqa: BLE001 — watchdog는 절대 실패하지 않는다
        print(f"watchdog: 예외 무시(워크플로 성공 유지) — {e}")


if __name__ == "__main__":
    main()
    sys.exit(0)  # 항상 성공 종료
