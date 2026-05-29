"""에어코리아 OpenAPI 클라이언트.

지원 엔드포인트:
1. 측정소정보 조회 (MsrstnInfoInqireSvc/getMsrstnList) - 시도별 측정소 목록과 좌표
2. 시도별 실시간 측정정보 (ArpltnInfoInqireSvc/getCtprvnRltmMesureDnsty)

설계 원칙:
- requests.Session 재사용으로 connection pooling
- 모든 호출에 timeout=30 명시
- resultCode != "00"이면 RuntimeError 발생
- 인증키는 로그에 노출하지 않음 (마스킹)
- 지수 백오프 재시도 (최대 3회)
- 응답 측정값의 "-" 또는 None은 NaN(파이썬 None)으로 처리
"""

from __future__ import annotations

import math
import re
import time
from datetime import datetime, timedelta
from typing import Any

import requests
from loguru import logger

# URL/메시지에 노출되는 serviceKey 값을 마스킹하기 위한 정규식
_SERVICE_KEY_PATTERN = re.compile(r"(serviceKey=)[^&\s]+", re.IGNORECASE)


def _scrub_key(text: str) -> str:
    """문자열 내 serviceKey 파라미터를 마스킹한다."""
    return _SERVICE_KEY_PATTERN.sub(r"\1***MASKED***", text)

from src.config import AIRKOREA_API_KEY
from src.storage.models import AirQualityMeasurement

# 에어코리아 OpenAPI Base URL
_BASE_URL = "https://apis.data.go.kr/B552584"
_ENDPOINT_STATION_INFO = f"{_BASE_URL}/MsrstnInfoInqireSvc/getMsrstnList"
# 주의: 시도별 실시간 측정정보 엔드포인트는 'ArpltnInforInqireSvc' (Info가 아니라 Infor).
# 2026-05-28 공공데이터활용지원센터 답변 확인.
_ENDPOINT_SIDO_REALTIME = f"{_BASE_URL}/ArpltnInforInqireSvc/getCtprvnRltmMesureDnsty"
# 측정소별 실시간 측정정보 조회 (기간 지원). dataTerm=DAILY면 최근 약 24시간 시간별 실측.
# 누락 시간대 백필(backfill)에 사용. 응답 item에는 stationName이 없어 호출 시 주입한다.
_ENDPOINT_STATION_PERIOD = (
    f"{_BASE_URL}/ArpltnInforInqireSvc/getMsrstnAcctoRltmMesureDnsty"
)

# 재시도 설정
_MAX_RETRIES = 3
_INITIAL_BACKOFF_SEC = 2.0

# 결측 표현
_MISSING_VALUES = {"-", "", None}


def _mask_key(key: str) -> str:
    """인증키를 로깅용으로 마스킹한다 (앞 4자, 뒤 4자만 노출)."""
    if len(key) <= 8:
        return "***"
    return f"{key[:4]}...{key[-4:]}"


def _parse_float(value: Any) -> float | None:
    """API 응답 값을 float로 변환. 결측("-", "", None)은 None 반환."""
    if value in _MISSING_VALUES:
        return None
    try:
        result = float(value)
        # NaN 차단
        if math.isnan(result):
            return None
        return result
    except (TypeError, ValueError):
        return None


def _parse_int(value: Any) -> int | None:
    """API 응답 값을 int로 변환. 결측이면 None 반환."""
    if value in _MISSING_VALUES:
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _parse_datetime(value: Any) -> datetime | None:
    """API 응답의 'YYYY-MM-DD HH:MM' 문자열을 datetime으로 변환.

    에어코리아는 자정을 'YYYY-MM-DD 24:00'으로 표기한다(해당 일의 끝).
    파이썬은 24시를 못 받으므로 '익일 00:00'으로 정규화한다.
    """
    if value in _MISSING_VALUES:
        return None
    text = str(value).strip()
    try:
        # '24:00' → 익일 00:00 정규화
        if " 24:00" in text:
            date_part = text.split(" ")[0]
            base = datetime.strptime(date_part, "%Y-%m-%d")
            return base + timedelta(days=1)
        return datetime.strptime(text, "%Y-%m-%d %H:%M")
    except (TypeError, ValueError) as exc:
        logger.warning(f"dataTime 파싱 실패: {value!r} ({exc})")
        return None


