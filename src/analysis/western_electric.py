"""Western Electric Rules (WE Rules) 이상 패턴 자동 판정 모듈.

전통 SPC에서 I-Chart에 적용하는 8개 비랜덤 패턴 탐지 규칙.
단순 3σ 이탈(Rule 1) 외에도 추세·한쪽 쏠림·허깅·지그재그 등을 탐지한다.

규칙 정의 (AIAG SPC Reference Manual / Western Electric Handbook 기준):
  Rule 1 : 1개 점이 ±3σ 초과 (Zone A 밖)
  Rule 2 : 연속 3개 중 2개 이상이 같은 쪽 ±2σ 초과 (Zone A 이상)
  Rule 3 : 연속 5개 중 4개 이상이 같은 쪽 ±1σ 초과 (Zone B 이상)
  Rule 4 : 연속 8개가 중심선의 같은 쪽
  Rule 5 : 연속 6개가 단조 증가 또는 단조 감소 (추세)
  Rule 6 : 연속 15개가 모두 ±1σ 이내 (Zone C 허깅)
  Rule 7 : 연속 14개가 교대로 증감 (지그재그)
  Rule 8 : 연속 8개가 모두 ±1σ 초과 (양쪽 Zone B 이상 — 층화/이봉분포)

설계 원칙:
- 결측(NaN)은 자동 제외
- 각 규칙의 위반 인덱스: 패턴을 완성하는 마지막 점의 인덱스
  (= 경보가 처음 울리는 시점. 이후 연속 창이 또 조건을 만족하면 계속 추가)
- sigma/target 외부 주입 허용 (Phase I 기준 고정 운용 지원)
- InsufficientSampleError: 최소 표본 미만
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

# 최소 표본: Rule 6(15개 창) 적용 가능한 최소치
MIN_SAMPLE_SIZE: int = 2

# I-chart MR 기반 σ 추정 상수
_D2_N2: float = 1.128

# 각 룰 설명 (한국어, 대시보드 표시용)
RULE_DESCRIPTIONS: dict[int, str] = {
    1: "Rule 1: 1점이 ±3σ 초과",
    2: "Rule 2: 연속 3점 중 2점 이상 같은 쪽 ±2σ 초과",
    3: "Rule 3: 연속 5점 중 4점 이상 같은 쪽 ±1σ 초과",
    4: "Rule 4: 연속 8점이 중심선 같은 쪽",
    5: "Rule 5: 연속 6점 단조 증가/감소 (추세)",
    6: "Rule 6: 연속 15점이 ±1σ 이내 (허깅)",
    7: "Rule 7: 연속 14점 교대 증감 (지그재그)",
    8: "Rule 8: 연속 8점이 모두 ±1σ 초과 (층화)",
}


class InsufficientSampleError(ValueError):
    """표본이 최소 요건 미만일 때 발생."""


@dataclass(frozen=True)
class WERulesResult:
    """WE Rules 판정 결과.

    Attributes:
        n: 결측 제외 후 표본 크기.
        center: 중심선(평균).
        sigma: 사용된 σ 추정값.
        violations_by_rule: {rule_number: [위반 인덱스 리스트]} 형태.
            위반 인덱스는 패턴을 완성한 마지막 점의 0-based 인덱스.
        active_rules: 위반이 1건 이상인 룰 번호 집합.
        all_violation_indices: 모든 룰의 위반 인덱스 합집합(중복 제거, 정렬).
    """

    n: int
    center: float
    sigma: float
    violations_by_rule: dict[int, list[int]] = field(default_factory=dict)

    @property
    def active_rules(self) -> set[int]:
        """위반이 1건 이상인 룰 번호 집합."""
        return {r for r, v in self.violations_by_rule.items() if v}

    @property
    def all_violation_indices(self) -> list[int]:
        """모든 룰의 위반 인덱스 합집합 (중복 제거, 정렬)."""
        merged: set[int] = set()
        for v in self.violations_by_rule.values():
            merged.update(v)
        return sorted(merged)

    @property
    def is_in_control(self) -> bool:
        """어떤 룰도 위반이 없으면 True."""
        return len(self.active_rules) == 0

    def summary(self) -> str:
        """위반 룰 요약 문자열 (한국어)."""
        if self.is_in_control:
            return "모든 WE Rules 통과 — 비랜덤 패턴 없음."
        parts = []
        for r in sorted(self.active_rules):
            cnt = len(self.violations_by_rule[r])
            parts.append(f"{RULE_DESCRIPTIONS[r]} ({cnt}건)")
        return "위반 룰: " + " | ".join(parts)


# ---------------------------------------------------------------------------
# 내부 헬퍼
# ---------------------------------------------------------------------------

def _clean(values: pd.Series | np.ndarray | list[float]) -> np.ndarray:
    return pd.Series(values, dtype="float64").dropna().to_numpy()


def _estimate_sigma_mr(arr: np.ndarray) -> float:
    mr = np.abs(np.diff(arr))
    sigma = float(mr.mean()) / _D2_N2
    if sigma == 0 or np.isnan(sigma):
        raise ValueError(
            f"이동범위 기반 σ 추정이 0 또는 NaN (σ={sigma}). "
            "측정값이 모두 동일하거나 비정상 데이터입니다."
        )
    return sigma


def _standardize(arr: np.ndarray, center: float, sigma: float) -> np.ndarray:
    """(arr - center) / sigma 표준화."""
    return (arr - center) / sigma


# ---------------------------------------------------------------------------
# 개별 룰 함수 (모두 내부용 _check_rule_N)
# 반환: 위반 인덱스 리스트 (패턴을 완성한 마지막 점의 0-based 인덱스)
# ---------------------------------------------------------------------------

def _check_rule_1(z: np.ndarray) -> list[int]:
    """Rule 1: 1개 점이 ±3σ 초과."""
    return [int(i) for i in range(len(z)) if abs(z[i]) > 3.0]


def _check_rule_2(z: np.ndarray) -> list[int]:
    """Rule 2: 연속 3개 중 2개 이상이 같은 쪽 ±2σ 초과."""
    violations: list[int] = []
    n = len(z)
    for i in range(2, n):
        w = z[i - 2: i + 1]
        if sum(1 for v in w if v > 2.0) >= 2 or sum(1 for v in w if v < -2.0) >= 2:
            violations.append(i)
    return violations


def _check_rule_3(z: np.ndarray) -> list[int]:
    """Rule 3: 연속 5개 중 4개 이상이 같은 쪽 ±1σ 초과."""
    violations: list[int] = []
    n = len(z)
    for i in range(4, n):
        w = z[i - 4: i + 1]
        if sum(1 for v in w if v > 1.0) >= 4 or sum(1 for v in w if v < -1.0) >= 4:
            violations.append(i)
    return violations


def _check_rule_4(z: np.ndarray) -> list[int]:
    """Rule 4: 연속 8개가 중심선 같은 쪽 (z > 0 또는 z < 0)."""
    violations: list[int] = []
    n = len(z)
    for i in range(7, n):
        w = z[i - 7: i + 1]
        if all(v > 0 for v in w) or all(v < 0 for v in w):
            violations.append(i)
    return violations


def _check_rule_5(arr: np.ndarray) -> list[int]:
    """Rule 5: 연속 6개가 단조 증가 또는 단조 감소."""
    violations: list[int] = []
    n = len(arr)
    for i in range(5, n):
        w = arr[i - 5: i + 1]
        diffs = np.diff(w)
        if bool(np.all(diffs > 0)) or bool(np.all(diffs < 0)):
            violations.append(i)
    return violations


def _check_rule_6(z: np.ndarray) -> list[int]:
    """Rule 6: 연속 15개가 모두 ±1σ 이내 (Zone C 허깅)."""
    violations: list[int] = []
    n = len(z)
    for i in range(14, n):
        w = z[i - 14: i + 1]
        if all(abs(v) < 1.0 for v in w):
            violations.append(i)
    return violations


def _check_rule_7(arr: np.ndarray) -> list[int]:
    """Rule 7: 연속 14개가 교대로 증감 (지그재그)."""
    violations: list[int] = []
    n = len(arr)
    for i in range(13, n):
        w = arr[i - 13: i + 1]
        diffs = np.diff(w)
        # 인접 차분이 모두 반대 부호
        alternating = all(diffs[j] * diffs[j + 1] < 0 for j in range(len(diffs) - 1))
        if alternating:
            violations.append(i)
    return violations


def _check_rule_8(z: np.ndarray) -> list[int]:
    """Rule 8: 연속 8개가 모두 ±1σ 초과 (양쪽 Zone B 이상 — 층화)."""
    violations: list[int] = []
    n = len(z)
    for i in range(7, n):
        w = z[i - 7: i + 1]
        if all(abs(v) > 1.0 for v in w):
            violations.append(i)
    return violations


# ---------------------------------------------------------------------------
# 공개 API
# ---------------------------------------------------------------------------

def we_rules(
    values: pd.Series | np.ndarray | list[float],
    sigma: float | None = None,
    target: float | None = None,
    rules: list[int] | None = None,
    min_n: int = MIN_SAMPLE_SIZE,
) -> WERulesResult:
    """Western Electric 8 Rules를 적용해 비랜덤 패턴을 판정한다.

    Args:
        values: 시간순 측정값 시퀀스. NaN은 자동 제외.
        sigma: σ 직접 지정. None이면 이동범위(MR) 기반 추정.
        target: 중심선. None이면 표본 평균.
        rules: 적용할 룰 번호 리스트(1~8). None이면 전체 8개.
        min_n: 최소 표본 크기.

    Returns:
        WERulesResult 인스턴스.

    Raises:
        InsufficientSampleError: 결측 제외 후 표본 < min_n.
        ValueError: sigma <= 0 또는 rules에 유효하지 않은 번호.
    """
    arr = _clean(values)
    n = int(arr.size)
    if n < min_n:
        raise InsufficientSampleError(
            f"표본 크기 {n}이(가) 최소 요건 {min_n} 미만입니다."
        )

    center = float(arr.mean()) if target is None else float(target)
    sig = _estimate_sigma_mr(arr) if sigma is None else float(sigma)
    if sig <= 0 or np.isnan(sig):
        raise ValueError(f"σ는 양수여야 합니다 (받은 값: {sig}).")

    active_rules = list(range(1, 9)) if rules is None else rules
    for r in active_rules:
        if r not in range(1, 9):
            raise ValueError(f"유효하지 않은 룰 번호: {r}. 1~8 사이 정수만 허용.")

    z = _standardize(arr, center, sig)

    _rule_funcs = {
        1: lambda: _check_rule_1(z),
        2: lambda: _check_rule_2(z),
        3: lambda: _check_rule_3(z),
        4: lambda: _check_rule_4(z),
        5: lambda: _check_rule_5(arr),
        6: lambda: _check_rule_6(z),
        7: lambda: _check_rule_7(arr),
        8: lambda: _check_rule_8(z),
    }

    violations_by_rule: dict[int, list[int]] = {}
    for r in active_rules:
        violations_by_rule[r] = _rule_funcs[r]()

    return WERulesResult(
        n=n,
        center=center,
        sigma=sig,
        violations_by_rule=violations_by_rule,
    )
