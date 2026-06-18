"""시각화. ./output/ 에 PNG 저장. 한글 폰트 자동 감지."""

from __future__ import annotations

import os
import sys

import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")  # 헤드리스 환경 대응
import matplotlib.pyplot as plt
from matplotlib import font_manager


def set_korean_font() -> str:
    """Malgun Gothic/AppleGothic 등 한글 폰트 자동 감지·설정. 마이너스 깨짐 방지."""
    candidates = [
        "Malgun Gothic",      # Windows
        "AppleGothic",        # macOS
        "Apple SD Gothic Neo",
        "NanumGothic",        # Linux(나눔)
        "Noto Sans CJK KR",
        "Noto Sans KR",
    ]
    available = {f.name for f in font_manager.fontManager.ttflist}
    chosen = next((c for c in candidates if c in available), None)
    if chosen:
        plt.rcParams["font.family"] = chosen
    else:
        print(
            "[plots][경고] 한글 폰트를 찾지 못했습니다. 라벨이 깨질 수 있습니다 "
            "(NanumGothic 설치 권장).",
            file=sys.stderr,
        )
    plt.rcParams["axes.unicode_minus"] = False
    return chosen or "default"


def _lab(w: int) -> str:
    return {21: "1M", 63: "3M", 126: "6M", 252: "12M"}.get(w, f"{w}d")


def plot_discount_trend(df: pd.DataFrame, mean: float, outdir: str,
                        threshold_band: int = 30) -> str:
    fig, ax = plt.subplots(figsize=(12, 5))
    ax.plot(df.index, df["discount_pct"], lw=0.8, color="#1f4e79", label="할인율(%)")
    ax.axhline(mean, ls="--", color="gray", lw=1.2, label=f"평균 {mean:.1f}%")
    ax.axhspan(threshold_band, df["discount_pct"].max() + 2, color="orange",
               alpha=0.12, label=f"임계값 {threshold_band}% 이상")
    ax.set_title("삼성전자 보통주 대비 우선주 할인율(괴리율) 장기 추이")
    ax.set_ylabel("할인율 (%)")
    ax.set_xlabel("날짜")
    ax.legend(loc="upper right", fontsize=9)
    ax.grid(True, alpha=0.3)
    path = os.path.join(outdir, "01_discount_trend.png")
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)
    return path


def plot_rel_return_boxplots(trades: pd.DataFrame, thresholds: list[int],
                             windows: list[int], outdir: str) -> str:
    """버킷별 forward 상대수익률 분포 boxplot. 윈도우별 subplot, x축=임계값 버킷."""
    n = len(windows)
    fig, axes = plt.subplots(1, n, figsize=(4.2 * n, 5), sharey=True)
    if n == 1:
        axes = [axes]
    for ax, w in zip(axes, windows):
        data, labels, counts = [], [], []
        for thr in thresholds:
            vals = trades[(trades["window"] == w) & (trades["threshold"] == thr)]["rel_ret"]
            data.append(vals.to_numpy() * 100 if len(vals) else np.array([np.nan]))
            labels.append(f"{thr}%")
            counts.append(len(vals))
        ax.boxplot(data, tick_labels=labels, showmeans=True)
        ax.axhline(0, color="red", lw=0.8, ls=":")
        ax.set_title(f"{_lab(w)} 보유")
        ax.set_xlabel("진입 임계 할인율")
        ax.grid(True, axis="y", alpha=0.3)
        # 표본수 주석
        for i, c in enumerate(counts, start=1):
            ax.annotate(f"n={c}", (i, ax.get_ylim()[0]), ha="center", va="bottom",
                        fontsize=8, color="gray")
    axes[0].set_ylabel("상대수익률 (우선주-보통주, %)")
    fig.suptitle("버킷별 forward 상대수익률 분포 (overlapping 표본 — 참고용)", y=1.02)
    path = os.path.join(outdir, "02_rel_return_boxplot.png")
    fig.tight_layout()
    fig.savefig(path, dpi=130, bbox_inches="tight")
    plt.close(fig)
    return path


def plot_entry_vs_6m_scatter(trades: pd.DataFrame, outdir: str,
                             window: int = 126) -> str:
    """진입 시 할인율 vs 보유기간 후 상대수익률 산점도 (상관 눈으로 확인)."""
    sub = trades[trades["window"] == window]
    fig, ax = plt.subplots(figsize=(8, 6))
    if sub.empty:
        ax.text(0.5, 0.5, f"{_lab(window)} 표본 없음", ha="center", va="center")
    else:
        x = sub["entry_discount"].to_numpy()
        y = sub["rel_ret"].to_numpy() * 100
        ax.scatter(x, y, s=10, alpha=0.35, color="#2e7d32", edgecolors="none")
        ax.axhline(0, color="red", lw=0.8, ls=":")
        if len(x) > 2 and np.std(x) > 0:
            r = float(np.corrcoef(x, y)[0, 1])
            b, a = np.polyfit(x, y, 1)
            xs = np.linspace(x.min(), x.max(), 50)
            ax.plot(xs, a + b * xs, color="black", lw=1.2,
                    label=f"추세선 (Pearson r={r:.1f})")
            ax.legend(loc="upper right", fontsize=9)
    ax.set_title(f"진입 할인율 vs {_lab(window)} 후 상대수익률")
    ax.set_xlabel("진입 시 할인율 (%)")
    ax.set_ylabel("상대수익률 (우선주-보통주, %)")
    ax.grid(True, alpha=0.3)
    path = os.path.join(outdir, "03_entry_vs_6m_scatter.png")
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)
    return path


def make_all(df: pd.DataFrame, trades: pd.DataFrame, mean: float,
             thresholds: list[int], windows: list[int], outdir: str) -> list[str]:
    set_korean_font()
    os.makedirs(outdir, exist_ok=True)
    paths = [
        plot_discount_trend(df, mean, outdir),
        plot_rel_return_boxplots(trades, thresholds, windows, outdir),
    ]
    scatter_win = 126 if 126 in windows else windows[len(windows) // 2]
    paths.append(plot_entry_vs_6m_scatter(trades, outdir, scatter_win))
    for p in paths:
        print(f"[plots] 저장: {p}")
    return paths