class AirkoreaClient:
    """에어코리아 OpenAPI 클라이언트.

    사용 예:
        client = AirkoreaClient()
        stations = client.get_stations(addr="충북")
        measurements = client.get_sido_realtime(sido_name="충북")
    """

    def __init__(self, service_key: str | None = None) -> None:
        """클라이언트 초기화.

        Args:
            service_key: 에어코리아 Decoding 키. None이면 config.AIRKOREA_API_KEY 사용.

        Raises:
            ValueError: 키가 없거나 빈 문자열일 때.
        """
        self._service_key = service_key or AIRKOREA_API_KEY
        if not self._service_key:
            raise ValueError(
                "AIRKOREA_API_KEY가 설정되지 않았습니다. "
                "로컬: .env 파일에 추가. GitHub Actions: Repository Secret 등록."
            )
        self._session = requests.Session()
        logger.debug(
            f"AirkoreaClient 초기화 (key={_mask_key(self._service_key)})"
        )

    def __enter__(self) -> "AirkoreaClient":
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()

    def close(self) -> None:
        """Session을 닫는다."""
        self._session.close()

    # ------------------------------------------------------------------
    # 내부: HTTP 호출 + 재시도
    # ------------------------------------------------------------------
    def _request_json(
        self, url: str, params: dict[str, Any]
    ) -> dict[str, Any]:
        """JSON 응답을 받는 GET 요청. 지수 백오프 재시도 포함.

        Raises:
            RuntimeError: 모든 재시도 실패 또는 resultCode != "00".
        """
        last_error: Exception | None = None
        backoff = _INITIAL_BACKOFF_SEC

        for attempt in range(1, _MAX_RETRIES + 1):
            try:
                logger.debug(
                    f"GET {url} (attempt {attempt}/{_MAX_RETRIES}, "
                    f"params={ {k: v for k, v in params.items() if k != 'serviceKey'} })"
                )
                response = self._session.get(url, params=params, timeout=30)
                response.raise_for_status()
                payload = response.json()

                # 에어코리아 표준 응답 구조 검증
                header = (
                    payload.get("response", {}).get("header", {})
                    if isinstance(payload, dict)
                    else {}
                )
                result_code = header.get("resultCode")
                result_msg = header.get("resultMsg", "")
                if result_code != "00":
                    raise RuntimeError(
                        f"에어코리아 API 오류: resultCode={result_code}, "
                        f"resultMsg={result_msg}"
                    )

                return payload

            except (requests.RequestException, RuntimeError, ValueError) as exc:
                last_error = exc
                scrubbed = _scrub_key(str(exc))
                logger.warning(
                    f"API 호출 실패 (attempt {attempt}/{_MAX_RETRIES}): {scrubbed}"
                )
                if attempt < _MAX_RETRIES:
                    time.sleep(backoff)
                    backoff *= 2.0

        # 모든 재시도 실패. 인증키 노출 방지를 위해 chained traceback은 끊는다.
        scrubbed_last = _scrub_key(str(last_error))
        raise RuntimeError(
            f"API 호출이 {_MAX_RETRIES}회 모두 실패했습니다: {scrubbed_last}"
        ) from None

    # ------------------------------------------------------------------
    # 1. 측정소정보 조회
    # ------------------------------------------------------------------
    def get_stations(
        self,
        addr: str | None = None,
        station_name: str | None = None,
        num_of_rows: int = 200,
    ) -> list[dict[str, Any]]:
        """측정소 목록을 조회한다.

        Args:
            addr: 시도명 (예: "충북"). None이면 전국 검색이지만 권장하지 않음.
            station_name: 특정 측정소명 (예: "오창읍"). 부분 일치 검색.
            num_of_rows: 한 페이지당 결과 수.

        Returns:
            측정소 정보 딕셔너리 리스트. 각 항목은 stationName, dmX, dmY, addr,
            year, mangName 등을 포함.
        """
        params: dict[str, Any] = {
            "serviceKey": self._service_key,
            "returnType": "json",
            "numOfRows": num_of_rows,
            "pageNo": 1,
        }
        if addr is not None:
            params["addr"] = addr
        if station_name is not None:
            params["stationName"] = station_name

        payload = self._request_json(_ENDPOINT_STATION_INFO, params)
        items = (
            payload.get("response", {})
            .get("body", {})
            .get("items", [])
        ) or []
        logger.info(
            f"측정소정보 조회: addr={addr}, stationName={station_name} "
            f"-> {len(items)}건"
        )
        return items

    # ------------------------------------------------------------------
    # 2. 시도별 실시간 측정정보
    # ------------------------------------------------------------------
    def get_sido_realtime(
        self,
        sido_name: str,
        num_of_rows: int = 200,
        ver: str = "1.3",
    ) -> list[dict[str, Any]]:
        """시도별 실시간 측정정보를 조회한다.

        Args:
            sido_name: 시도명 (예: "충북", "전국").
            num_of_rows: 한 페이지당 결과 수.
            ver: API 버전. "1.3"이면 PM2.5 포함.

        Returns:
            측정소별 실시간 측정 딕셔너리 리스트.
        """
        params: dict[str, Any] = {
            "serviceKey": self._service_key,
            "returnType": "json",
            "numOfRows": num_of_rows,
            "pageNo": 1,
            "sidoName": sido_name,
            "ver": ver,
        }
        payload = self._request_json(_ENDPOINT_SIDO_REALTIME, params)
        items = (
            payload.get("response", {})
            .get("body", {})
            .get("items", [])
        ) or []
        logger.info(
            f"시도별 실시간 측정정보 조회: sido={sido_name} -> {len(items)}건"
        )
        return items

    # ------------------------------------------------------------------
    # 3. 측정소별 기간 측정정보 (백필용)
    # ------------------------------------------------------------------
    def get_station_period(
        self,
        station_name: str,
        data_term: str = "DAILY",
        num_of_rows: int = 100,
        ver: str = "1.3",
    ) -> list[dict[str, Any]]:
        """특정 측정소의 기간별 시간 측정정보를 조회한다 (백필용).

        시도별 실시간 엔드포인트는 '현재 시각' 1건만 주지만, 이 엔드포인트는
        dataTerm 기간의 '시간별 시계열'을 반환하므로 누락된 과거 시간대를 메울 수 있다.

        Args:
            station_name: 측정소명 (예: "오창읍").
            data_term: 기간. "DAILY"(최근 약 24시간) / "MONTH" / "3MONTH".
            num_of_rows: 한 페이지당 결과 수.
            ver: API 버전. "1.3"이면 PM2.5 포함.

        Returns:
            시간별 측정 딕셔너리 리스트. 각 item에 stationName을 주입해 반환한다
            (원본 응답에는 측정소명이 없으므로 to_measurement 호환을 위해 추가).
        """
        params: dict[str, Any] = {
            "serviceKey": self._service_key,
            "returnType": "json",
            "numOfRows": num_of_rows,
            "pageNo": 1,
            "stationName": station_name,
            "dataTerm": data_term,
            "ver": ver,
        }
        payload = self._request_json(_ENDPOINT_STATION_PERIOD, params)
        items = (
            payload.get("response", {})
            .get("body", {})
            .get("items", [])
        ) or []
        # 응답 item에는 stationName이 없으므로 주입 (to_measurement 호환).
        for item in items:
            item["stationName"] = station_name
        logger.info(
            f"측정소별 기간 측정정보 조회: station={station_name}, "
            f"term={data_term} -> {len(items)}건"
        )
        return items


