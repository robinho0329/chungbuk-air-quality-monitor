"""자기상관 보정 잔차 관리도 테스트.

합성 AR(1)+일주기 데이터로 검증:
- 강한 자기상관 → 원시 I-chart는 거짓경보 과다, 잔차 I-chart는 명목수준
- 잔차의 lag-1 ACF가 백색화(≈0)
- AR(1) 계수 회복, 일주기 제거
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from src.analysis.control_chart import InsufficientSampleError
from src.analysis.residual_chart import (
    ResidualChartResult,
    deseasonalize_hourly,
    fit_ar1,
    lag1_acf,
    residual_i_chart,
)


def _ar1(phi: float, n: int, sigma: float = 1.0, seed: int = 42) -> np.ndarray:
    rng = np.random.default_rng(seed)
    e = rng.normal(0, sigma, n)
    x = np.zeros(n)
    for t in range(1, n):
        x[t] = phi * x[t - 1] + e[t]
    return x


# ----------------------------------------------------------------------
# lag1_acf
# ----------------------------------------------------------------------
class TestLag1Acf:
    def test_white_noise_near_zero(self) -> None:
        x = np.random.default_rng(0).normal(0, 1, 2000)
        assert abs(lag1_acf(x)) < 0.1

    def test_ar1_high(self) -> None:
        x = _ar1(0.9, 2000)
        assert lag1_acf(x) > 0.8

    def test_too_short(self) -> None:
        assert lag1_acf(np.array([1.0])) == 0.0


# ----------------------------------------------------------------------
# deseasonalize / fit_ar1
# ----------------------------------------------------------------------
class TestDeseasonalize:
    def test_removes_hourly_pattern(self) -> None:
        hours = np.tile(np.arange(24), 50)
        # 시간대별 큰 오프셋 + 작은 노이즈
        base = hours * 2.0
        vals = base + np.random.default_rng(1).normal(0, 0.5, len(hours))
        deseason, means = deseasonalize_hourly(vals, hours)
        # 제거 후 평균≈0, 시간대 구조 사라짐
        assert abs(deseason.mean()) < 0.1
        assert means[10] > means[0]  # 시간대 평균이 단조 증가 반영


class TestFitAr1:
    def test_recovers_phi(self) -> None:
        x = _ar1(0.8, 5000)
        phi, resid = fit_ar1(x)
        assert math.isclose(phi, 0.8, abs_tol=0.05)
        # 잔차는 백색에 근접
        assert abs(lag1_acf(resid)) < 0.1

    def test_too_short_raises(self) -> None:
        with pytest.raises(InsufficientSampleError):
            fit_ar1(np.array([1.0]))


# ----------------------------------------------------------------------
# residual_i_chart (핵심)
# ----------------------------------------------------------------------
class TestResidualIChart:
    def test_residual_reduces_false_alarms(self) -> None:
        # 강한 자기상관(phi=0.9) 안정 공정 → 원시는 과다 경보, 잔차는 명목수준.
        x = _ar1(0.9, 1500, sigma=1.0, seed=7) + 50.0
        res = residual_i_chart(x, deseasonalize=False)
        assert isinstance(res, ResidualChartResult)
        # 백색화: 잔차 ACF가 원시보다 크게 감소
        assert res.acf_after < res.acf_before
        assert abs(res.acf_after) < 0.15
        # 거짓경보율: 잔차 < 원시
        assert res.resid_violation_rate < res.raw_violation_rate

    def test_deseasonalize_path(self) -> None:
        # 일주기 + AR(1) 결합 데이터
        n = 1500
        hours = np.tile(np.arange(24), n // 24 + 1)[:n]
        diurnal = 10 * np.sin(2 * np.pi * hours / 24)
        x = _ar1(0.85, n, sigma=1.0, seed=3) + diurnal + 30.0
        res = residual_i_chart(x, hours=hours, deseasonalize=True)
        assert abs(res.acf_after) < 0.2
        assert res.resid_violation_rate <= res.raw_violation_rate

    def test_requires_hours_when_deseasonalize(self) -> None:
        x = _ar1(0.5, 100)
        with pytest.raises(ValueError, match="hours"):
            residual_i_chart(x, deseasonalize=True)

    def test_insufficient_sample(self) -> None:
        with pytest.raises(InsufficientSampleError):
            residual_i_chart(_ar1(0.5, 10), deseasonalize=False)
