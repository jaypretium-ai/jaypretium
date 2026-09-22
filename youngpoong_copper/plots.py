"""시각화. ./output/ 에 PNG 저장.

원칙: 이중 y축(dual-axis) 사용 안 함. 수준 비교는 (1) 공통 기준일=100 인덱스 단일 축,
(2) 각자 축을 가진 소형 다중 패널(small multiples) 로 처리. YoY 는 같은 % 축에 겹친다.
"""

from __future__ import annotations

import os
import sys

import matplotlib
import pandas as pd

matplotlib.use("Agg")
import matplotlib.dates as mdates  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib import font_manager  # noqa: E402

# 팔레트 (dataviz 기본 검증 팔레트, light mode)
C_YP = "#2a78d6"     # series-1 blue  : 영풍
C_CU = "#eb6834"     # series-2 orange: 구리
SURFACE = "#fcfcfb"
TXT = "#0b0b0b"
TXT2 = "#52514e"
GRID = "#e6e5e1"


def set_font() -> bool:
    """한글 폰트가 있으면 사용, 없으면 영문 라벨로 폴백."""
    candidates = ["Malgun Gothic", "AppleGothic", "Apple SD Gothic Neo", "NanumGothic",
                  "Noto Sans CJK KR", "Noto Sans KR"]
    available = {f.name for f in font_manager.fontManager.ttflist}
    chosen = next((c for c in candidates if c in available), None)
    if chosen:
        plt.rcParams["font.family"] = chosen
    plt.rcParams["axes.unicode_minus"] = False
    return chosen is not None


def _style(ax, ylabel: str = "", pct: bool = False):
    ax.set_facecolor(SURFACE)
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    for sp in ("left", "bottom"):
        ax.spines[sp].set_color(GRID)
    ax.grid(True, axis="y", color=GRID, lw=0.8)
    ax.grid(False, axis="x")
    ax.tick_params(colors=TXT2, labelsize=9)
    ax.set_ylabel(ylabel, color=TXT2, fontsize=9)
    ax.xaxis.set_major_locator(mdates.MonthLocator(bymonth=(1, 4, 7, 10)))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%y-%m"))
    if pct:
        ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:+.0f}%"))


def _endlabel(ax, s: pd.Series, color: str, text: str):
    s = s.dropna()
    if s.empty:
        return
    ax.annotate(text, xy=(s.index[-1], s.iloc[-1]), xytext=(6, 0), textcoords="offset points",
                va="center", fontsize=9, color=TXT)
    ax.plot([s.index[-1]], [s.iloc[-1]], "o", ms=5, color=color, mec=SURFACE, mew=1.5)


def _line(ax, s: pd.Series, color: str, label: str, gaps=None, lw: float = 2.0,
          max_gap_days: int = 10):
    """하루이틀 결측(휴장·수집 누락)으로 선이 끊기지 않도록 관측치만 잇되, 긴 결측은 실제로 끊는다."""
    s = s.dropna()
    if s.empty:
        return
    # 관측 간격이 max_gap_days 를 넘는 곳(데이터 결측·YoY 기준값 결측)에서 선을 끊는다
    breaks = s.index.to_series().diff().dt.days > max_gap_days
    seg_id = breaks.cumsum()
    first = True
    for _, seg in s.groupby(seg_id):
        ax.plot(seg.index, seg.values, color=color, lw=lw, label=label if first else None)
        first = False


def _gap_shade(ax, gaps: list[tuple[str, str]]):
    for a, b in gaps:
        ax.axvspan(pd.Timestamp(a), pd.Timestamp(b), color="#000000", alpha=0.05, lw=0)


def _save(fig, outdir: str, name: str) -> str:
    path = os.path.join(outdir, name)
    fig.patch.set_facecolor(SURFACE)
    fig.tight_layout()
    fig.savefig(path, dpi=150, facecolor=SURFACE)
    plt.close(fig)
    return path


L = {  # 라벨 (한글 폰트 없으면 영문)
    True: dict(yp="영풍(000670) 종가", cu="구리 (USD/t)", idx="공통 시작일 = 100",
               t1="영풍 주가 vs 구리 가격 (인덱스, 시작=100)", t2="영풍 주가 / 구리 가격 (수준)",
               t3="영풍 주가 vs 구리 가격 YoY (%)", krw="원", gap="데이터 결측 구간",
               m="월말 기준", d="일별", yoy="전년동기 대비"),
    False: dict(yp="Youngpoong (000670) close", cu="Copper (USD/t)", idx="Index, first common date = 100",
                t1="Youngpoong vs Copper (indexed, start = 100)", t2="Youngpoong price / Copper price (levels)",
                t3="Youngpoong vs Copper, YoY change (%)", krw="KRW", gap="data gap",
                m="month-end", d="daily", yoy="year-over-year"),
}


def plot_indexed(df: pd.DataFrame, gaps, outdir: str, ko: bool) -> str:
    lab = L[ko]
    fig, ax = plt.subplots(figsize=(12, 5.2))
    _line(ax, df["yp"], C_YP, lab["yp"], gaps)
    _line(ax, df["cu"], C_CU, lab["cu"], gaps)
    ax.axhline(100, color=TXT2, lw=0.8, ls=":")
    _gap_shade(ax, gaps)
    _style(ax, lab["idx"])
    _endlabel(ax, df["yp"], C_YP, f"{df['yp'].dropna().iloc[-1]:.0f}")
    _endlabel(ax, df["cu"], C_CU, f"{df['cu'].dropna().iloc[-1]:.0f}")
    ax.set_title(lab["t1"], color=TXT, fontsize=12, loc="left")
    ax.legend(loc="upper left", frameon=False, fontsize=9)
    return _save(fig, outdir, "01_indexed_levels.png")


