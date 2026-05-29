"""가설검정 모듈: 산단 영향군 vs 베이스라인 비교 (t-test / ANOVA).

DMAIC의 Analyze 단계. 측정소 위치 가설(docs/ANALYSIS_HYPOTHESES.md)을 통계적으로 검증한다.

- Welch t-test(등분산 가정 안 함): 산단 영향군 vs 베이스라인(용암동) 평균 차이
- One-way ANOVA: 측정소(또는 그룹) 간 평균이 모두 같은가
- Cohen's d: 통계적 유의성과 별개의 '실질적' 효과크기 (QC에서 중요)

설계 원칙:
- 최소 표본(그룹당 30) 미만이면 InsufficientSampleError (검정 거부)
- 결측(NaN) 자동 제외
- p-value만 보지 않고 효과크기(Cohen's d / eta²)를 함께 보고
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy import stats

MIN_SAMPLE_SIZE: int = 30
DEFAULT_ALPHA: float = 0.05


class InsufficientSampleError(ValueError):
    """그룹 표본이 최소 요건 미만일 때 발생."""


def _clean(values: pd.Series | np.ndarray | list[float]) -> np.ndarray:
    """NaN 제거 후 float64 ndarray로 반환."""
    return pd.Series(values, dtype="float64").dropna().to_numpy()


def cohens_d(a: np.ndarray, b: np.ndarray) -> float:
    """두 독립표본의 Cohen's d (pooled SD 기준 효과크기).

    |d| 해석(통상): 0.2 작음 / 0.5 중간 / 0.8 큼.
    """
    na, nb = len(a), len(b)
    va, vb = a.var(ddof=1), b.var(ddof=1)
    pooled = np.sqrt(((na - 1) * va + (nb - 1) * vb) / (na + nb - 2))
    if pooled == 0:
        return 0.0
    return float((a.mean() - b.mean()) / pooled)


@dataclass(frozen=True)
class TTestResult:
    """Welch t-test 결과.

    Attributes:
        label_a, label_b: 두 그룹 라벨.
        n_a, n_b: 각 그룹 표본 수.
        mean_a, mean_b: 각 그룹 평균.
        diff: mean_a - mean_b.
        t_stat: t 통계량.
        p_value: 양측 p-value.
        dof: Welch 자유도.
        cohens_d: 효과크기.
        alpha: 유의수준.
    """

    label_a: str
    label_b: str
    n_a: int
    n_b: int
    mean_a: float
    mean_b: float
    diff: float
    t_stat: float
    p_value: float
    dof: float
    cohens_d: float
    alpha: float = DEFAULT_ALPHA

    @property
    def significant(self) -> bool:
        """유의수준 alpha에서 통계적으로 유의한가."""
        return self.p_value < self.alpha

    def effect_label(self) -> str:
        """Cohen's d 크기 해석 (한국어)."""
        ad = abs(self.cohens_d)
        if ad < 0.2:
            return "미미함"
        if ad < 0.5:
            return "작음"
        if ad < 0.8:
            return "중간"
        return "큼"

    def interpret(self) -> str:
        """검정 결과 한 줄 해석."""
        if not self.significant:
            return (
                f"'{self.label_a}'와 '{self.label_b}'의 평균 차이는 "
                f"통계적으로 유의하지 않음 (p={self.p_value:.4f})."
            )
        direction = "높음" if self.diff > 0 else "낮음"
        return (
            f"'{self.label_a}'가 '{self.label_b}'보다 평균 {abs(self.diff):.2f} {direction} "
            f"(p={self.p_value:.4f}, 효과크기 {self.effect_label()} d={self.cohens_d:.2f})."
        )


@dataclass(frozen=True)
class AnovaResult:
    """One-way ANOVA 결과.

    Attributes:
        labels: 그룹 라벨 리스트.
        group_ns: 그룹별 표본 수.
        group_means: 그룹별 평균.
        f_stat: F 통계량.
        p_value: p-value.
        eta_squared: 효과크기 η² (집단간제곱합/전체제곱합).
        alpha: 유의수준.
    """

    labels: list[str]
    group_ns: list[int]
    group_means: list[float]
    f_stat: float
    p_value: float
    eta_squared: float
    alpha: float = DEFAULT_ALPHA

    @property
    def significant(self) -> bool:
        return self.p_value < self.alpha

    def interpret(self) -> str:
        if not self.significant:
            return (
                f"{len(self.labels)}개 그룹 평균은 모두 같다고 볼 수 있음 "
                f"(p={self.p_value:.4f})."
            )
        hi = self.labels[int(np.argmax(self.group_means))]
        lo = self.labels[int(np.argmin(self.group_means))]
        return (
            f"그룹 간 평균 차이가 유의함 (F={self.f_stat:.2f}, p={self.p_value:.4f}, "
            f"η²={self.eta_squared:.3f}). 최고='{hi}', 최저='{lo}'."
        )


