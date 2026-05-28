"""공정능력 계산 단위 테스트.

합성 데이터 사용:
- 정규분포 N(μ=50, σ=5) 1000개로 안정적인 Cp/Cpk 검증
- 결측 제외 검증
- 최소 표본 검증
- USL/LSL 경계 케이스
- Cpk 음수 케이스 (절댓값 처리 안 함 확인)
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

from src.analysis.capability import (
    InsufficientSampleError,
    MIN_SAMPLE_SIZE,
    compute_capability,
)
from src.analysis.usl_lsl import SPEC_LIMITS, get_spec


# ----------------------------------------------------------------------
# usl_lsl 모듈
# ----------------------------------------------------------------------
class TestUslLslSpec:
    def test_all_6_pollutants_defined(self) -> None:
        assert set(SPEC_LIMITS.keys()) == {"pm10", "pm25", "o3", "no2", "so2", "co"}

    def test_pm10_daily_100(self) -> None:
        assert get_spec("pm10").usl_daily == 100.0

    def test_pm25_annual_15(self) -> None:
        assert get_spec("pm25").usl_annual == 15.0

    def test_all_lsl_zero(self) -> None:
        for spec in SPEC_LIMITS.values():
            assert spec.lsl == 0.0

    def test_unknown_pollutant_raises(self) -> None:
        with pytest.raises(KeyError):
            get_spec("ozone_xyz")

    def test_get_spec_case_insensitive(self) -> None:
        assert get_spec("PM10").usl_daily == 100.0

    def test_usl_for_unknown_basis_raises(self) -> None:
        with pytest.raises(ValueError):
            get_spec("pm10").usl_for("weekly")

    def test_usl_for_returns_none_when_undefined(self) -> None:
        # PM10은 hourly 기준이 없음
        assert get_spec("pm10").usl_for("hourly") is None


# ----------------------------------------------------------------------
# compute_capability: 정상 케이스
# ----------------------------------------------------------------------
class TestComputeCapabilityNormal:
    def _normal_data(self, mean: float, std: float, n: int, seed: int = 42) -> np.ndarray:
        rng = np.random.default_rng(seed)
        return rng.normal(loc=mean, scale=std, size=n)

    def test_centered_distribution_has_high_cpk(self) -> None:
        # μ=50, σ=5, USL=100, LSL=0 → Cp ≈ 100/(6*5) ≈ 3.33, Cpk ≈ 50/(3*5) ≈ 3.33
        data = self._normal_data(50, 5, 1000)
        result = compute_capability(data, usl=100, lsl=0)
        assert result.n == 1000
        assert math.isclose(result.mean, 50, abs_tol=1.0)
        assert math.isclose(result.std, 5, abs_tol=0.5)
        assert result.cp > 3.0  # 충분히 높음
        assert result.cpk > 3.0
        assert math.isclose(result.cp, result.cpk, abs_tol=0.5)  # 중심 분포

    def test_offset_distribution_lowers_cpk(self) -> None:
        # μ를 USL 가깝게 → cpu 작아짐 → cpk 작아짐
        data = self._normal_data(80, 5, 1000)  # USL=100
        result = compute_capability(data, usl=100, lsl=0)
        # cpu = (100-80)/15 ≈ 1.33, cpl = 80/15 ≈ 5.33 → cpk ≈ 1.33
        assert result.cpu < result.cpl
        assert result.cpk == result.cpu
        assert math.isclose(result.cpk, 1.33, abs_tol=0.2)

    def test_cpk_can_be_negative(self) -> None:
        # μ가 USL을 초과 → cpu 음수 → cpk 음수. 절댓값 처리 금지 확인.
        data = self._normal_data(120, 5, 1000)  # USL=100
        result = compute_capability(data, usl=100, lsl=0)
        assert result.cpu < 0
        assert result.cpk < 0
        assert result.interpret_cpk().startswith("공정 중심이 규격을 벗어남")


# ----------------------------------------------------------------------
# compute_capability: 경계·예외 케이스
# ----------------------------------------------------------------------
class TestComputeCapabilityEdgeCases:
    def test_min_sample_size_constant(self) -> None:
        assert MIN_SAMPLE_SIZE == 30

    def test_insufficient_sample_raises(self) -> None:
        data = [50.0] * 29  # 29개 - 1개 미달
        with pytest.raises(InsufficientSampleError):
            compute_capability(data, usl=100, lsl=0)

    def test_exactly_minimum_sample_passes_sample_check_but_fails_on_zero_std(self) -> None:
        # 30개 모두 동일값 → 표본 검사는 통과하지만 std=0으로 ValueError
        data = [50.0] * 30
        with pytest.raises(ValueError, match="표준편차가 0"):
            compute_capability(data, usl=100, lsl=0)

    def test_nan_values_excluded_from_count(self) -> None:
        # 25 정상 + 10 NaN → 25개로 카운트 → 미달
        rng = np.random.default_rng(42)
        good = rng.normal(50, 5, 25)
        bad = [float("nan")] * 10
        data = np.concatenate([good, bad])
        with pytest.raises(InsufficientSampleError):
            compute_capability(data, usl=100, lsl=0)

    def test_usl_below_lsl_raises(self) -> None:
        with pytest.raises(ValueError, match="USL"):
            compute_capability([50] * 100, usl=10, lsl=100)

    def test_accepts_pandas_series(self) -> None:
        rng = np.random.default_rng(42)
        s = pd.Series(rng.normal(50, 5, 100))
        result = compute_capability(s, usl=100)
        assert result.n == 100


# ----------------------------------------------------------------------
# CapabilityResult.interpret_cpk
# ----------------------------------------------------------------------
class TestCpkInterpretation:
    def _result_with_cpk(self, cpk: float):
        from src.analysis.capability import CapabilityResult
        return CapabilityResult(
            n=100, mean=50, std=5, usl=100, lsl=0,
            cp=cpk, cpk=cpk, cpu=cpk, cpl=cpk,
        )

    def test_negative(self) -> None:
        assert "벗어남" in self._result_with_cpk(-0.1).interpret_cpk()

    def test_low(self) -> None:
        assert "불량" in self._result_with_cpk(0.8).interpret_cpk()

    def test_marginal(self) -> None:
        assert "마진" in self._result_with_cpk(1.2).interpret_cpk()

    def test_good(self) -> None:
        assert "양호" in self._result_with_cpk(1.5).interpret_cpk()

    def test_excellent(self) -> None:
        assert "우수" in self._result_with_cpk(2.0).interpret_cpk()