def plot_small_multiples(df: pd.DataFrame, gaps, outdir: str, ko: bool) -> str:
    lab = L[ko]
    fig, axes = plt.subplots(2, 1, figsize=(12, 7), sharex=True)
    for ax, col, color, name, unit in (
        (axes[0], "yp", C_YP, lab["yp"], lab["krw"]),
        (axes[1], "cu", C_CU, lab["cu"], "USD/t"),
    ):
        s = df[col]
        _line(ax, s, color, name, gaps, lw=1.8)
        _gap_shade(ax, gaps)
        _style(ax, unit)
        ax.set_title(name, color=TXT, fontsize=11, loc="left")
        ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:,.0f}"))
        _endlabel(ax, s, color, f"{s.dropna().iloc[-1]:,.0f}")
    fig.suptitle(lab["t2"], color=TXT, fontsize=12, x=0.01, ha="left")
    return _save(fig, outdir, "02_levels_small_multiples.png")


def plot_yoy(yo_d: pd.DataFrame, yo_m: pd.DataFrame, gaps, outdir: str, ko: bool) -> str:
    lab = L[ko]
    fig, axes = plt.subplots(2, 1, figsize=(12, 8), sharex=False)
    # (a) 일별 YoY
    ax = axes[0]
    _line(ax, yo_d["yp"], C_YP, lab["yp"], gaps, lw=1.6)
    _line(ax, yo_d["cu"], C_CU, lab["cu"], gaps, lw=1.6)
    ax.axhline(0, color=TXT2, lw=0.8)
    _gap_shade(ax, gaps)
    _style(ax, f"YoY % ({lab['d']})", pct=True)
    ax.set_title(f"{lab['t3']} - {lab['d']}", color=TXT, fontsize=11, loc="left")
    ax.legend(loc="upper left", frameon=False, fontsize=9)
    _endlabel(ax, yo_d["yp"], C_YP, f"{yo_d['yp'].dropna().iloc[-1]:+.0f}%")
    _endlabel(ax, yo_d["cu"], C_CU, f"{yo_d['cu'].dropna().iloc[-1]:+.0f}%")
    # (b) 월별 YoY 막대
    ax = axes[1]
    w = 12  # days
    x = yo_m.index
    ax.bar(x - pd.Timedelta(days=w / 2 + 1), yo_m["yp"], width=w, color=C_YP, label=lab["yp"],
           edgecolor=SURFACE, linewidth=1)
    ax.bar(x + pd.Timedelta(days=w / 2 + 1), yo_m["cu"], width=w, color=C_CU, label=lab["cu"],
           edgecolor=SURFACE, linewidth=1)
    ax.axhline(0, color=TXT2, lw=0.8)
    _style(ax, f"YoY % ({lab['m']})", pct=True)
    ax.set_title(f"{lab['t3']} - {lab['m']}", color=TXT, fontsize=11, loc="left")
    ax.legend(loc="upper left", frameon=False, fontsize=9)
    return _save(fig, outdir, "03_yoy.png")


def plot_scatter_yoy(yo_m: pd.DataFrame, outdir: str, ko: bool) -> str:
    lab = L[ko]
    d = yo_m.dropna()
    fig, ax = plt.subplots(figsize=(6.5, 6))
    ax.scatter(d["cu"], d["yp"], s=42, color=C_YP, edgecolor=SURFACE, linewidth=1.2, alpha=0.9)
    if len(d) > 3:
        import numpy as np
        b, a = np.polyfit(d["cu"], d["yp"], 1)
        xs = np.linspace(d["cu"].min(), d["cu"].max(), 20)
        ax.plot(xs, a + b * xs, color=TXT2, lw=1, ls="--")
        ax.text(0.02, 0.96, f"slope {b:.2f}, corr {d['cu'].corr(d['yp']):.2f}, n={len(d)}",
                transform=ax.transAxes, va="top", fontsize=9, color=TXT2)
    for t, r in d.iterrows():
        if abs(r["yp"]) > d["yp"].abs().quantile(0.85):
            ax.annotate(t.strftime("%y-%m"), (r["cu"], r["yp"]), xytext=(4, 3),
                        textcoords="offset points", fontsize=7, color=TXT2)
    ax.axhline(0, color=GRID, lw=0.8); ax.axvline(0, color=GRID, lw=0.8)
    ax.set_facecolor(SURFACE)
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    ax.tick_params(colors=TXT2, labelsize=9)
    ax.set_xlabel(f"{lab['cu']} YoY %", color=TXT2, fontsize=9)
    ax.set_ylabel(f"{lab['yp']} YoY %", color=TXT2, fontsize=9)
    ax.set_title(f"{lab['t3']} - {lab['m']}", color=TXT, fontsize=11, loc="left")
    return _save(fig, outdir, "04_yoy_scatter.png")


def make_all(daily: pd.DataFrame, indexed: pd.DataFrame, yo_d: pd.DataFrame, yo_m: pd.DataFrame,
             gaps, outdir: str) -> list[str]:
    ko = set_font()
    if not ko:
        print("[plots] 한글 폰트 없음 -> 영문 라벨 사용", file=sys.stderr)
    return [
        plot_indexed(indexed, gaps, outdir, ko),
        plot_small_multiples(daily, gaps, outdir, ko),
        plot_yoy(yo_d, yo_m, gaps, outdir, ko),
        plot_scatter_yoy(yo_m, outdir, ko),
    ]
