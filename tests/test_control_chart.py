"""SPC 관리도 단위 테스트.

합성 데이터로 검증:
- 안정 공정(in-control): 이탈 0건이 기대됨
- 평균 이동(shift): EWMA/CUSUM이 빠르게 탐지
- 단발 이상치: I-chart가 탐지
- σ 추정·경계·예외 케이스
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

from src.analysis.control_chart import (
    ControlChartResult,
    InsufficientSampleError,
    cusum_chart,
    estimate_sigma_mr,
    ewma_chart,
    i_chart,
)


def _stable(mean: float, std: float, n: int, seed: int = 42) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return rng.normal(loc=mean, scale=std, size=n)


# ----------------------------------------------------------------------
# σ 추정 (이동범위)
# ----------------------------------------------------------------------
class TestEstimateSigmaMR:
    def test_recovers_true_sigma_approximately(self) -> None:
        data = _stable(50, 5, 2000)
        sig = estimate_sigma_mr(data)
        # MR 기반 추정이 참 σ(5)에 근접
        assert math.isclose(sig, 5, abs_tol=0.5)

    def test_constant_series_raises(self) -> None:
        with pytest.raises(ValueError, match="σ 추정"):
            estimate_sigma_mr(np.full(50, 7.0))


# ----------------------------------------------------------------------
# I-Chart
# ----------------------------------------------------------------------
class TestIChart:
    def test_stable_process_no_or_few_violations(self) -> None:
        data = _stable(50, 5, 500)
        res = i_chart(data)
        assert res.chart_type == "I"
        assert res.n == 500
        # 3σ 관리한계 → 안정 공정 이탈률은 매우 낮음(<1%)
        assert len(res.violations) <= 5

    def test_single_outlier_detected(self) -> None:
        data = _stable(50, 5, 200).copy()
        data[100] = 200.0  # 명백한 특수원인
        res = i_chart(data)
        assert 100 in res.violations

    def test_control_limits_symmetric_around_center(self) -> None:
        data = _stable(50, 5, 300)
        res = i_chart(data)
        assert math.isclose(res.ucl[0] - res.center, res.center - res.lcl[0], rel_tol=1e-9)
        assert math.isclose(res.ucl[0], res.center + 3 * res.sigma, rel_tol=1e-9)

    def test_explicit_sigma_and_target(self) -> None:
        data = _stable(50, 5, 100)
        res = i_chart(data, sigma=5.0, target=50.0)
        assert res.sigma == 5.0
        assert res.center == 50.0
        assert math.isclose(res.ucl[0], 65.0, rel_tol=1e-9)

    def test_insufficient_sample_raises(self) -> None:
        with pytest.raises(InsufficientSampleError):
            i_chart([50.0])  # 1개 < 2

    def test_nan_excluded(self) -> None:
        data = [50.0, float("nan"), 52.0, 48.0, 51.0]
        res = i_chart(data)
        assert res.n == 4


# ----------------------------------------------------------------------
# EWMA
# ----------------------------------------------------------------------
class TestEwmaChart:
    def test_stable_process_in_control(self) -> None:
        data = _stable(50, 5, 500)
        res = ewma_chart(data, lam=0.2, L=3.0)
        assert res.chart_type == "EWMA"
        assert len(res.violations) <= 5

    def test_detects_small_sustained_shift(self) -> None:
        # 전반부 안정 + 후반부 +1.5σ 이동 → EWMA가 탐지.
        # SPC 실무: 중심/σ는 안정(Phase I) 기준으로 고정한 뒤 모니터링한다.
        rng = np.random.default_rng(7)
        first = rng.normal(50, 5, 150)
        second = rng.normal(50 + 1.5 * 5, 5, 150)
        data = np.concatenate([first, second])
        res = ewma_chart(data, lam=0.2, L=3.0, sigma=5.0, target=50.0)
        assert len(res.violations) > 0
        # 이동 이후 구간에서 첫 이탈이 발생
        assert min(res.violations) >= 150

    def test_control_limits_widen_then_stabilize(self) -> None:
        data = _stable(50, 5, 300)
        res = ewma_chart(data, lam=0.2, L=3.0)
        width = res.ucl - res.center
        # 초기 폭 < 후기 폭 (점근적으로 증가·수렴)
        assert width[0] < width[-1]
        assert width[-1] <= 3.0 * res.sigma * math.sqrt(0.2 / 1.8) + 1e-9

    def test_invalid_lambda_raises(self) -> None:
        with pytest.raises(ValueError, match="λ"):
            ewma_chart(_stable(50, 5, 100), lam=1.5)


# ----------------------------------------------------------------------
# CUSUM
# ----------------------------------------------------------------------
class TestCusumChart:
    def test_stable_process_in_control(self) -> None:
        # k=0.5, h=5의 in-control ARL은 약 465 → 500점에서 거짓경보 몇 건은 정상.
        # 핵심은 거짓경보 '비율'이 낮다는 점(< 2%).
        data = _stable(50, 5, 500)
        res = cusum_chart(data, k=0.5, h=5.0)
        assert res.chart_type == "CUSUM"
        assert len(res.violations) / res.n < 0.02

    def test_detects_sustained_shift(self) -> None:
        rng = np.random.default_rng(11)
        first = rng.normal(50, 5, 100)
        second = rng.normal(50 + 1.0 * 5, 5, 100)  # +1σ 이동
        data = np.concatenate([first, second])
        # target/sigma를 안정 구간 기준으로 고정해야 이동을 누적 탐지
        res = cusum_chart(data, k=0.5, h=5.0, sigma=5.0, target=50.0)
        assert len(res.violations) > 0
        assert min(res.violations) >= 100

    def test_extra_contains_pos_neg(self) -> None:
        data = _stable(50, 5, 100)
        res = cusum_chart(data)
        assert "cusum_pos" in res.extra
        assert "cusum_neg" in res.extra
        assert res.extra["cusum_pos"].shape == (100,)
        # max_c는 두 누적합의 원소별 최댓값
        assert np.all(
            res.values == np.maximum(res.extra["cusum_pos"], res.extra["cusum_neg"])
        )

    def test_lcl_is_zero_and_ucl_is_h_sigma(self) -> None:
        data = _stable(50, 5, 100)
        res = cusum_chart(data, k=0.5, h=5.0, sigma=5.0)
        assert np.all(res.lcl == 0)
        assert math.isclose(res.ucl[0], 5.0 * 5.0, rel_tol=1e-9)

    def test_invalid_h_raises(self) -> None:
        with pytest.raises(ValueError, match="h는 양수"):
            cusum_chart(_stable(50, 5, 100), h=0)


# ----------------------------------------------------------------------
# ControlChartResult
# ----------------------------------------------------------------------
class TestControlChartResult:
    def test_is_in_control_property(self) -> None:
        res = ControlChartResult(
            chart_type="I", n=10, values=np.zeros(10), center=0.0,
            ucl=np.ones(10), lcl=-np.ones(10), sigma=1.0, target=0.0,
            violations=[],
        )
        assert res.is_in_control is True
        res2 = ControlChartResult(
            chart_type="I", n=10, values=np.zeros(10), center=0.0,
            ucl=np.ones(10), lcl=-np.ones(10), sigma=1.0, target=0.0,
            violations=[3],
        )
        assert res2.is_in_control is False

    def test_accepts_pandas_series(self) -> None:
        s = pd.Series(_stable(50, 5, 100))
        res = i_chart(s)
        assert res.n == 100
