"""
Seasonality analysis: earnings-season months (Feb/May/Aug/Nov) vs the rest,
per-month breakdown, and the direct 1M-vs-3M season-month comparison the US
report hypothesizes.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import metrics


def by_calendar_month(r: pd.Series) -> pd.DataFrame:
    """Mean / median / win-rate / t-stat for each calendar month 1..12."""
    r = r.dropna()
    g = r.groupby(r.index.month)
    rows = []
    for mth in range(1, 13):
        x = g.get_group(mth) if mth in g.groups else pd.Series(dtype=float)
        mu, t = metrics.newey_west_t(x, lags=3) if len(x) else (np.nan, np.nan)
        rows.append(
            {
                "month": mth,
                "N": len(x),
                "mean": x.mean() if len(x) else np.nan,
                "median": x.median() if len(x) else np.nan,
                "win_rate": (x > 0).mean() if len(x) else np.nan,
                "t_stat": t,
            }
        )
    return pd.DataFrame(rows).set_index("month")


def season_vs_other(
    r: pd.Series,
    season_months=(2, 5, 8, 11),
    n_boot: int = 5000,
    seed: int = 0,
) -> dict:
    """Compare season-month returns against the other-month returns."""
    r = r.dropna()
    is_season = r.index.month.isin(season_months)
    s, o = r[is_season], r[~is_season]

    def _blk(x):
        mu, t = metrics.newey_west_t(x, lags=3) if len(x) else (np.nan, np.nan)
        return {
            "N": len(x),
            "mean": x.mean() if len(x) else np.nan,
            "median": x.median() if len(x) else np.nan,
            "win_rate": (x > 0).mean() if len(x) else np.nan,
            "IR": metrics.sharpe(x) if len(x) else np.nan,
            "t_stat": t,
            "MaxDD": metrics.max_drawdown(x) if len(x) else np.nan,
        }

    diff = (s.mean() if len(s) else np.nan) - (o.mean() if len(o) else np.nan)
    # bootstrap CI for the season-minus-other mean difference
    rng = np.random.default_rng(seed)
    sv, ov = s.values, o.values
    if len(sv) >= 3 and len(ov) >= 3:
        boot = np.array(
            [
                rng.choice(sv, len(sv)).mean() - rng.choice(ov, len(ov)).mean()
                for _ in range(n_boot)
            ]
        )
        ci = (float(np.quantile(boot, 0.025)), float(np.quantile(boot, 0.975)))
        p_gt0 = float((boot > 0).mean())
    else:
        ci, p_gt0 = (np.nan, np.nan), np.nan
    return {
        "season": _blk(s),
        "other": _blk(o),
        "season_minus_other": diff,
        "boot_ci95": ci,
        "boot_p_diff_gt_0": p_gt0,
    }


def per_season_month(r: pd.Series, season_months=(2, 5, 8, 11)) -> pd.DataFrame:
    """Break the season effect out by each individual season month."""
    r = r.dropna()
    rows = []
    for mth in season_months:
        x = r[r.index.month == mth]
        mu, t = metrics.newey_west_t(x, lags=2) if len(x) else (np.nan, np.nan)
        rows.append(
            {
                "month": mth,
                "N": len(x),
                "mean": x.mean() if len(x) else np.nan,
                "win_rate": (x > 0).mean() if len(x) else np.nan,
                "t_stat": t,
            }
        )
    return pd.DataFrame(rows).set_index("month")


def compare_horizons_in_season(
    series_by_factor: dict[str, pd.Series],
    pairs=(("OP_1M", "OP_3M"), ("NP_1M", "NP_3M"), ("EPS_1M", "EPS_3M")),
    season_months=(2, 5, 8, 11),
) -> pd.DataFrame:
    """
    Direct 1M-vs-3M test *within season months* — the core US hypothesis:
    is the freshest 1-month revision stronger right after earnings season than
    the 3-month cumulative revision?
    """
    rows = []
    for a, b in pairs:
        if a not in series_by_factor or b not in series_by_factor:
            continue
        ra, rb = series_by_factor[a].dropna(), series_by_factor[b].dropna()
        sa = ra[ra.index.month.isin(season_months)]
        sb = rb[rb.index.month.isin(season_months)]
        mua, ta = metrics.newey_west_t(sa, 2)
        mub, tb = metrics.newey_west_t(sb, 2)
        rows.append(
            {
                "pair": f"{a} vs {b}",
                "1M_mean": mua,
                "1M_t": ta,
                "3M_mean": mub,
                "3M_t": tb,
                "1M_minus_3M": mua - mub,
                "winner": a if mua > mub else b,
            }
        )
    return pd.DataFrame(rows)