# ----------------------------------------------------------------------
# 변환 헬퍼: API 응답 dict -> AirQualityMeasurement
# ----------------------------------------------------------------------
def to_measurement(item: dict[str, Any]) -> AirQualityMeasurement | None:
    """에어코리아 시도별 실시간 응답 1건을 AirQualityMeasurement로 변환한다.

    station_name 또는 dataTime이 비어있으면 None을 반환한다 (저장 불가).
    """
    station_name = (item.get("stationName") or "").strip()
    data_time = _parse_datetime(item.get("dataTime"))
    if not station_name or data_time is None:
        logger.warning(
            f"필수 필드 누락으로 변환 스킵: stationName={station_name!r}, "
            f"dataTime={item.get('dataTime')!r}"
        )
        return None

    # Flag: 결측 사유. 측정값이 정상일 때는 보통 None.
    flag_candidates = [
        item.get(k)
        for k in (
            "pm10Flag",
            "pm25Flag",
            "o3Flag",
            "no2Flag",
            "so2Flag",
            "coFlag",
            "khaiFlag",
        )
    ]
    flag_set = {f for f in flag_candidates if f}
    flag_str = ", ".join(sorted(flag_set)) if flag_set else None

    return AirQualityMeasurement(
        station_name=station_name,
        data_time=data_time,
        pm10=_parse_float(item.get("pm10Value")),
        pm25=_parse_float(item.get("pm25Value")),
        o3=_parse_float(item.get("o3Value")),
        no2=_parse_float(item.get("no2Value")),
        so2=_parse_float(item.get("so2Value")),
        co=_parse_float(item.get("coValue")),
        khai=_parse_float(item.get("khaiValue")),
        pm10_grade=_parse_int(item.get("pm10Grade")),
        pm25_grade=_parse_int(item.get("pm25Grade")),
        o3_grade=_parse_int(item.get("o3Grade")),
        no2_grade=_parse_int(item.get("no2Grade")),
        so2_grade=_parse_int(item.get("so2Grade")),
        co_grade=_parse_int(item.get("coGrade")),
        khai_grade=_parse_int(item.get("khaiGrade")),
        flag=flag_str,
    )


def filter_target_stations(
    items: list[dict[str, Any]],
    target_names: tuple[str, ...],
) -> list[dict[str, Any]]:
    """응답 항목 중 target_names에 포함되는 측정소만 반환한다."""
    target_set = set(target_names)
    filtered = [
        item
        for item in items
        if (item.get("stationName") or "").strip() in target_set
    ]
    logger.info(
        f"필터링: 전체 {len(items)}건 -> 대상 {len(filtered)}건 "
        f"(targets={target_names})"
    )
    return filtered
