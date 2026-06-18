"""전체 기간 통계 계산.

평균/중앙값/표준편차/min/max/현재값/z-score/백분위 + 연도별 평균 테이블.
표시는 소수점 1자리(가짜 정밀도 금지). 내부 저장은 원 수치 유지.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats as sp


def summary(df: pd.DataFrame) -> dict:
    """할인율 전체 기간 요약 통계."""
    d = df["discount_pct"].to_numpy()
    mean = float(np.mean(d))
    std = float(np.std(d, ddof=1)) if len(d) > 1 else float("nan")
    current = float(d[-1])
    z = (current - mean) / std if std and not np.isnan(std) else float("nan")
    pct = float(sp.percentileofscore(d, current, kind="mean"))
    return {
        "n": int(len(d)),
        "start": df.index[0].date().isoformat(),
        "end": df.index[-1].date().isoformat(),
        "mean": mean,
        "median": float(np.median(d)),
        "std": std,
        "min": float(np.min(d)),
        "max": float(np.max(d)),
        "current": current,
        "current_z": z,
        "current_percentile": pct,
    }


def yearly_table(df: pd.DataFrame) -> pd.DataFrame:
    """연도별 평균/중앙값/표준편차/표본수."""
    g = df.groupby(df.index.year)["discount_pct"]
    tbl = pd.DataFrame(
        {
            "mean": g.mean(),
            "median": g.median(),
            "std": g.std(ddof=1),
            "min": g.min(),
            "max": g.max(),
            "n": g.size(),
        }
    )
    tbl.index.name = "year"
    return tbl


def print_summary(s: dict) -> None:
    print("\n=== 할인율(괴리율) 전체 기간 통계 ===")
    print(f"기간            : {s['start']} ~ {s['end']}  (거래일 {s['n']}일)")
    print(f"평균 / 중앙값   : {s['mean']:.1f}% / {s['median']:.1f}%")
    print(f"표준편차        : {s['std']:.1f}%p")
    print(f"최소 / 최대     : {s['min']:.1f}% / {s['max']:.1f}%")
    print(f"현재값          : {s['current']:.1f}%")
    print(f"현재 z-score    : {s['current_z']:.1f}  (양수=평소보다 할인 큼)")
    print(f"현재 백분위     : {s['current_percentile']:.1f} 퍼센타일")


def print_yearly(tbl: pd.DataFrame) -> None:
    print("\n=== 연도별 평균 할인율 ===")
    print(f"{'year':>6} {'mean':>7} {'median':>7} {'std':>6} {'min':>6} {'max':>6} {'n':>5}")
    for year, row in tbl.iterrows():
        print(
            f"{year:>6} {row['mean']:>6.1f}% {row['median']:>6.1f}% "
            f"{row['std']:>5.1f} {row['min']:>5.1f} {row['max']:>5.1f} {int(row['n']):>5}"
        )


def save_csvs(s: dict, tbl: pd.DataFrame, summary_path: str, yearly_path: str) -> None:
    pd.DataFrame([s]).to_csv(summary_path, index=False)
    tbl.round(4).to_csv(yearly_path)
    print(f"[stats] 요약 저장: {summary_path}")
    print(f"[stats] 연도별 저장: {yearly_path}")