def welch_ttest(
    group_a: pd.Series | np.ndarray | list[float],
    group_b: pd.Series | np.ndarray | list[float],
    *,
    label_a: str = "A",
    label_b: str = "B",
    alpha: float = DEFAULT_ALPHA,
    min_n: int = MIN_SAMPLE_SIZE,
) -> TTestResult:
    """두 독립표본의 Welch t-test (등분산 가정 안 함).

    Raises:
        InsufficientSampleError: 어느 한 그룹이라도 표본 < min_n.
        ValueError: 분산이 0이라 검정 불가.
    """
    a, b = _clean(group_a), _clean(group_b)
    if len(a) < min_n or len(b) < min_n:
        raise InsufficientSampleError(
            f"표본 부족: {label_a}={len(a)}, {label_b}={len(b)} (최소 {min_n})."
        )
    if a.var(ddof=1) == 0 and b.var(ddof=1) == 0:
        raise ValueError("두 그룹 모두 분산이 0이라 t-test 불가.")

    res = stats.ttest_ind(a, b, equal_var=False)  # Welch
    return TTestResult(
        label_a=label_a,
        label_b=label_b,
        n_a=len(a),
        n_b=len(b),
        mean_a=float(a.mean()),
        mean_b=float(b.mean()),
        diff=float(a.mean() - b.mean()),
        t_stat=float(res.statistic),
        p_value=float(res.pvalue),
        dof=float(getattr(res, "df", np.nan)),
        cohens_d=cohens_d(a, b),
        alpha=alpha,
    )


def one_way_anova(
    groups: dict[str, pd.Series | np.ndarray | list[float]],
    *,
    alpha: float = DEFAULT_ALPHA,
    min_n: int = MIN_SAMPLE_SIZE,
) -> AnovaResult:
    """여러 그룹의 평균이 모두 같은지 검정 (one-way ANOVA).

    Args:
        groups: {라벨: 값 시퀀스}. 표본이 min_n 미만인 그룹은 자동 제외.

    Raises:
        InsufficientSampleError: 유효 그룹이 2개 미만.
    """
    cleaned: dict[str, np.ndarray] = {}
    for label, vals in groups.items():
        arr = _clean(vals)
        if len(arr) >= min_n and arr.var(ddof=1) > 0:
            cleaned[label] = arr
    if len(cleaned) < 2:
        raise InsufficientSampleError(
            f"ANOVA에는 표본 {min_n}+ 인 그룹이 2개 이상 필요. 현재 {len(cleaned)}개."
        )

    labels = list(cleaned.keys())
    arrays = [cleaned[label] for label in labels]
    f_stat, p_value = stats.f_oneway(*arrays)

    # eta² = SS_between / SS_total
    all_vals = np.concatenate(arrays)
    grand_mean = all_vals.mean()
    ss_between = sum(len(g) * (g.mean() - grand_mean) ** 2 for g in arrays)
    ss_total = float(((all_vals - grand_mean) ** 2).sum())
    eta_sq = ss_between / ss_total if ss_total > 0 else 0.0

    return AnovaResult(
        labels=labels,
        group_ns=[len(g) for g in arrays],
        group_means=[float(g.mean()) for g in arrays],
        f_stat=float(f_stat),
        p_value=float(p_value),
        eta_squared=float(eta_sq),
        alpha=alpha,
    )


def industrial_vs_baseline(
    df: pd.DataFrame,
    pollutant: str,
    station_groups: dict[str, str],
    industrial_group: str,
    baseline_group: str,
    *,
    alpha: float = DEFAULT_ALPHA,
    min_n: int = MIN_SAMPLE_SIZE,
) -> TTestResult:
    """산단 영향군 vs 베이스라인의 특정 오염물질 평균을 Welch t-test로 비교.

    Args:
        df: station_name, {pollutant} 컬럼을 가진 측정 DataFrame.
        pollutant: 비교할 컬럼명 (예: 'pm25').
        station_groups: {측정소명: 그룹명} 매핑.
        industrial_group, baseline_group: 그룹명.
    """
    grp = df["station_name"].map(station_groups)
    a = df.loc[grp == industrial_group, pollutant]
    b = df.loc[grp == baseline_group, pollutant]
    return welch_ttest(
        a, b,
        label_a=industrial_group,
        label_b=baseline_group,
        alpha=alpha,
        min_n=min_n,
    )


def anova_across_stations(
    df: pd.DataFrame,
    pollutant: str,
    *,
    alpha: float = DEFAULT_ALPHA,
    min_n: int = MIN_SAMPLE_SIZE,
) -> AnovaResult:
    """측정소 간 특정 오염물질 평균이 모두 같은지 ANOVA로 검정."""
    groups = {
        str(name): sub[pollutant]
        for name, sub in df.groupby("station_name")
    }
    return one_way_anova(groups, alpha=alpha, min_n=min_n)
