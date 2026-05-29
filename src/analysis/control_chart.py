"""SPC 관리도(Control Chart) 계산 모듈.

시간당 개별 측정값(n=1 서브그룹)에 적합한 3종 관리도를 제공한다.

1. I-Chart (개별값 관리도, Individuals/X chart)
   - 중심선 = 평균, 관리한계 = 평균 ± 3σ
   - σ는 이동범위(Moving Range) 기반 추정: σ̂ = MR̄ / d2 (n=2 → d2=1.128)
   - 단발성 이상치(특수원인) 탐지에 강함

2. EWMA-Chart (지수가중이동평균)
   - z_t = λ·x_t + (1-λ)·z_{t-1}, z_0 = target
   - 작은 평균 이동(small shift)에 민감. λ=0.2, L=3 통상값
   - 관리한계는 초기에 좁았다가 점근적으로 ±L·σ·√(λ/(2-λ))로 수렴

3. CUSUM-Chart (누적합, 표 형식 tabular CUSUM)
   - C⁺_t = max(0, x_t - (target + k) + C⁺_{t-1})
   - C⁻_t = max(0, (target - k) - x_t + C⁻_{t-1})
   - |C| > H 이면 이탈. 기준이동(slack) k=0.5σ, 결정구간 H=5σ 통상값
   - 지속적인 작은 평균 이동을 누적해 빠르게 탐지

설계 원칙(capability.py와 일관):
- 결측(NaN)은 자동 제외
- σ는 데이터에서 추정하되 외부 주입(sigma 인자) 허용
- 최소 표본 미만이면 InsufficientSampleError
- 절댓값/클리핑 등 임의 가공 없음
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

# I-chart 이동범위(n=2) 상수: MR̄/d2 로 σ 추정
_D2_N2: float = 1.128

# 관리도 계산에 필요한 최소 표본(작아도 동작은 하나 통계적 의미는 30+ 권장)
MIN_SAMPLE_SIZE: int = 2


class InsufficientSampleError(ValueError):
    """표본이 관리도 계산 최소 요건 미만일 때 발생."""


def _clean(values: pd.Series | np.ndarray | list[float]) -> np.ndarray:
    """입력을 float64 numpy 배열로 변환하고 NaN을 제거한다.

    Args:
        values: 측정값 시퀀스.

    Returns:
        결측이 제거된 1차원 float64 배열.
    """
    return pd.Series(values, dtype="float64").dropna().to_numpy()


def estimate_sigma_mr(arr: np.ndarray) -> float:
    """이동범위(Moving Range) 기반 표준편차 추정.

    σ̂ = MR̄ / d2,  MR_i = |x_i - x_{i-1}|,  d2(n=2) = 1.128

    개별값 관리도(I-chart)의 표준 σ 추정 방식이다. 표본표준편차(ddof=1)와
    달리 인접 관측치 변동만 사용하므로 추세/이동이 있어도 단기 산포를 안정적으로 본다.

    Args:
        arr: 결측이 제거된 측정값 배열 (길이 ≥ 2).

    Returns:
        추정 표준편차(>0).

    Raises:
        ValueError: 추정 σ가 0 또는 NaN (모든 인접값이 동일 등).
    """
    mr = np.abs(np.diff(arr))
    sigma = float(mr.mean()) / _D2_N2
    if sigma == 0 or np.isnan(sigma):
        raise ValueError(
            f"이동범위 기반 σ 추정이 0 또는 NaN입니다 (σ={sigma}). "
            "측정값이 모두 동일하거나 비정상 데이터입니다."
        )
    return sigma


@dataclass(frozen=True)
class ControlChartResult:
    """관리도 계산 결과 (공통 컨테이너).

    Attributes:
        chart_type: 'I', 'EWMA', 'CUSUM' 중 하나.
        n: 결측 제외 후 표본 크기.
        values: 플롯 대상 통계량 시퀀스.
            - I: 원본 측정값
            - EWMA: EWMA 통계량 z_t
            - CUSUM: 각 시점의 max(C⁺, C⁻) (관리한계와 직접 비교 가능한 양의 값)
        center: 중심선 값(스칼라).
        ucl: 상한 관리한계 시퀀스(시점별; EWMA는 가변).
        lcl: 하한 관리한계 시퀀스. CUSUM은 단측(0)이라 0 배열.
        sigma: 사용된 σ 추정값.
        target: 사용된 목표/중심값(평균).
        violations: 관리한계 이탈 시점의 인덱스 리스트(0-based).
        extra: 차트별 부가 데이터(예: CUSUM의 cusum_pos/cusum_neg).
    """

    chart_type: str
    n: int
    values: np.ndarray
    center: float
    ucl: np.ndarray
    lcl: np.ndarray
    sigma: float
    target: float
    violations: list[int]
    extra: dict[str, np.ndarray] = field(default_factory=dict)

    @property
    def is_in_control(self) -> bool:
        """이탈 시점이 하나도 없으면 True (관리 상태)."""
        return len(self.violations) == 0


def i_chart(
    values: pd.Series | np.ndarray | list[float],
    sigma: float | None = None,
    target: float | None = None,
    min_n: int = MIN_SAMPLE_SIZE,
) -> ControlChartResult:
    """개별값 관리도(I-Chart)를 계산한다.

    Args:
        values: 측정값 시퀀스. NaN 자동 제외.
        sigma: σ를 직접 지정. None이면 이동범위 기반 추정.
        target: 중심선. None이면 표본 평균.
        min_n: 최소 표본 크기.

    Returns:
        ControlChartResult (chart_type='I').

    Raises:
        InsufficientSampleError: 표본 < min_n.
        ValueError: σ가 0/NaN 또는 부적절.
    """
    arr = _clean(values)
    n = int(arr.size)
    if n < min_n:
        raise InsufficientSampleError(
            f"표본 크기 {n}이(가) 최소 요건 {min_n} 미만입니다."
        )

    center = float(arr.mean()) if target is None else float(target)
    sig = estimate_sigma_mr(arr) if sigma is None else float(sigma)
    if sig <= 0 or np.isnan(sig):
        raise ValueError(f"σ는 양수여야 합니다 (받은 값: {sig}).")

    ucl_val = center + 3 * sig
    lcl_val = center - 3 * sig
    ucl = np.full(n, ucl_val)
    lcl = np.full(n, lcl_val)

    violations = [
        i for i in range(n) if arr[i] > ucl_val or arr[i] < lcl_val
    ]

    return ControlChartResult(
        chart_type="I",
        n=n,
        values=arr,
        center=center,
        ucl=ucl,
        lcl=lcl,
        sigma=sig,
        target=center,
        violations=violations,
    )


def ewma_chart(
    values: pd.Series | np.ndarray | list[float],
    lam: float = 0.2,
    L: float = 3.0,
    sigma: float | None = None,
    target: float | None = None,
    min_n: int = MIN_SAMPLE_SIZE,
) -> ControlChartResult:
    """EWMA 관리도를 계산한다.

    z_t = λ·x_t + (1-λ)·z_{t-1},  z_0 = target
    관리한계 = target ± L·σ·√( (λ/(2-λ))·(1-(1-λ)^{2t}) )

    Args:
        values: 측정값 시퀀스. NaN 자동 제외.
        lam: 가중치 λ (0<λ≤1). 작을수록 과거를 더 반영(작은 이동에 민감). 기본 0.2.
        L: 관리한계 폭 계수(σ 배수). 기본 3.0.
        sigma: σ 직접 지정. None이면 이동범위 기반 추정.
        target: 중심값. None이면 표본 평균.
        min_n: 최소 표본 크기.

    Returns:
        ControlChartResult (chart_type='EWMA'). values는 z_t 시퀀스.

    Raises:
        InsufficientSampleError: 표본 < min_n.
        ValueError: λ 범위 위반 또는 σ 부적절.
    """
    if not (0.0 < lam <= 1.0):
        raise ValueError(f"λ는 (0, 1] 범위여야 합니다 (받은 값: {lam}).")

    arr = _clean(values)
    n = int(arr.size)
    if n < min_n:
        raise InsufficientSampleError(
            f"표본 크기 {n}이(가) 최소 요건 {min_n} 미만입니다."
        )

    center = float(arr.mean()) if target is None else float(target)
    sig = estimate_sigma_mr(arr) if sigma is None else float(sigma)
    if sig <= 0 or np.isnan(sig):
        raise ValueError(f"σ는 양수여야 합니다 (받은 값: {sig}).")

    # EWMA 통계량
    z = np.empty(n)
    prev = center
    for t in range(n):
        prev = lam * arr[t] + (1 - lam) * prev
        z[t] = prev

    # 시점별 가변 관리한계
    t_idx = np.arange(1, n + 1)
    var_factor = (lam / (2 - lam)) * (1 - (1 - lam) ** (2 * t_idx))
    half_width = L * sig * np.sqrt(var_factor)
    ucl = center + half_width
    lcl = center - half_width

    violations = [i for i in range(n) if z[i] > ucl[i] or z[i] < lcl[i]]

    return ControlChartResult(
        chart_type="EWMA",
        n=n,
        values=z,
        center=center,
        ucl=ucl,
        lcl=lcl,
        sigma=sig,
        target=center,
        violations=violations,
    )


def cusum_chart(
    values: pd.Series | np.ndarray | list[float],
    k: float = 0.5,
    h: float = 5.0,
    sigma: float | None = None,
    target: float | None = None,
    min_n: int = MIN_SAMPLE_SIZE,
) -> ControlChartResult:
    """표 형식(tabular) CUSUM 관리도를 계산한다.

    표준화 없이 원 단위로 계산하되, slack k와 결정구간 h는 σ 배수로 받는다.
        K = k·σ (기준 이동 허용량),  H = h·σ (결정구간)
        C⁺_t = max(0, x_t - (target + K) + C⁺_{t-1})
        C⁻_t = max(0, (target - K) - x_t + C⁻_{t-1})
    |C⁺| 또는 |C⁻| 가 H를 초과하면 이탈.

    Args:
        values: 측정값 시퀀스. NaN 자동 제외.
        k: 기준 이동 허용량(σ 배수). 통상 0.5(=탐지하려는 이동의 절반). 기본 0.5.
        h: 결정구간(σ 배수). 통상 4~5. 기본 5.0.
        sigma: σ 직접 지정. None이면 이동범위 기반 추정.
        target: 목표값. None이면 표본 평균.
        min_n: 최소 표본 크기.

    Returns:
        ControlChartResult (chart_type='CUSUM').
        values는 시점별 max(C⁺, C⁻), ucl은 H 상수배열, lcl은 0 배열.
        extra={'cusum_pos': C⁺, 'cusum_neg': C⁻}.

    Raises:
        InsufficientSampleError: 표본 < min_n.
        ValueError: k/h 음수 또는 σ 부적절.
    """
    if k < 0 or h <= 0:
        raise ValueError(f"k는 0 이상, h는 양수여야 합니다 (k={k}, h={h}).")

    arr = _clean(values)
    n = int(arr.size)
    if n < min_n:
        raise InsufficientSampleError(
            f"표본 크기 {n}이(가) 최소 요건 {min_n} 미만입니다."
        )

    center = float(arr.mean()) if target is None else float(target)
    sig = estimate_sigma_mr(arr) if sigma is None else float(sigma)
    if sig <= 0 or np.isnan(sig):
        raise ValueError(f"σ는 양수여야 합니다 (받은 값: {sig}).")

    big_k = k * sig
    big_h = h * sig

    c_pos = np.zeros(n)
    c_neg = np.zeros(n)
    prev_pos = 0.0
    prev_neg = 0.0
    for t in range(n):
        prev_pos = max(0.0, arr[t] - (center + big_k) + prev_pos)
        prev_neg = max(0.0, (center - big_k) - arr[t] + prev_neg)
        c_pos[t] = prev_pos
        c_neg[t] = prev_neg

    max_c = np.maximum(c_pos, c_neg)
    ucl = np.full(n, big_h)
    lcl = np.zeros(n)
    violations = [i for i in range(n) if max_c[i] > big_h]

    return ControlChartResult(
        chart_type="CUSUM",
        n=n,
        values=max_c,
        center=0.0,  # CUSUM 플롯의 기준선은 0
        ucl=ucl,
        lcl=lcl,
        sigma=sig,
        target=center,
        violations=violations,
        extra={"cusum_pos": c_pos, "cusum_neg": c_neg},
    )
