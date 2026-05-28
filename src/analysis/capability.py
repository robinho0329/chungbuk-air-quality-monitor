"""공정능력지수(Cp, Cpk, Pp, Ppk) 계산 모듈.

설계 원칙:
1. 최소 표본 30개 미만이면 InsufficientSampleError 발생 (계산 거부)
2. 표준편차는 표본표준편차 (ddof=1, NumPy/pandas 기본)
3. Cpk 음수는 그대로 반환 (절댓값 처리 금지)
4. 결측(NaN)은 자동 제외 후 카운트 검증

용어:
- Cp: 단기 공정능력 (분포 폭 vs 규격 폭). 위치 무관.
- Cpk: 단기 공정능력 (위치까지 고려). 한쪽 치우침에 민감.
- Pp/Ppk: 장기 공정성능. 같은 공식이지만 보통 더 긴 기간의 σ를 사용.
  이 구현에서는 입력 데이터 그대로 사용 (단기/장기 구분 책임은 호출자).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

MIN_SAMPLE_SIZE: int = 30


class InsufficientSampleError(ValueError):
    """표본이 최소 요건 미만일 때 발생."""


@dataclass(frozen=True)
class CapabilityResult:
    """공정능력 계산 결과.

    Attributes:
        n: 결측 제외 후 표본 크기.
        mean: 표본 평균.
        std: 표본표준편차 (ddof=1).
        usl: 사용된 USL.
        lsl: 사용된 LSL.
        cp: (USL - LSL) / (6σ). 양쪽 규격이 있을 때만 의미.
        cpk: min((USL-μ)/(3σ), (μ-LSL)/(3σ)). 위치 고려.
        cpu: (USL - μ) / (3σ). 상한 한 방향 능력.
        cpl: (μ - LSL) / (3σ). 하한 한 방향 능력.
    """

    n: int
    mean: float
    std: float
    usl: float
    lsl: float
    cp: float
    cpk: float
    cpu: float
    cpl: float

    def interpret_cpk(self) -> str:
        """Cpk 통상 해석 (한국어). 6시그마/SPC 표준 임계."""
        if self.cpk < 0:
            return "공정 중심이 규격을 벗어남 (즉시 조치)"
        if self.cpk < 1.0:
            return "불량 위험 (개선 필요)"
        if self.cpk < 1.33:
            return "마진 부족 (관리 강화)"
        if self.cpk < 1.67:
            return "양호"
        return "우수 (6시그마 수준)"


def compute_capability(
    values: pd.Series | np.ndarray | list[float],
    usl: float,
    lsl: float = 0.0,
    min_n: int = MIN_SAMPLE_SIZE,
) -> CapabilityResult:
    """공정능력지수를 계산한다.

    Args:
        values: 측정값 시퀀스. NaN은 자동 제외.
        usl: 상한 규격. 양수 필수.
        lsl: 하한 규격. 기본 0.
        min_n: 최소 표본 크기 (기본 30).

    Returns:
        CapabilityResult 인스턴스.

    Raises:
        InsufficientSampleError: 결측 제외 후 표본 < min_n.
        ValueError: USL <= LSL이거나 표준편차가 0(또는 NaN).
    """
    if usl <= lsl:
        raise ValueError(
            f"USL({usl})은 LSL({lsl})보다 커야 합니다."
        )

    # numpy array로 통일하고 NaN 제거
    arr = pd.Series(values, dtype="float64").dropna().to_numpy()
    n = int(arr.size)

    if n < min_n:
        raise InsufficientSampleError(
            f"표본 크기 {n}이(가) 최소 요건 {min_n} 미만입니다. "
            f"Cp/Cpk 계산을 거부합니다."
        )

    mean = float(arr.mean())
    # ddof=1: 표본표준편차
    std = float(arr.std(ddof=1))

    if std == 0 or np.isnan(std):
        raise ValueError(
            f"표준편차가 0 또는 NaN입니다 (std={std}). "
            "측정값이 모두 동일하거나 비정상 데이터입니다."
        )

    cp = (usl - lsl) / (6 * std)
    cpu = (usl - mean) / (3 * std)
    cpl = (mean - lsl) / (3 * std)
    cpk = min(cpu, cpl)

    return CapabilityResult(
        n=n,
        mean=mean,
        std=std,
        usl=usl,
        lsl=lsl,
        cp=cp,
        cpk=cpk,
        cpu=cpu,
        cpl=cpl,
    )
