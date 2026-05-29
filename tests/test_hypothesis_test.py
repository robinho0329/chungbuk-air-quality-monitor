"""가설검정 모듈 단위 테스트.

합성 데이터로 검증:
- 평균이 명확히 다른 두 그룹 → 유의 + 큰 효과크기
- 같은 분포의 두 그룹 → 비유의
- 표본 부족 → InsufficientSampleError
- ANOVA: 한 그룹만 다를 때 유의
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.analysis.hypothesis_test import (
    AnovaResult,
    InsufficientSampleError,
    TTestResult,
    anova_across_stations,
    cohens_d,
    industrial_vs_baseline,
    one_way_anova,
    welch_ttest,
)


def _normal(mean: float, std: float, n: int, seed: int) -> np.ndarray:
    return np.random.default_rng(seed).normal(mean, std, n)


# ----------------------------------------------------------------------
# Welch t-test
# ----------------------------------------------------------------------
class TestWelchTTest:
    def test_clearly_different_means_significant(self) -> None:
        a = _normal(40, 5, 100, 1)
        b = _normal(25, 5, 100, 2)
        res = welch_ttest(a, b, label_a="산단", label_b="베이스")
        assert isinstance(res, TTestResult)
        assert res.significant
        assert res.diff > 0
        assert abs(res.cohens_d) > 0.8  # 큰 효과
        assert res.effect_label() == "큼"

    def test_same_distribution_not_significant(self) -> None:
        # 동일 모집단에서 뽑아 반으로 분할 → 차이는 순수 표본변동(귀무가설 참).
        pool = _normal(30, 5, 200, 0)
        res = welch_ttest(pool[:100], pool[100:])
        assert not res.significant

    def test_insufficient_sample_raises(self) -> None:
        with pytest.raises(InsufficientSampleError):
            welch_ttest(_normal(30, 5, 10, 1), _normal(30, 5, 100, 2))

    def test_nan_excluded(self) -> None:
        a = np.concatenate([_normal(40, 5, 50, 1), [np.nan] * 5])
        b = _normal(25, 5, 50, 2)
        res = welch_ttest(a, b)
        assert res.n_a == 50  # NaN 제외

    def test_zero_variance_both_raises(self) -> None:
        with pytest.raises(ValueError, match="분산이 0"):
            welch_ttest(np.full(40, 5.0), np.full(40, 5.0))


# ----------------------------------------------------------------------
# Cohen's d
# ----------------------------------------------------------------------
class TestCohensD:
    def test_zero_when_identical(self) -> None:
        a = _normal(30, 5, 100, 1)
        assert abs(cohens_d(a, a)) < 1e-9

    def test_positive_when_a_larger(self) -> None:
        a = _normal(40, 5, 100, 1)
        b = _normal(20, 5, 100, 2)
        assert cohens_d(a, b) > 0


# ----------------------------------------------------------------------
# ANOVA
# ----------------------------------------------------------------------
class TestOneWayAnova:
    def test_one_group_different_is_significant(self) -> None:
        groups = {
            "a": _normal(30, 5, 60, 1),
            "b": _normal(30, 5, 60, 2),
            "c": _normal(45, 5, 60, 3),  # 명확히 다름
        }
        res = one_way_anova(groups)
        assert isinstance(res, AnovaResult)
        assert res.significant
        assert res.labels[int(np.argmax(res.group_means))] == "c"

    def test_all_same_not_significant(self) -> None:
        groups = {f"g{i}": _normal(30, 5, 60, i) for i in range(4)}
        res = one_way_anova(groups)
        assert not res.significant

    def test_fewer_than_two_valid_groups_raises(self) -> None:
        groups = {"a": _normal(30, 5, 60, 1), "b": _normal(30, 5, 10, 2)}
        with pytest.raises(InsufficientSampleError):
            one_way_anova(groups)


# ----------------------------------------------------------------------
# 고수준 헬퍼 (DataFrame)
# ----------------------------------------------------------------------
class TestHighLevelHelpers:
    def _make_df(self) -> pd.DataFrame:
        rng = np.random.default_rng(42)
        rows = []
        # 산단 3곳(평균 높음) + 베이스 1곳(평균 낮음)
        for st, mean in [("A", 35), ("B", 36), ("C", 34), ("BASE", 22)]:
            for v in rng.normal(mean, 5, 40):
                rows.append({"station_name": st, "pm25": v})
        return pd.DataFrame(rows)

    def test_industrial_vs_baseline(self) -> None:
        df = self._make_df()
        groups = {"A": "산단", "B": "산단", "C": "산단", "BASE": "베이스"}
        res = industrial_vs_baseline(
            df, "pm25", groups, "산단", "베이스"
        )
        assert res.significant
        assert res.diff > 0  # 산단이 더 높음

    def test_anova_across_stations(self) -> None:
        df = self._make_df()
        res = anova_across_stations(df, "pm25")
        assert res.significant
        assert len(res.labels) == 4
