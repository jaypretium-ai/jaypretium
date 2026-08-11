"""Performance statistics for monthly return series."""
from __future__ import annotations

import numpy as np
import pandas as pd

_MONTHS = 12


def _ann_factor(freq_per_year: int = _MONTHS) -> int:
    return freq_per_year


def cagr(r: pd.Series) -> float:
    r = r.dropna()
    if r.empty:
        return np.nan
    growth = (1 + r).prod()
    years = len(r) / _MONTHS
    return growth ** (1 / years) - 1 if years > 0 and growth > 0 else np.nan


def ann_vol(r: pd.Series) -> float:
    return r.dropna().std(ddof=1) * np.sqrt(_MONTHS)


def sharpe(r: pd.Series, rf: pd.Series | float = 0.0) -> float:
    r = r.dropna()
    ex = r - (rf.reindex(r.index) if isinstance(rf, pd.Series) else rf)
    sd = ex.std(ddof=1)
    return ex.mean() / sd * np.sqrt(_MONTHS) if sd else np.nan


def downside_vol(r: pd.Series, mar: float = 0.0) -> float:
    r = r.dropna()
    d = np.minimum(r - mar, 0.0)
    return np.sqrt((d**2).mean()) * np.sqrt(_MONTHS)


def sortino(r: pd.Series, rf: pd.Series | float = 0.0, mar: float = 0.0) -> float:
    r = r.dropna()
    ex = r - (rf.reindex(r.index) if isinstance(rf, pd.Series) else rf)
    dv = downside_vol(r, mar)
    return ex.mean() * _MONTHS / dv if dv else np.nan


def max_drawdown(r: pd.Series) -> float:
    r = r.dropna()
    if r.empty:
        return np.nan
    eq = (1 + r).cumprod()
    return (eq / eq.cummax() - 1).min()


def information_ratio(r: pd.Series, bench: pd.Series) -> float:
    a = (r - bench.reindex(r.index)).dropna()
    sd = a.std(ddof=1)
    return a.mean() / sd * np.sqrt(_MONTHS) if sd else np.nan


def hit_ratio(r: pd.Series) -> float:
    r = r.dropna()
    return (r > 0).mean() if len(r) else np.nan


def beta(r: pd.Series, bench: pd.Series) -> float:
    df = pd.concat([r, bench], axis=1).dropna()
    if len(df) < 3:
        return np.nan
    cov = np.cov(df.iloc[:, 0], df.iloc[:, 1])
    return cov[0, 1] / cov[1, 1] if cov[1, 1] else np.nan


def newey_west_t(r: pd.Series, lags: int = 6) -> tuple[float, float]:
    """Mean and Newey-West (HAC) t-stat of a monthly series' mean."""
    x = r.dropna().values
    n = len(x)
    if n < 3:
        return (np.nanmean(x) if n else np.nan, np.nan)
    mu = x.mean()
    e = x - mu
    gamma0 = (e @ e) / n
    var = gamma0
    for L in range(1, min(lags, n - 1) + 1):
        w = 1 - L / (lags + 1)
        cov = (e[L:] @ e[:-L]) / n
        var += 2 * w * cov
    se = np.sqrt(var / n)
    return mu, (mu / se if se > 0 else np.nan)


def bootstrap_ci(
    r: pd.Series, stat=np.mean, n_boot: int = 5000, alpha: float = 0.05, seed: int = 0
) -> tuple[float, float]:
    """Percentile bootstrap CI for a statistic of a return series."""
    x = r.dropna().values
    if len(x) < 3:
        return (np.nan, np.nan)
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(x), size=(n_boot, len(x)))
    stats = np.array([stat(x[i]) for i in idx])
    return (
        float(np.quantile(stats, alpha / 2)),
        float(np.quantile(stats, 1 - alpha / 2)),
    )


def summary(
    r: pd.Series,
    bench: pd.Series | None = None,
    rf: pd.Series | float = 0.0,
    turnover: float | None = None,
    nw_lags: int = 6,
) -> dict:
    """Full performance dashboard for one monthly return series."""
    r = r.dropna()
    mu, tstat = newey_west_t(r, nw_lags)
    d = {
        "N_months": int(len(r)),
        "CAGR": cagr(r),
        "AnnVol": ann_vol(r),
        "Sharpe": sharpe(r, rf),
        "Sortino": sortino(r, rf),
        "MaxDD": max_drawdown(r),
        "HitRatio": hit_ratio(r),
        "MonthlyWinRate": hit_ratio(r),
        "AvgMonthly": r.mean(),
        "MedMonthly": r.median(),
        "DownsideVol": downside_vol(r),
        "WorstMonth": r.min() if len(r) else np.nan,
        "BestMonth": r.max() if len(r) else np.nan,
        "NW_tstat": tstat,
    }
    if bench is not None:
        d["IR"] = information_ratio(r, bench)
        d["Beta"] = beta(r, bench)
    if turnover is not None:
        d["Turnover"] = turnover
        d["AvgHoldingMonths"] = (1.0 / turnover) if turnover else np.nan
    return d
