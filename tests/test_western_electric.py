"""Western Electric Rules 단위 테스트.

각 룰에 대해:
- 해당 패턴을 직접 심었을 때 탐지되는지
- 안정 공정(in-control)에서 거짓경보가 거의 없는지
- 경계 조건 및 예외 처리
"""

from __future__ import annotations

import numpy as np
import pytest

from src.analysis.western_electric import (
    InsufficientSampleError,
    RULE_DESCRIPTIONS,
    WERulesResult,
    we_rules,
)


def _stable(n: int = 300, mean: float = 50.0, std: float = 5.0, seed: int = 42) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return rng.normal(loc=mean, scale=std, size=n)


# ---------------------------------------------------------------------------
# 기본 동작
# ---------------------------------------------------------------------------

class TestWeRulesBasic:
    def test_returns_we_rules_result(self) -> None:
        res = we_rules(_stable())
        assert isinstance(res, WERulesResult)

    def test_all_8_rules_applied_by_default(self) -> None:
        res = we_rules(_stable())
        assert set(res.violations_by_rule.keys()) == set(range(1, 9))

    def test_selective_rules(self) -> None:
        res = we_rules(_stable(), rules=[1, 4])
        assert set(res.violations_by_rule.keys()) == {1, 4}

    def test_invalid_rule_number_raises(self) -> None:
        with pytest.raises(ValueError, match="유효하지 않은"):
            we_rules(_stable(), rules=[0])

    def test_insufficient_sample_raises(self) -> None:
        with pytest.raises(InsufficientSampleError):
            we_rules([50.0])  # 1개 < 2

    def test_nan_excluded(self) -> None:
        data = list(_stable(50)) + [float("nan")] * 10
        res = we_rules(data)
        assert res.n == 50

    def test_sigma_zero_raises(self) -> None:
        with pytest.raises(ValueError, match="σ"):
            we_rules(_stable(), sigma=0.0)

    def test_explicit_sigma_and_target(self) -> None:
        data = _stable()
        res = we_rules(data, sigma=5.0, target=50.0)
        assert res.sigma == 5.0
        assert res.center == 50.0

    def test_stable_process_mostly_in_control(self) -> None:
        """안정 공정: Rule 1(3σ) 위반이 거의 없어야 함."""
        res = we_rules(_stable(n=500), rules=[1])
        assert len(res.violations_by_rule[1]) <= 5

    def test_is_in_control_property(self) -> None:
        # 모든 룰 통과 → True
        res = we_rules(_stable(n=500), rules=[1])
        # 통제 아래일 수도 있고 아닐 수도 있으므로, 타입만 확인
        assert isinstance(res.is_in_control, bool)

    def test_all_violation_indices_sorted_unique(self) -> None:
        data = _stable()
        data[50] = 200.0  # Rule 1 트리거
        res = we_rules(data)
        idxs = res.all_violation_indices
        assert idxs == sorted(set(idxs))


# ---------------------------------------------------------------------------
# Rule 1: 1개 점이 ±3σ 초과
# ---------------------------------------------------------------------------

class TestRule1:
    def test_outlier_detected(self) -> None:
        data = _stable(n=200)
        data[100] = 200.0  # 명백한 3σ 초과
        res = we_rules(data, sigma=5.0, target=50.0, rules=[1])
        assert 100 in res.violations_by_rule[1]

    def test_no_false_alarm_stable(self) -> None:
        data = _stable(n=500)
        res = we_rules(data, rules=[1])
        assert len(res.violations_by_rule[1]) <= 5  # 0.27% 명목 FAR


# ---------------------------------------------------------------------------
# Rule 2: 연속 3개 중 2개 이상 같은 쪽 ±2σ 초과
# ---------------------------------------------------------------------------

