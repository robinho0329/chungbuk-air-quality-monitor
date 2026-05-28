"""환경 변수 로드 및 검증 모듈.

.env 파일에서 환경 변수를 읽어 모듈 상수로 노출한다.
필수 변수가 누락되면 import 시점에 명시적 ValueError를 발생시킨다.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# 프로젝트 루트 경로
PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent

# .env 로드 (없어도 에러는 발생시키지 않음. 필수 변수 검증은 아래에서 수행)
load_dotenv(PROJECT_ROOT / ".env")


def _require(name: str) -> str:
    """필수 환경 변수를 읽고 누락 시 ValueError를 발생시킨다.

    Args:
        name: 환경 변수 이름.

    Returns:
        환경 변수 값 (문자열, 양끝 공백 제거).

    Raises:
        ValueError: 환경 변수가 설정되지 않았거나 빈 문자열일 때.
    """
    value = os.getenv(name, "").strip()
    if not value:
        raise ValueError(
            f"필수 환경 변수 '{name}'가 설정되어 있지 않습니다. "
            f".env 파일에 추가하거나 .env.example을 참고하세요."
        )
    return value


def _optional(name: str, default: str) -> str:
    """선택 환경 변수를 읽고 누락 시 기본값을 반환한다."""
    value = os.getenv(name, "").strip()
    return value if value else default


# ============================================================
# 에어코리아 OpenAPI
# ============================================================
# 키 검증은 사용 시점(collectors/airkorea.py)에 수행한다.
# 이렇게 해야 dashboard처럼 수집을 안 하는 컴포넌트도 키 없이 import 가능
# (Streamlit Cloud 배포 시 import-time ValueError 회피).
# Decoding 키 (URL 디코딩된 형태). requests params에 넘기면 자동 인코딩됨.
AIRKOREA_API_KEY: str = _optional("AIRKOREA_API_KEY", "")

# Encoding 키 (URL 인코딩된 형태). 일부 호출에서 백업용으로 사용.
AIRKOREA_API_KEY_ENCODED: str = _optional("AIRKOREA_API_KEY_ENCODED", "")

# ============================================================
# 데이터베이스
# ============================================================
DATABASE_URL: str = _optional(
    "DATABASE_URL",
    f"sqlite:///{(PROJECT_ROOT / 'src' / 'storage' / 'data.db').as_posix()}",
)

# ============================================================
# 로깅
# ============================================================
LOG_LEVEL: str = _optional("LOG_LEVEL", "INFO").upper()

# ============================================================
# Phase 3+ 환경 변수 (현재는 선택)
# ============================================================
WEATHER_API_KEY: str = _optional("WEATHER_API_KEY", "")
DISCORD_WEBHOOK_URL: str = _optional("DISCORD_WEBHOOK_URL", "")

# ============================================================
# 대상 측정소 (확정 정의)
# ============================================================
# Phase 1: 4개 측정소. 실제 stationName은 측정소정보 API로 검증 후 docs/stations.md에 기록.
TARGET_STATIONS: tuple[str, ...] = ("오창읍", "복대동", "오송읍", "용암동")

# 시도명 (에어코리아 시도별 실시간 측정정보 API의 sidoName 파라미터)
TARGET_SIDO: str = "충북"
