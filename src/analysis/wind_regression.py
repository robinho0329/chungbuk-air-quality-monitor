"""풍향·기상 결합 분석 (Phase 4).

대기질 측정(data_time)과 기상 관측(obs_time)을 시간 단위로 조인해:
1. 오염장미(pollution rose): 풍향 8방위별 평균 농도 — 어느 방향 바람이 오염을 싣고 오나.
2. 산단 방위 검정: '산단→측정소' 방위 섹터에서 부는 바람일 때 농도가 유의하게 높은가
   (Welch t-test + Cohen's d). H4 가설의 정량 검정.
3. 기상 회귀: 농도 ~ 풍속·기온·습도. 분산분해에서 드러난 '시간·기상 97.6%'의 내역을
   실제 기상 변수로 설명(추론 → 실증).

설계 원칙: scipy/numpy만 사용, 외부 의존 최소. 표본 부족 시 명시적 예외.
좌표는 (위도, 경도). 방위는 0=북, 시계방향(기상 풍향 관례와 동일).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

MIN_SAMPLE_SIZE: int = 30

# 8방위 라벨 (중심 방위각)
SECTORS_8 = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
_SECTOR_DEG = {s: i * 45.0 for i, s in enumerate(SECTORS_8)}


class InsufficientSampleError(ValueError):
    """표본이 최소 요건 미만일 때 발생."""


# ---------------------------------------------------------------------------
# 기하: 방위각
# ---------------------------------------------------------------------------

def bearing(from_lat: float, from_lon: float, to_lat: float, to_lon: float) -> float:
    """from→to 초기 방위각(deg, 0=북, 시계방향, 0~360)."""
    φ1, φ2 = math.radians(from_lat), math.radians(to_lat)
    dλ = math.radians(to_lon - from_lon)
    y = math.sin(dλ) * math.cos(φ2)
    x = math.cos(φ1) * math.sin(φ2) - math.sin(φ1) * math.cos(φ2) * math.cos(dλ)
    return (math.degrees(math.atan2(y, x)) + 360.0) % 360.0


def angular_diff(a: float, b: float) -> float:
    """두 방위각의 최소 차이(0~180)."""
    d = abs((a - b) % 360.0)
    return min(d, 360.0 - d)


def wind_sector(deg: float) -> str:
    """풍향(deg)을 8방위 라벨로. 풍향은 '바람이 불어오는 방향'(기상 관례)."""
    idx = int(((deg % 360.0) + 22.5) // 45.0) % 8
    return SECTORS_8[idx]


# ---------------------------------------------------------------------------
# 결과 컨테이너
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class DirectionalResult:
    """산단 방위 섹터 vs 그 외의 농도 비교."""
    pollutant: str
    source_bearing: float
    n_in: int
    n_out: int
    mean_in: float
    mean_out: float
    diff: float
    t_stat: float
    p_value: float
    cohens_d: float

    @property
    def significant(self) -> bool:
        return self.p_value < 0.05

    def interpret(self) -> str:
        if self.n_in < MIN_SAMPLE_SIZE or self.n_out < MIN_SAMPLE_SIZE:
            return "표본 부족 — 해석 보류"
        if not self.significant:
            return (
                f"산단 방위 바람일 때와 아닐 때 {self.pollutant} 평균차는 "
                f"유의하지 않음 (p={self.p_value:.4f})."
            )
        hi = "높음" if self.diff > 0 else "낮음"
        return (
            f"산단({self.source_bearing:.0f}°) 방위 바람일 때 {self.pollutant}가 "
            f"{abs(self.diff):.2f} {hi} (p={self.p_value:.4f}, d={self.cohens_d:.2f})."
        )


@dataclass(frozen=True)
class WeatherRegressionResult:
    """농도 ~ 풍속·기온·습도 다중선형회귀."""
    pollutant: str
    n: int
    r2: float
    coef: dict[str, float] = field(default_factory=dict)
    intercept: float = 0.0


# ---------------------------------------------------------------------------
# 데이터 결합
# ---------------------------------------------------------------------------

def join_air_weather(
    df_air: pd.DataFrame, df_wx: pd.DataFrame,
    air_time: str = "data_time", wx_time: str = "obs_time",
) -> pd.DataFrame:
    """대기질·기상을 정시(hour) 기준으로 inner join.

    Args:
        df_air: data_time + 오염물질 컬럼.
        df_wx: obs_time + ta/hm/ws/wd/rn.
    Returns:
        조인된 DataFrame (양쪽 컬럼 + 'wd','ws','ta','hm','rn').
    """
    a = df_air.copy()
    w = df_wx.copy()
    a["_h"] = pd.to_datetime(a[air_time]).dt.floor("h")
    w["_h"] = pd.to_datetime(w[wx_time]).dt.floor("h")
    w = w.drop_duplicates("_h", keep="last")
    merged = a.merge(w[["_h", "ta", "hm", "ws", "wd", "rn"]], on="_h", how="inner")
    return merged.drop(columns="_h")


# ---------------------------------------------------------------------------
# 1. 오염장미
# ---------------------------------------------------------------------------

def pollution_rose(df: pd.DataFrame, pollutant: str) -> dict[str, float]:
    """풍향 8방위별 평균 농도. {섹터: 평균} (해당 섹터 표본 없으면 제외)."""
    sub = df.dropna(subset=[pollutant, "wd"])
    if sub.empty:
        return {}
    sectors = sub["wd"].map(wind_sector)
    return {
        s: float(sub.loc[sectors == s, pollutant].mean())
        for s in SECTORS_8 if (sectors == s).any()
    }


# ---------------------------------------------------------------------------
# 2. 산단 방위 검정
# ---------------------------------------------------------------------------

def directional_test(
    df: pd.DataFrame, pollutant: str, source_bearing: float,
    sector_width: float = 45.0, min_n: int = MIN_SAMPLE_SIZE,
) -> DirectionalResult:
    """풍향이 산단 방위(±sector_width/2) 안일 때 vs 밖일 때 농도 비교 (Welch t-test).

    풍향(wd)은 '바람이 불어오는 방향'이므로, 산단이 측정소 기준 source_bearing에
    있을 때 그 방위에서 부는 바람이 산단 배출을 싣고 온다.
    """
    from scipy import stats

    sub = df.dropna(subset=[pollutant, "wd"])
    if len(sub) < min_n:
        raise InsufficientSampleError(f"표본 {len(sub)} < {min_n}")
    in_mask = sub["wd"].map(lambda d: angular_diff(d, source_bearing) <= sector_width / 2)
    a = sub.loc[in_mask, pollutant].to_numpy()
    b = sub.loc[~in_mask, pollutant].to_numpy()
    if len(a) < 2 or len(b) < 2:
        raise InsufficientSampleError("한쪽 그룹 표본 부족")
    t, p = stats.ttest_ind(a, b, equal_var=False)
    # Cohen's d (pooled)
    na, nb = len(a), len(b)
    sp = math.sqrt(((na - 1) * a.var(ddof=1) + (nb - 1) * b.var(ddof=1)) / (na + nb - 2))
    d = (a.mean() - b.mean()) / sp if sp > 0 else 0.0
    return DirectionalResult(
        pollutant=pollutant, source_bearing=source_bearing,
        n_in=na, n_out=nb, mean_in=float(a.mean()), mean_out=float(b.mean()),
        diff=float(a.mean() - b.mean()), t_stat=float(t), p_value=float(p),
        cohens_d=float(d),
    )


# ---------------------------------------------------------------------------
# 3. 기상 회귀
# ---------------------------------------------------------------------------

def weather_regression(
    df: pd.DataFrame, pollutant: str,
    predictors: tuple[str, ...] = ("ws", "ta", "hm"),
    min_n: int = MIN_SAMPLE_SIZE,
) -> WeatherRegressionResult:
    """농도 ~ predictors 다중선형회귀 (OLS, numpy.lstsq). R²·계수 반환."""
    cols = [pollutant, *predictors]
    sub = df.dropna(subset=cols)
    if len(sub) < min_n:
        raise InsufficientSampleError(f"표본 {len(sub)} < {min_n}")
    X = sub[list(predictors)].to_numpy(dtype=float)
    y = sub[pollutant].to_numpy(dtype=float)
    Xd = np.column_stack([np.ones(len(X)), X])
    beta, *_ = np.linalg.lstsq(Xd, y, rcond=None)
    yhat = Xd @ beta
    ss_res = float(((y - yhat) ** 2).sum())
    ss_tot = float(((y - y.mean()) ** 2).sum())
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0
    return WeatherRegressionResult(
        pollutant=pollutant, n=len(sub), r2=r2,
        coef={p: float(b) for p, b in zip(predictors, beta[1:])},
        intercept=float(beta[0]),
    )
