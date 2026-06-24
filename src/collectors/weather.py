"""기상청 ASOS 시간자료 수집 클라이언트 (Phase 4).

공공데이터포털 '기상청 지상(종관, ASOS) 시간자료 조회서비스'를 호출해
청주(지점 131)의 시간별 기온·습도·풍속·풍향·강수를 수집한다.
대기질 측정값(data_time)과 시간 단위로 조인해 풍향 회귀·기상 보정 SPC에 쓴다.

설계 원칙(airkorea.py와 동일):
- 인증키 마스킹/스크럽으로 로그 노출 차단
- 지수 백오프 재시도 3회
- 결측("", "-", None)은 None으로
- WEATHER_API_KEY 미설정 시 ValueError(사용 시점)

API 키: 공공데이터포털에서 '기상청_지상(종관, ASOS) 시간자료' 활용신청 → Decoding 키를
WEATHER_API_KEY로 .env / GitHub Secret에 등록.
"""

from __future__ import annotations

import re
import time
from datetime import datetime
from typing import Any

import requests
from loguru import logger

from src.config import KMA_ASOS_STATION_ID, WEATHER_API_KEY
from src.storage.models import WeatherObservation

_ENDPOINT = "https://apis.data.go.kr/1360000/AsosHourlyInfoService/getWthrDataList"
_MAX_RETRIES = 3
_INITIAL_BACKOFF_SEC = 2.0
_MISSING = {"-", "", None, "null"}


def _mask_key(key: str) -> str:
    if not key:
        return "(빈 키)"
    return key[:4] + "…" + key[-4:] if len(key) > 8 else "****"


def _scrub_key(text: str) -> str:
    """로그/예외 문자열에서 serviceKey 값을 제거."""
    return re.sub(r"(serviceKey=)[^&\s]+", r"\1***", text)


def _pf(v: Any) -> float | None:
    """결측 안전 float 파싱."""
    if v in _MISSING:
        return None
    try:
        return float(str(v).strip())
    except (ValueError, TypeError):
        return None


def _parse_tm(v: Any) -> datetime | None:
    """ASOS 관측시각 'YYYY-MM-DD HH:MM' 파싱."""
    if v in _MISSING:
        return None
    s = str(v).strip()
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None


def to_observation(item: dict[str, Any], station_id: int) -> WeatherObservation | None:
    """ASOS 응답 item 1건을 WeatherObservation으로 변환. 시각 없으면 None.

    강수량(rn)은 무강수 시 빈 문자열로 오므로 None→0.0으로 보정한다.
    """
    obs_time = _parse_tm(item.get("tm"))
    if obs_time is None:
        return None
    rn = _pf(item.get("rn"))
    return WeatherObservation(
        station_id=station_id,
        obs_time=obs_time,
        ta=_pf(item.get("ta")),
        hm=_pf(item.get("hm")),
        ws=_pf(item.get("ws")),
        wd=_pf(item.get("wd")),
        rn=0.0 if rn is None else rn,
    )


class KmaAsosClient:
    """기상청 ASOS 시간자료 클라이언트.

    사용 예:
        with KmaAsosClient() as c:
            obs = c.get_hourly("20260601", "00", "20260601", "23")
    """

    def __init__(self, service_key: str | None = None) -> None:
        self._service_key = service_key or WEATHER_API_KEY
        if not self._service_key:
            raise ValueError(
                "WEATHER_API_KEY가 설정되지 않았습니다. 공공데이터포털 "
                "'기상청 지상(종관,ASOS) 시간자료' 활용신청 후 Decoding 키를 "
                ".env 또는 GitHub Secret에 등록하세요."
            )
        self._session = requests.Session()
        logger.debug(f"KmaAsosClient 초기화 (key={_mask_key(self._service_key)})")

    def __enter__(self) -> "KmaAsosClient":
        return self

    def __exit__(self, *_a: object) -> None:
        self.close()

    def close(self) -> None:
        self._session.close()

    def _request_json(self, params: dict[str, Any]) -> dict[str, Any]:
        last_error: Exception | None = None
        backoff = _INITIAL_BACKOFF_SEC
        for attempt in range(1, _MAX_RETRIES + 1):
            try:
                resp = self._session.get(_ENDPOINT, params=params, timeout=30)
                resp.raise_for_status()
                payload = resp.json()
                header = (
                    payload.get("response", {}).get("header", {})
                    if isinstance(payload, dict) else {}
                )
                code = header.get("resultCode")
                if code not in ("00", None):  # 일부 정상 응답은 header 생략
                    raise RuntimeError(
                        f"기상청 API 오류: resultCode={code}, "
                        f"resultMsg={header.get('resultMsg', '')}"
                    )
                return payload
            except (requests.RequestException, RuntimeError, ValueError) as exc:
                last_error = exc
                logger.warning(
                    f"기상청 API 실패 (attempt {attempt}/{_MAX_RETRIES}): "
                    f"{_scrub_key(str(exc))}"
                )
                if attempt < _MAX_RETRIES:
                    time.sleep(backoff)
                    backoff *= 2.0
        raise RuntimeError(
            f"기상청 API 호출이 {_MAX_RETRIES}회 모두 실패: {_scrub_key(str(last_error))}"
        ) from None

    def get_hourly(
        self,
        start_dt: str,
        start_hh: str,
        end_dt: str,
        end_hh: str,
        station_id: int = KMA_ASOS_STATION_ID,
        num_of_rows: int = 999,
    ) -> list[WeatherObservation]:
        """기간 시간자료를 조회해 WeatherObservation 리스트로 반환.

        Args:
            start_dt/end_dt: 'YYYYMMDD'.
            start_hh/end_hh: 'HH' (00~23).
            station_id: ASOS 지점번호 (기본 청주 131).
        """
        params = {
            "serviceKey": self._service_key,
            "dataType": "JSON",
            "dataCd": "ASOS",
            "dateCd": "HR",
            "startDt": start_dt,
            "startHh": start_hh,
            "endDt": end_dt,
            "endHh": end_hh,
            "stnIds": str(station_id),
            "numOfRows": num_of_rows,
            "pageNo": 1,
        }
        payload = self._request_json(params)
        items = (
            payload.get("response", {})
            .get("body", {})
            .get("items", {})
            .get("item", [])
        )
        if isinstance(items, dict):
            items = [items]
        out: list[WeatherObservation] = []
        for it in items:
            obs = to_observation(it, station_id)
            if obs is not None:
                out.append(obs)
        logger.info(f"기상청 ASOS {station_id}: {len(items)}건 응답 → {len(out)}건 변환")
        return out
