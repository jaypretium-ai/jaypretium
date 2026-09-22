"""정렬·YoY·상관 계산."""

from __future__ import annotations

import numpy as np
import pandas as pd


def monthly(df: pd.DataFrame, tail_days: int = 7) -> pd.DataFrame:
    """월말 종가. 결측 월은 NaN 유지(ffill 하지 않음: gap 을 숨기지 않는다).

    마지막 관측치가 월말 기준 tail_days 이내가 아니면(월 중 데이터가 끊긴 경우) 그 달은 NaN 처리해
    부분 월(partial month)을 월말값으로 오인하지 않게 한다.
    """
    out = {}
    for col in df.columns:
        s = df[col].dropna()
        last = s.groupby(s.index.to_period("M")).tail(1)
        ok = (last.index.to_period("M").to_timestamp("M") - last.index).days <= tail_days
        ok[-1] = True  # 최신 월은 MTD(월중) 값 허용
        last = last[ok]
        last.index = last.index.to_period("M").to_timestamp("M")
        out[col] = last
    m = pd.DataFrame(out)
    full = pd.date_range(m.index.min(), m.index.max(), freq="ME")
    return m.reindex(full)


def yoy(s: pd.Series, periods: int) -> pd.Series:
    """전년동기 대비 %."""
    return (s / s.shift(periods) - 1.0) * 100.0


def daily_yoy(df: pd.DataFrame) -> pd.DataFrame:
    """일별 YoY: 각 날짜 t 에 대해 t-365d 이전 마지막 관측치 대비 (asof)."""
    out = {}
    for col in df.columns:
        s = df[col].dropna()
        prev_idx = s.index - pd.Timedelta(days=365)
        prev = s.reindex(prev_idx, method="ffill", tolerance=pd.Timedelta(days=10))
        prev.index = s.index
        out[col] = (s / prev - 1.0) * 100.0
    return pd.DataFrame(out)


def rebase(df: pd.DataFrame, base: float = 100.0) -> pd.DataFrame:
    """공통 시작점(첫 공통 관측일)=100 으로 인덱싱. 단일 축에 두 시계열을 겹칠 때 사용."""
    common = df.dropna()
    if common.empty:
        raise ValueError("공통 관측일이 없습니다")
    first = common.index[0]
    return df / df.loc[first] * base


def summary_stats(daily: pd.DataFrame, monthly_df: pd.DataFrame) -> dict:
    d = daily.dropna()
    m = monthly_df.dropna()
    ret_d = np.log(d).diff().dropna()
    ret_m = np.log(m).diff().dropna()
    yo = pd.DataFrame({c: yoy(m[c], 12) for c in m.columns}).dropna()
    out = {
        "n_daily": int(len(d)),
        "corr_daily_logret": float(ret_d["yp"].corr(ret_d["cu"])) if len(ret_d) > 10 else np.nan,
        "corr_monthly_logret": float(ret_m["yp"].corr(ret_m["cu"])) if len(ret_m) > 6 else np.nan,
        "corr_yoy": float(yo["yp"].corr(yo["cu"])) if len(yo) > 6 else np.nan,
        "beta_monthly": float(np.polyfit(ret_m["cu"], ret_m["yp"], 1)[0]) if len(ret_m) > 6 else np.nan,
    }
    for c in ("yp", "cu"):
        s = daily[c].dropna()
        out[f"{c}_last"] = float(s.iloc[-1])
        out[f"{c}_last_date"] = str(s.index[-1].date())
        # 1Y 전 asof
        prev = s.reindex([s.index[-1] - pd.Timedelta(days=365)], method="ffill",
                         tolerance=pd.Timedelta(days=10))
        out[f"{c}_yoy_pct"] = float((s.iloc[-1] / prev.iloc[0] - 1) * 100) if not prev.isna().all() else np.nan
        out[f"{c}_ytd_pct"] = float((s.iloc[-1] / s[s.index.year == s.index[-1].year].iloc[0] - 1) * 100)
        out[f"{c}_max"] = float(s.max()); out[f"{c}_max_date"] = str(s.idxmax().date())
        out[f"{c}_min"] = float(s.min()); out[f"{c}_min_date"] = str(s.idxmin().date())
    return out
