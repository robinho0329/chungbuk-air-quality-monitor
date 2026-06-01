"""IsolationForest 기반 다변량 이상 탐지 모듈.

단변량 관리도(I-Chart/EWMA/CUSUM/WE Rules)는 지표를 하나씩 독립 처리하지만,
실제 대기질 이상은 여러 오염물질이 동시에 비정상 패턴을 보이는 경우가 많다.
IsolationForest는 측정소별 다변량 시계열(PM10, PM2.5, O3, NO2, SO2, CO)에서
고립되기 쉬운(= 이상한) 샘플을 비지도 학습으로 탐지한다.

설계 원칙:
- 결측(NaN)은 행 단위 제거 (모든 지표가 있는 시각만 사용)
- sklearn IsolationForest 래핑: contamination은 호출자가 지정 (기본 'auto')
- 최소 표본: 학습에 필요한 10건 (기본값)
- 외부 결과: AnomalyResult(이상 인덱스, 점수 배열, 사용 피처 목록)
- 피처 스케일링 없음 (IsolationForest는 거리 무관 → 스케일 불변)
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

# sklearn은 optional dependency로 가져옴 (Streamlit Cloud도 설치됨)
try:
    from sklearn.ensemble import IsolationForest as _IsolationForest
except ImportError as _e:  # pragma: no cover
    raise ImportError(
        "scikit-learn이 필요합니다. `uv add scikit-learn` 또는 "
        "`pip install scikit-learn`으로 설치하세요."
    ) from _e

# 이상 탐지에 사용할 기본 피처(오염물질) 목록
DEFAULT_FEATURES: list[str] = ["pm10", "pm25", "o3", "no2", "so2", "co"]

MIN_SAMPLE_SIZE: int = 10


class InsufficientSampleError(ValueError):
    """표본이 최소 요건 미만일 때 발생."""


@dataclass(frozen=True)
class AnomalyResult:
    """IsolationForest 이상 탐지 결과.

    Attributes:
        n: 결측 제외(완전 케이스) 후 표본 크기.
        features: 탐지에 사용된 피처(오염물질) 이름 리스트.
        anomaly_indices: 이상으로 판정된 0-based 인덱스 리스트.
            (입력 DataFrame의 NaN 제거 후 재인덱싱 기준)
        scores: 이상 점수 배열(낮을수록 이상 — sklearn 반환값 그대로).
            음수가 이상(anomaly), 양수가 정상(inlier).
        contamination: 사용된 contamination 파라미터 값.
        n_anomalies: 탐지된 이상치 수.
    """

    n: int
    features: list[str]
    anomaly_indices: list[int]
    scores: np.ndarray
    contamination: float | str
    n_anomalies: int = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "n_anomalies", len(self.anomaly_indices))

    @property
    def anomaly_rate(self) -> float:
        """이상치 비율 (0~1)."""
        return self.n_anomalies / self.n if self.n > 0 else 0.0

    def summary(self) -> str:
        """이상 탐지 결과 요약 (한국어)."""
        if self.n_anomalies == 0:
            return f"이상치 없음 — {self.n}개 시각 중 다변량 이상 패턴 미탐지."
        return (
            f"{self.n}개 시각 중 **{self.n_anomalies}건({self.anomaly_rate * 100:.1f}%)** "
            f"이상치 탐지 (contamination={self.contamination}, "
            f"피처: {', '.join(self.features)})."
        )


def detect_anomalies(
    df: pd.DataFrame,
    features: list[str] | None = None,
    contamination: float | str = "auto",
    n_estimators: int = 100,
    random_state: int = 42,
    min_n: int = MIN_SAMPLE_SIZE,
) -> AnomalyResult:
    """IsolationForest로 다변량 이상치를 탐지한다.

    Args:
        df: 측정 데이터 DataFrame. 최소한 features 컬럼을 포함해야 한다.
        features: 탐지에 사용할 컬럼 이름 리스트.
            None이면 DEFAULT_FEATURES 중 df에 존재하는 것만 사용.
        contamination: IsolationForest contamination 파라미터.
            'auto' 또는 0~0.5 float. 기본 'auto'.
        n_estimators: 트리 수. 기본 100.
        random_state: 재현성 시드. 기본 42.
        min_n: 결측 제외 후 최소 표본 크기.

    Returns:
        AnomalyResult 인스턴스.

    Raises:
        InsufficientSampleError: 완전 케이스(non-NaN) 표본 < min_n.
        ValueError: 사용 가능한 피처가 없거나 contamination 범위 위반.
    """
    # 피처 결정
    if features is None:
        use_features = [f for f in DEFAULT_FEATURES if f in df.columns]
    else:
        use_features = [f for f in features if f in df.columns]

    if not use_features:
        raise ValueError(
            f"사용 가능한 피처가 없습니다. "
            f"요청: {features or DEFAULT_FEATURES}, "
            f"df 컬럼: {list(df.columns)}"
        )

    # 완전 케이스만 추출
    sub = df[use_features].dropna()
    n = len(sub)
    if n < min_n:
        raise InsufficientSampleError(
            f"완전 케이스 표본 {n}이(가) 최소 요건 {min_n} 미만입니다."
        )

    X = sub.to_numpy(dtype=float)

    # IsolationForest 학습 + 예측
    iso = _IsolationForest(
        n_estimators=n_estimators,
        contamination=contamination,
        random_state=random_state,
    )
    preds = iso.fit_predict(X)   # 1=정상, -1=이상
    scores = iso.score_samples(X)  # 낮을수록 이상

    anomaly_indices = [int(i) for i in range(n) if preds[i] == -1]

    return AnomalyResult(
        n=n,
        features=use_features,
        anomaly_indices=anomaly_indices,
        scores=scores,
        contamination=contamination,
    )


def detect_anomalies_by_station(
    df: pd.DataFrame,
    station_col: str = "station_name",
    features: list[str] | None = None,
    contamination: float | str = "auto",
    n_estimators: int = 100,
    random_state: int = 42,
    min_n: int = MIN_SAMPLE_SIZE,
) -> dict[str, AnomalyResult]:
    """측정소별로 IsolationForest 이상 탐지를 수행한다.

    Args:
        df: 전체 측정 데이터. station_col 컬럼으로 측정소 구분.
        station_col: 측정소 이름 컬럼. 기본 'station_name'.
        features: 탐지 피처. None이면 DEFAULT_FEATURES.
        contamination: IsolationForest contamination.
        n_estimators: 트리 수.
        random_state: 시드.
        min_n: 측정소별 최소 표본.

    Returns:
        {station_name: AnomalyResult} 딕셔너리.
        표본 부족 측정소는 포함되지 않음.
    """
    results: dict[str, AnomalyResult] = {}
    if station_col not in df.columns:
        raise ValueError(f"station_col='{station_col}'이 df에 없습니다.")

    for station in df[station_col].unique():
        sub_df = df[df[station_col] == station].reset_index(drop=True)
        try:
            results[str(station)] = detect_anomalies(
                sub_df,
                features=features,
                contamination=contamination,
                n_estimators=n_estimators,
                random_state=random_state,
                min_n=min_n,
            )
        except InsufficientSampleError:
            pass  # 표본 부족 측정소는 건너뜀

    return results
