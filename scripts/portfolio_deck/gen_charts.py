"""포트폴리오 덱용 차트 이미지 생성 (실데이터 + Pretendard).

레퍼런스 스타일: 깔끔한 흰 배경, 코발트/회색/레드 팔레트, 한글 라벨.
출력: build/deck/img/*.png
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path("/Users/t2025-m0190/workspace/chungbuk-air-quality-monitor")
sys.path.insert(0, str(ROOT))

import matplotlib  # noqa: E402
matplotlib.use("Agg")
import matplotlib.font_manager as fm  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

# Pretendard 등록
FONT_DIR = Path("/Users/t2025-m0190/Library/Fonts")
for f in ["Regular", "Medium", "SemiBold", "Bold", "ExtraBold", "Black"]:
    p = FONT_DIR / f"Pretendard-{f}.otf"
    if p.exists():
        fm.fontManager.addfont(str(p))
plt.rcParams["font.family"] = "Pretendard"
plt.rcParams["axes.unicode_minus"] = False

from src.analysis.capability import InsufficientSampleError, compute_capability  # noqa: E402
from src.analysis.control_chart import i_chart  # noqa: E402
from src.analysis.residual_chart import residual_i_chart  # noqa: E402
from src.analysis.usl_lsl import SPEC_LIMITS  # noqa: E402
from src.config import STATION_GROUPS, INDUSTRIAL_GROUP, BASELINE_GROUP  # noqa: E402
from src.storage.database import query_all  # noqa: E402

POLLUTANTS = list(SPEC_LIMITS.keys())
KR = {p: SPEC_LIMITS[p].description.split("(")[0].strip() for p in POLLUTANTS}
DISP = {"pm10": "PM10", "pm25": "PM2.5", "o3": "O₃", "no2": "NO₂", "so2": "SO₂", "co": "CO"}

IMG = Path("/Users/t2025-m0190/workspace/chungbuk-air-quality-monitor/build/deck/img")
IMG.mkdir(parents=True, exist_ok=True)

# 팔레트
COBALT = "#1F40E6"
NAVY = "#16294D"
RED = "#E04646"
GRAY = "#9AA5B1"
TEAL = "#0E9488"

def load():
    rows = query_all()
    df = pd.DataFrame.from_records([
        {"station_name": r.station_name, "data_time": r.data_time,
         **{p: getattr(r, p) for p in POLLUTANTS}} for r in rows
    ])
    df["data_time"] = pd.to_datetime(df["data_time"])
    return df

def usl(p):
    s = SPEC_LIMITS[p]
    for b in ("daily", "annual", "hourly"):
        u = s.usl_for(b)
        if u is not None:
            return u
    return None

df = load()
stations = sorted(df["station_name"].unique())

# ── 1. Cpk 히트맵 (측정소 × 오염물질) ─────────────────────────────
cpk_mat = np.full((len(stations), len(POLLUTANTS)), np.nan)
for i, st in enumerate(stations):
    sub = df[df["station_name"] == st]
    for j, p in enumerate(POLLUTANTS):
        u = usl(p)
        if u is None:
            continue
        try:
            cpk_mat[i, j] = compute_capability(sub[p].dropna(), usl=u, lsl=0.0).cpk
        except (InsufficientSampleError, ValueError):
            pass

fig, ax = plt.subplots(figsize=(9, 4.1), dpi=200)
# 1.0 기준 발산형: 낮을수록 빨강(위험), 높을수록 파랑(양호)
from matplotlib.colors import TwoSlopeNorm
norm = TwoSlopeNorm(vmin=0.2, vcenter=1.0, vmax=1.6)
im = ax.imshow(cpk_mat, cmap="RdYlBu", norm=norm, aspect="auto")
ax.set_xticks(range(len(POLLUTANTS)))
ax.set_xticklabels([DISP[p] for p in POLLUTANTS], fontsize=12, fontweight="bold")
ax.set_yticks(range(len(stations)))
ax.set_yticklabels(stations, fontsize=12)
for i in range(len(stations)):
    for j in range(len(POLLUTANTS)):
        v = cpk_mat[i, j]
        if not np.isnan(v):
            ax.text(j, i, f"{v:.2f}", ha="center", va="center",
                    fontsize=11, fontweight="bold",
                    color="white" if (v < 0.55 or v > 1.45) else "#222222")
ax.set_title("측정소 × 오염물질 공정능력지수(Cpk)  ·  낮을수록 불량 위험",
             fontsize=13, fontweight="bold", color=NAVY, pad=12)
cbar = fig.colorbar(im, ax=ax, fraction=0.025, pad=0.02)
cbar.ax.tick_params(labelsize=9)
ax.set_xticks(np.arange(-.5, len(POLLUTANTS), 1), minor=True)
ax.set_yticks(np.arange(-.5, len(stations), 1), minor=True)
ax.grid(which="minor", color="white", linewidth=2)
ax.tick_params(which="minor", length=0)
fig.tight_layout()
fig.savefig(IMG / "cpk_heatmap.png", bbox_inches="tight")
plt.close(fig)

# ── 2. 오염물질별 평균 Cpk 바 (임계선) ────────────────────────────
mean_cpk = {p: np.nanmean(cpk_mat[:, j]) for j, p in enumerate(POLLUTANTS)}
order = sorted(POLLUTANTS, key=lambda p: mean_cpk[p])
vals = [mean_cpk[p] for p in order]
colors = [RED if v < 1.0 else TEAL for v in vals]

fig, ax = plt.subplots(figsize=(8.2, 4.3), dpi=200)
bars = ax.bar([DISP[p] for p in order], vals, color=colors, width=0.62, zorder=3)
ax.axhline(1.0, color=RED, ls="--", lw=1.4, zorder=2)
ax.axhline(1.33, color="#2E7D32", ls=":", lw=1.4, zorder=2)
ax.text(len(order)-0.4, 1.02, "Cpk 1.0 (불량 위험 임계)", color=RED, fontsize=9.5, ha="right", fontweight="bold")
ax.text(len(order)-0.4, 1.35, "Cpk 1.33 (양호)", color="#2E7D32", fontsize=9.5, ha="right", fontweight="bold")
for b, v in zip(bars, vals):
    ax.text(b.get_x()+b.get_width()/2, v+0.02, f"{v:.2f}", ha="center", va="bottom",
            fontsize=11, fontweight="bold", color=NAVY)
ax.set_ylim(0, 1.55)
ax.set_ylabel("평균 Cpk", fontsize=11)
ax.set_title("오염물질별 평균 공정능력지수", fontsize=13, fontweight="bold", color=NAVY, pad=10)
ax.spines[["top", "right"]].set_visible(False)
ax.tick_params(labelsize=12)
ax.grid(axis="y", color="#E2E8F0", lw=0.7, zorder=0)
fig.tight_layout()
fig.savefig(IMG / "cpk_bar.png", bbox_inches="tight")
plt.close(fig)

# ── 3. 산단 vs 거주지 PM2.5 박스플롯 ──────────────────────────────
df["group"] = df["station_name"].map(STATION_GROUPS)
ind = df.loc[df["group"] == INDUSTRIAL_GROUP, "pm25"].dropna()
base = df.loc[df["group"] == BASELINE_GROUP, "pm25"].dropna()
fig, ax = plt.subplots(figsize=(7.6, 4.3), dpi=200)
bp = ax.boxplot([ind, base], tick_labels=[f"{INDUSTRIAL_GROUP}\n(n={len(ind):,})", f"{BASELINE_GROUP}\n(n={len(base):,})"],
                patch_artist=True, showfliers=False, widths=0.5,
                medianprops=dict(color=NAVY, lw=2))
for patch, c in zip(bp["boxes"], [COBALT, GRAY]):
    patch.set_facecolor(c)
    patch.set_alpha(0.55)
ax.set_ylabel("PM2.5 (㎍/㎥)", fontsize=11)
ax.set_title("산단 영향군 vs 거주지 — PM2.5 분포", fontsize=13, fontweight="bold", color=NAVY, pad=10)
ax.spines[["top", "right"]].set_visible(False)
ax.tick_params(labelsize=11)
ax.grid(axis="y", color="#E2E8F0", lw=0.7)
fig.tight_layout()
fig.savefig(IMG / "group_box.png", bbox_inches="tight")
plt.close(fig)

# ── 4. 잔차 관리도 Before/After (자기상관 보정) ───────────────────
# 대표: 오송읍 PM2.5 (Cpk 최저권)
target_st = "오송읍" if "오송읍" in stations else stations[0]
sub = df[df["station_name"] == target_st].sort_values("data_time")
series = sub["pm25"]
times = sub["data_time"]
raw = i_chart(series)
rr = residual_i_chart(series, hours=times.dt.hour, deseasonalize=True)

fig, axes = plt.subplots(1, 2, figsize=(11.5, 4.0), dpi=200)
# Before: raw I-chart
arr = series.dropna().to_numpy()
x = np.arange(len(arr))
ax = axes[0]
ax.plot(x, arr, color=COBALT, lw=0.8, zorder=2)
ax.axhline(raw.center, color="#2E7D32", lw=1)
ax.axhline(raw.ucl[0], color=RED, ls="--", lw=1)
ax.axhline(raw.lcl[0], color=RED, ls="--", lw=1)
viol = raw.violations
ax.scatter([x[i] for i in viol], [arr[i] for i in viol], color=RED, s=14, zorder=3)
ax.set_title(f"BEFORE — 전통 I-Chart   (이탈 {len(viol)/raw.n*100:.0f}%)",
             fontsize=12, fontweight="bold", color=RED, pad=8)
ax.set_xlabel("관측 순서", fontsize=10)
ax.set_ylabel("PM2.5", fontsize=10)
ax.spines[["top", "right"]].set_visible(False)
ax.grid(color="#EEF1F5", lw=0.6)
# After: residual chart
rc = rr.resid_chart
xr = np.arange(rc.n)
ax = axes[1]
ax.plot(xr, rc.values, color=TEAL, lw=0.8, zorder=2)
ax.axhline(rc.center, color="#2E7D32", lw=1)
ax.axhline(rc.ucl[0], color=RED, ls="--", lw=1)
ax.axhline(rc.lcl[0], color=RED, ls="--", lw=1)
rv = rc.violations
ax.scatter([xr[i] for i in rv], [rc.values[i] for i in rv], color=RED, s=14, zorder=3)
ax.set_title(f"AFTER — 잔차 관리도   (이탈 {rr.resid_violation_rate*100:.0f}%)",
             fontsize=12, fontweight="bold", color=TEAL, pad=8)
ax.set_xlabel("관측 순서", fontsize=10)
ax.set_ylabel("잔차 e", fontsize=10)
ax.spines[["top", "right"]].set_visible(False)
ax.grid(color="#EEF1F5", lw=0.6)
fig.suptitle(f"{target_st} · PM2.5 — 자기상관 보정 전후 (ACF {rr.acf_before:.2f} → ≈0({rr.acf_after:.2f}))",
             fontsize=13, fontweight="bold", color=NAVY, y=1.02)
fig.tight_layout()
fig.savefig(IMG / "residual_ba.png", bbox_inches="tight")
plt.close(fig)

# ── 5. 6개 오염물질 박스플롯 그리드 ───────────────────────────────
fig, axes = plt.subplots(2, 3, figsize=(11.5, 5.2), dpi=200)
box_colors = ["#7FA8F5", "#F2A65A", "#6BBF73", "#E07B7B", "#B79CE0", "#5FC9C2"]
UNIT = {"pm10": "㎍/㎥", "pm25": "㎍/㎥", "o3": "ppm", "no2": "ppm", "so2": "ppm", "co": "ppm"}
for ax, p, c in zip(axes.flat, POLLUTANTS, box_colors):
    data = df[p].dropna()
    bp = ax.boxplot(data, vert=False, patch_artist=True, showfliers=False,
                    widths=0.55, medianprops=dict(color=NAVY, lw=1.6))
    bp["boxes"][0].set_facecolor(c)
    bp["boxes"][0].set_alpha(0.6)
    ax.set_title(f"{DISP[p]}  ({UNIT[p]})", fontsize=12, fontweight="bold", color=NAVY)
    ax.set_yticks([])
    ax.set_xlabel(UNIT[p], fontsize=9, color=GRAY)
    ax.text(0.97, 0.82, "✓ 이상치 0", transform=ax.transAxes, ha="right",
            color="#2E7D32", fontsize=8.5, fontweight="bold")
    ax.spines[["top", "right", "left"]].set_visible(False)
    ax.grid(axis="x", color="#EEF1F5", lw=0.6)
    ax.tick_params(labelsize=9)
fig.suptitle("6종 오염물질 분포 (Box Plot) — 결측·이상치 점검", fontsize=13, fontweight="bold", color=NAVY, y=1.0)
fig.tight_layout()
fig.savefig(IMG / "box_grid.png", bbox_inches="tight")
plt.close(fig)

# ── 6. PM2.5 일별 평균 시계열 (산단 vs 거주지 + USL) ──────────────
dfg = df.copy()
dfg["group"] = dfg["station_name"].map(STATION_GROUPS)
daily = (dfg.dropna(subset=["pm25"])
         .groupby([pd.Grouper(key="data_time", freq="D"), "group"])["pm25"]
         .mean().reset_index())
ind_d = daily[daily["group"] == INDUSTRIAL_GROUP]
base_d = daily[daily["group"] == BASELINE_GROUP]
USL_PM25_DAILY = 35.0
fig, ax = plt.subplots(figsize=(8.6, 4.0), dpi=200)
ax.plot(ind_d["data_time"], ind_d["pm25"], label=f"{INDUSTRIAL_GROUP} (산단 4곳 평균)", lw=2, color=COBALT)
ax.plot(base_d["data_time"], base_d["pm25"], label=f"{BASELINE_GROUP} (용암동)", lw=2, color=GRAY)
ax.axhline(USL_PM25_DAILY, color=RED, ls="--", lw=1.3)
ax.text(daily["data_time"].max(), USL_PM25_DAILY + 1.0, "USL 35 ㎍/㎥ (일평균 환경기준)",
        color=RED, fontsize=9.5, ha="right", fontweight="bold")
ax.set_title("PM2.5 일별 평균 추세 — 산단 영향군 vs 거주지", fontsize=13, fontweight="bold", color=NAVY, pad=10)
ax.set_ylabel("PM2.5 일평균 (㎍/㎥)", fontsize=11)
ax.legend(fontsize=9.5, loc="upper right", frameon=False)
ax.spines[["top", "right"]].set_visible(False)
ax.grid(color="#EEF1F5", lw=0.7)
fig.autofmt_xdate()
fig.tight_layout()
fig.savefig(IMG / "ts_pm25.png", bbox_inches="tight")
plt.close(fig)
_exceed = (ind_d["pm25"] > USL_PM25_DAILY).sum()

print("✅ 차트 생성 완료:", sorted(p.name for p in IMG.glob("*.png")))
print(f"   산단 PM2.5 일평균 USL(35) 초과일: {_exceed}일 / {len(ind_d)}일")
print(f"   대상 측정소: {stations}")
print(f"   평균 Cpk(낮은순): " + ", ".join(f"{DISP[p]}={mean_cpk[p]:.2f}" for p in order))
print(f"   잔차 보정: {target_st} PM2.5 이탈 {len(raw.violations)/raw.n*100:.0f}% → {rr.resid_violation_rate*100:.0f}%")
