"""자기상관 보정 잔차 관리도 (Residual / ARIMA-style SPC).

문제: 전통 SPC 관리도는 관측치가 독립(i.i.d.)이라 가정한다. 그러나 대기질·연속공정
데이터는 강한 시계열 자기상관(예: PM2.5 lag-1 ACF≈0.93)을 가져, MR(이동범위) 기반
σ 추정이 분산을 과소평가 → 관리한계가 좁아져 **거짓경보가 폭증**한다.

해법(SPC 표준): 시계열 구조를 모델로 제거한 **잔차**에 관리도를 적용한다.
  1) 일주기(hour-of-day) 계절성 제거 — 시간대 평균 차감
  2) 남은 계열에 AR(1) 적합 → 잔차 e_t (백색잡음에 근접)
  3) e_t에 I-Chart 적용 → 거짓경보율이 명목수준(≈0.27%)에 수렴

자체 구현(numpy)으로 무거운 의존성 없이 처리. 원시 계열 직접 관리도와의
거짓경보율 Before/After 비교를 제공한다.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from src.analysis.control_chart import (
    ControlChartResult,
    InsufficientSampleError,
    i_chart,
)

MIN_SAMPLE_SIZE: int = 30


def lag1_acf(x: np.ndarray) -> float:
    """lag-1 자기상관계수. 표본<2 또는 분산 0이면 0.0."""
    x = np.asarray(x, dtype="float64")
    if x.size < 2:
        return 0.0
    a, b = x[:-1], x[1:]
    denom = a.std() * b.std()
    if denom == 0:
        return 0.0
    return float(np.corrcoef(a, b)[0, 1])


def deseasonalize_hourly(
    values: np.ndarray, hours: np.ndarray
) -> tuple[np.ndarray, dict[int, float]]:
    """시간대(0~23) 평균을 차감해 일주기 계절성을 제거한다.

    Returns:
        (계절성 제거된 계열, {시각: 평균} 맵).
    """
    values = np.asarray(values, dtype="float64")
    hours = np.asarray(hours)
    hour_means: dict[int, float] = {}
    for h in np.unique(hours):
        hour_means[int(h)] = float(values[hours == h].mean())
    deseason = values - np.array([hour_means[int(h)] for h in hours])
    return deseason, hour_means


def fit_ar1(x: np.ndarray) -> tuple[float, np.ndarray]:
    """평균 0 가정 계열에 AR(1) 적합. (phi, 잔차) 반환.

    phi = Σ x_t·x_{t-1} / Σ x_{t-1}²,  잔차 e_t = x_t - phi·x_{t-1} (t=1..n-1).
    """
    x = np.asarray(x, dtype="float64")
    if x.size < 2:
        raise InsufficientSampleError("AR(1) 적합에는 최소 2개 관측치 필요.")
    prev, curr = x[:-1], x[1:]
    denom = float((prev**2).sum())
    phi = float((prev * curr).sum() / denom) if denom > 0 else 0.0
    resid = curr - phi * prev
    return phi, resid


@dataclass(frozen=True)
class ResidualChartResult:
    """잔차 관리도 결과 + 원시 대비 진단.

    Attributes:
        phi: 추정된 AR(1) 계수.
        acf_before: 원시(계절성 제거 후) 계열의 lag-1 ACF.
        acf_after: 잔차의 lag-1 ACF (≈0이면 백색화 성공).
        raw_chart: 원시 계열 직접 I-Chart 결과.
        resid_chart: 잔차 I-Chart 결과.
        n: 잔차 표본 수.
    """

    phi: float
    acf_before: float
    acf_after: float
    raw_chart: ControlChartResult
    resid_chart: ControlChartResult
    n: int

    @property
    def raw_violation_rate(self) -> float:
        """원시 관리도 이탈률(거짓경보 프록시)."""
        return len(self.raw_chart.violations) / self.raw_chart.n

    @property
    def resid_violation_rate(self) -> float:
        """잔차 관리도 이탈률."""
        return len(self.resid_chart.violations) / self.resid_chart.n

    def interpret(self) -> str:
        """한 줄 해석."""
        return (
            f"lag-1 ACF {self.acf_before:.2f}→{self.acf_after:.2f} (백색화), "
            f"이탈률 {self.raw_violation_rate * 100:.1f}%→"
            f"{self.resid_violation_rate * 100:.1f}% "
            f"(거짓경보 {'감소' if self.resid_violation_rate < self.raw_violation_rate else '변화없음'})."
        )


def residual_i_chart(
    values: pd.Series | np.ndarray | list[float],
    hours: pd.Series | np.ndarray | list[int] | None = None,
    *,
    deseasonalize: bool = True,
    min_n: int = MIN_SAMPLE_SIZE,
) -> ResidualChartResult:
    """자기상관 보정 잔차 I-Chart를 계산하고 원시 관리도와 비교한다.

    Args:
        values: 측정값 시계열 (시간 오름차순 가정). NaN은 제외.
        hours: 각 관측치의 시각(0~23). deseasonalize=True면 필수.
        deseasonalize: 일주기(시간대) 계절성 제거 여부.
        min_n: 최소 표본.

    Returns:
        ResidualChartResult.

    Raises:
        InsufficientSampleError: 표본 < min_n.
        ValueError: deseasonalize=True인데 hours 미제공, 또는 분산 0.
    """
    s = pd.Series(values, dtype="float64")
    mask = s.notna().to_numpy()
    arr = s.to_numpy()[mask]
    if arr.size < min_n:
        raise InsufficientSampleError(
            f"표본 {arr.size} < 최소 {min_n}. 잔차 관리도 계산 거부."
        )

    # 원시 계열 직접 I-Chart (비교 기준)
    raw_chart = i_chart(arr, min_n=min_n)

    # 1) 일주기 계절성 제거
    if deseasonalize:
        if hours is None:
            raise ValueError("deseasonalize=True면 hours가 필요합니다.")
        hrs = np.asarray(pd.Series(hours))[mask]
        deseason, _ = deseasonalize_hourly(arr, hrs)
    else:
        deseason = arr - arr.mean()

    acf_before = lag1_acf(deseason)

    # 2) AR(1) 적합 → 잔차
    phi, resid = fit_ar1(deseason)
    acf_after = lag1_acf(resid)

    # 3) 잔차에 I-Chart (목표=0: 잔차는 평균 0 백색잡음)
    resid_chart = i_chart(resid, target=0.0, min_n=min_n)

    return ResidualChartResult(
        phi=phi,
        acf_before=acf_before,
        acf_after=acf_after,
        raw_chart=raw_chart,
        resid_chart=resid_chart,
        n=int(resid.size),
    )
