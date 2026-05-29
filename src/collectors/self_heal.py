"""Self-healing 수집 백필.

GitHub Actions 스케줄 cron은 best-effort라 시간당 수집을 자주 드롭한다.
이 모듈은 매 수집 실행 시 최근 N시간의 '빠진 시각'을 감지해 기간조회로 자동 복구한다.
→ cron이 며칠 드롭돼도 다음 한 번의 성공 실행이 누락분을 멱등하게 메운다(수렴 보장).

핵심:
- 기대 시각 격자(now-window ~ now, 시간단위) vs DB 실제 (측정소, 시각) 쌍 비교 → 갭 산출.
- 가장 오래된 갭이 24h 이내면 DAILY, 그보다 오래면 MONTH 기간조회 사용.
- INSERT OR IGNORE라 중복 삽입은 무해 → 반복 실행 안전.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from loguru import logger

from src.collectors.airkorea import AirkoreaClient, to_measurement
from src.config import TARGET_STATIONS
from src.storage.database import insert_measurements, query_pairs_since

KST = timezone(timedelta(hours=9))
# 갭이 이 시간보다 오래면 MONTH로 escalate(그 외 DAILY). DAILY 실제 커버(~24h)에
# 분 단위 여유를 둬 24h 윈도우가 경계에서 불필요하게 MONTH로 튀지 않게 함.
_DAILY_COVERAGE_HOURS = 30
# 수집기 기본 점검 윈도우(시간). 실측 cron 드롭은 수 시간 수준이라 24h면 충분하며,
# 이 범위는 DAILY 기간조회(저비용)로 모두 커버되어 매 실행 MONTH 호출 낭비를 막는다.
DEFAULT_WINDOW_HOURS = 24


def _now_kst_naive() -> datetime:
    """현재 KST를 tz-naive datetime으로 (DB의 data_time과 동일 기준)."""
    return datetime.now(tz=KST).replace(tzinfo=None)


def find_missing_hours(
    window_hours: int = DEFAULT_WINDOW_HOURS,
    stations: tuple[str, ...] = TARGET_STATIONS,
    *,
    now: datetime | None = None,
) -> dict[str, list[datetime]]:
    """최근 window_hours 구간에서 측정소별로 DB에 빠진 정시 시각을 찾는다.

    Args:
        window_hours: 점검할 과거 구간(시간). 기본 48.
        stations: 대상 측정소.
        now: 기준 현재시각(테스트용 주입). None이면 현재 KST.

    Returns:
        {측정소명: [빠진 datetime, ...]} (빈 리스트면 갭 없음).
    """
    if now is None:
        now = _now_kst_naive()
    # 기대 정시 격자: now의 정시부터 과거로 window_hours개.
    current_hour = now.replace(minute=0, second=0, microsecond=0)
    expected_hours = [
        current_hour - timedelta(hours=i) for i in range(window_hours + 1)
    ]
    since = expected_hours[-1]
    present = query_pairs_since(since)

    missing: dict[str, list[datetime]] = {}
    for st in stations:
        gaps = [h for h in expected_hours if (st, h) not in present]
        if gaps:
            missing[st] = sorted(gaps)
    return missing


@dataclass(frozen=True)
class HealResult:
    """self-heal 실행 결과.

    Attributes:
        missing_before: 복구 전 총 누락 시각·측정소 수.
        missing_after: 복구 후 남은 누락 수.
        inserted: 신규 삽입 건수.
        term_used: 사용한 기간조회 term (DAILY/MONTH) 또는 None(갭 없음).
    """

    missing_before: int
    missing_after: int
    inserted: int
    term_used: str | None

    @property
    def healed(self) -> int:
        """이번 실행으로 메운 시각 수."""
        return self.missing_before - self.missing_after


def self_heal(
    window_hours: int = DEFAULT_WINDOW_HOURS,
    stations: tuple[str, ...] = TARGET_STATIONS,
    *,
    client: AirkoreaClient | None = None,
    now: datetime | None = None,
) -> HealResult:
    """최근 window_hours의 누락 시각을 기간조회로 자동 복구한다.

    Args:
        window_hours: 점검 구간(시간). 기본 48.
        stations: 대상 측정소.
        client: 재사용할 AirkoreaClient(없으면 내부 생성).
        now: 기준 현재시각(테스트용).

    Returns:
        HealResult.
    """
    if now is None:
        now = _now_kst_naive()

    missing_before = find_missing_hours(window_hours, stations, now=now)
    n_before = sum(len(v) for v in missing_before.values())
    if n_before == 0:
        logger.info(f"self-heal: 최근 {window_hours}h 누락 없음 — 스킵")
        return HealResult(0, 0, 0, None)

    # 가장 오래된 갭이 DAILY 커버리지를 넘으면 MONTH로 escalate.
    oldest = min(min(v) for v in missing_before.values())
    age_hours = (now - oldest).total_seconds() / 3600
    term = "DAILY" if age_hours <= _DAILY_COVERAGE_HOURS else "MONTH"
    logger.info(
        f"self-heal: 누락 {n_before}건 (가장 오래된 갭 {age_hours:.0f}h 전) "
        f"→ {term} 기간조회로 복구 시도"
    )

    owns_client = client is None
    if client is None:
        client = AirkoreaClient()
    inserted_total = 0
    try:
        rows_req = 100 if term == "DAILY" else 9999
        # 누락이 있는 측정소만 조회 (불필요한 호출 절약)
        for st in missing_before:
            try:
                items = client.get_station_period(
                    st, data_term=term, num_of_rows=rows_req
                )
            except RuntimeError as exc:
                logger.warning(f"  {st}: 기간조회 실패 — 스킵 ({exc})")
                continue
            measurements = [
                m for m in (to_measurement(it) for it in items) if m is not None
            ]
            if measurements:
                _, inserted = insert_measurements(measurements)
                inserted_total += inserted
            time.sleep(0.5)  # API 매너
    finally:
        if owns_client:
            client.close()

    missing_after = find_missing_hours(window_hours, stations, now=now)
    n_after = sum(len(v) for v in missing_after.values())
    result = HealResult(n_before, n_after, inserted_total, term)
    logger.info(
        f"self-heal 완료: {result.healed}건 복구 / {n_after}건 잔여 "
        f"(신규 삽입 {inserted_total}건)"
    )
    return result