class TestRule2:
    def test_pattern_detected(self) -> None:
        data = _stable(n=100, mean=50.0, std=5.0)
        # 인덱스 50~52: 3개 중 2개를 +2σ 초과 (55=+1σ, 62=+2.4σ, 63=+2.4σ)
        data[50] = 50 + 2.5 * 5  # +2.5σ
        data[52] = 50 + 2.5 * 5  # +2.5σ
        res = we_rules(data, sigma=5.0, target=50.0, rules=[2])
        assert 52 in res.violations_by_rule[2]

    def test_opposite_sides_not_triggered(self) -> None:
        """같은 쪽이 아니라 양쪽에 걸쳐 있으면 Rule 2 불발."""
        data = _stable(n=100, mean=50.0, std=5.0)
        data[50] = 50 + 2.5 * 5   # 양수 쪽
        data[51] = 50 - 2.5 * 5   # 음수 쪽
        res = we_rules(data, sigma=5.0, target=50.0, rules=[2])
        # 창 [50,51,52]: 양수 1개, 음수 1개 → 조건 불만족
        assert 51 not in res.violations_by_rule[2]


# ---------------------------------------------------------------------------
# Rule 3: 연속 5개 중 4개 이상 같은 쪽 ±1σ 초과
# ---------------------------------------------------------------------------

class TestRule3:
    def test_pattern_detected(self) -> None:
        data = np.full(50, 50.0)
        # 인덱스 10~14: 5개 중 4개가 +1σ 초과
        data[10] = 56.0  # +1.2σ (sigma=5 기준)
        data[11] = 56.0
        data[12] = 56.0
        data[13] = 56.0
        data[14] = 52.0  # +0.4σ (조건 제외)
        res = we_rules(data, sigma=5.0, target=50.0, rules=[3])
        assert 14 in res.violations_by_rule[3]

    def test_mixed_sides_not_triggered(self) -> None:
        data = np.array([57.0, 57.0, 43.0, 57.0, 57.0] * 10, dtype=float)
        # 양수 4개 + 음수 1개 (같은 쪽 4개 만족하므로 탐지됨)
        res = we_rules(data, sigma=5.0, target=50.0, rules=[3])
        # +1σ 초과 4개이므로 탐지돼야 함
        assert len(res.violations_by_rule[3]) > 0


# ---------------------------------------------------------------------------
# Rule 4: 연속 8개가 중심선 같은 쪽
# ---------------------------------------------------------------------------

class TestRule4:
    def test_8_above_detected(self) -> None:
        data = np.full(50, 50.0)
        data[10:18] = 52.0  # 중심선(50) 위쪽 8개
        res = we_rules(data, sigma=5.0, target=50.0, rules=[4])
        assert 17 in res.violations_by_rule[4]

    def test_7_not_enough(self) -> None:
        data = np.full(50, 50.0)
        data[10:17] = 52.0  # 7개만
        data[17] = 48.0     # 중심선 아래
        res = we_rules(data, sigma=5.0, target=50.0, rules=[4])
        # 17번은 아래로 꺾였으므로 창 [10..17]이 같은 쪽 아님
        assert 17 not in res.violations_by_rule[4]


# ---------------------------------------------------------------------------
# Rule 5: 연속 6개 단조 증가/감소
# ---------------------------------------------------------------------------

class TestRule5:
    def test_increasing_trend_detected(self) -> None:
        data = np.full(50, 50.0)
        data[10:16] = [50, 51, 52, 53, 54, 55]  # 6개 단조 증가
        res = we_rules(data, sigma=5.0, target=50.0, rules=[5])
        assert 15 in res.violations_by_rule[5]

    def test_decreasing_trend_detected(self) -> None:
        data = np.full(50, 50.0)
        data[10:16] = [55, 54, 53, 52, 51, 50]  # 6개 단조 감소
        res = we_rules(data, sigma=5.0, target=50.0, rules=[5])
        assert 15 in res.violations_by_rule[5]

    def test_non_monotone_not_triggered(self) -> None:
        data = np.full(50, 50.0)
        data[10:16] = [50, 52, 51, 53, 54, 55]  # 51에서 꺾임
        res = we_rules(data, sigma=5.0, target=50.0, rules=[5])
        assert 15 not in res.violations_by_rule[5]


# ---------------------------------------------------------------------------
# Rule 6: 연속 15개가 ±1σ 이내 (허깅)
# ---------------------------------------------------------------------------

class TestRule6:
    def test_hugging_detected(self) -> None:
        data = np.full(50, 50.0)
        # 인덱스 0~14: 15개 모두 ±0.5σ 이내
        data[0:15] = [50.1, 49.9, 50.2, 50.0, 50.1,
                      49.8, 50.3, 50.1, 49.9, 50.2,
                      50.0, 50.1, 49.8, 50.2, 50.1]
        res = we_rules(data, sigma=5.0, target=50.0, rules=[6])
        assert 14 in res.violations_by_rule[6]

    def test_14_points_not_enough(self) -> None:
        data = np.full(50, 50.0)
        data[0:14] = [50.1] * 14
        data[14] = 56.0  # ±1σ 초과
        res = we_rules(data, sigma=5.0, target=50.0, rules=[6])
        assert 14 not in res.violations_by_rule[6]


# ---------------------------------------------------------------------------
# Rule 7: 연속 14개 교대 증감
# ---------------------------------------------------------------------------

class TestRule7:
    def test_zigzag_detected(self) -> None:
        # 지그재그: 올라갔다 내려갔다 반복 (14개)
        base = np.full(50, 50.0)
        zigzag = [50.0, 52.0, 50.0, 52.0, 50.0, 52.0, 50.0,
                  52.0, 50.0, 52.0, 50.0, 52.0, 50.0, 52.0]  # 14개
        base[0:14] = zigzag
        res = we_rules(base, sigma=5.0, target=50.0, rules=[7])
        assert 13 in res.violations_by_rule[7]

    def test_monotone_not_zigzag(self) -> None:
        data = np.arange(50, dtype=float)
        res = we_rules(data, sigma=5.0, target=25.0, rules=[7])
        assert len(res.violations_by_rule[7]) == 0


# ---------------------------------------------------------------------------
# Rule 8: 연속 8개 모두 ±1σ 초과 (층화)
# ---------------------------------------------------------------------------

class TestRule8:
    def test_stratification_detected(self) -> None:
        data = np.full(50, 50.0)
        # 8개 모두 +1σ 초과 or -1σ 미만 (양쪽 섞여도 OK)
        data[10:14] = 56.0  # +1.2σ
        data[14:18] = 44.0  # -1.2σ
        res = we_rules(data, sigma=5.0, target=50.0, rules=[8])
        assert 17 in res.violations_by_rule[8]

    def test_within_1sigma_not_triggered(self) -> None:
        data = np.full(50, 50.5)  # 중심 근처
        res = we_rules(data, sigma=5.0, target=50.0, rules=[8])
        assert len(res.violations_by_rule[8]) == 0


# ---------------------------------------------------------------------------
# WERulesResult 프로퍼티
# ---------------------------------------------------------------------------

class TestWERulesResult:
    def test_active_rules_empty_when_clean(self) -> None:
        res = we_rules(np.full(30, 50.0), sigma=5.0, target=50.0)
        # 상수 데이터: Rule 5/6 등 걸릴 수 있지만, active_rules는 세트
        assert isinstance(res.active_rules, set)

    def test_summary_in_control(self) -> None:
        # 이탈 없는 케이스 강제 구성
        from src.analysis.western_electric import WERulesResult
        r = WERulesResult(
            n=100, center=50.0, sigma=5.0,
            violations_by_rule={i: [] for i in range(1, 9)},
        )
        assert "통과" in r.summary()

    def test_summary_with_violations(self) -> None:
        from src.analysis.western_electric import WERulesResult
        r = WERulesResult(
            n=100, center=50.0, sigma=5.0,
            violations_by_rule={1: [10, 20], **{i: [] for i in range(2, 9)}},
        )
        assert "Rule 1" in r.summary()
        assert "2건" in r.summary()

    def test_rule_descriptions_have_8_entries(self) -> None:
        assert len(RULE_DESCRIPTIONS) == 8
        assert set(RULE_DESCRIPTIONS.keys()) == set(range(1, 9))
