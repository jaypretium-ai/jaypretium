"""
Event-time analysis around earnings announcements.

Question: right after a company reports, do the analyst revisions that follow
actually predict the stock's subsequent excess return? We line each stock's
daily excess return up to its own report date and average, split by whether the
stock was a top-revision or bottom-revision name at the report, over windows
0-5, 6-20, 21-60 trading days after the announcement.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

WINDOWS = {"0-5d": (0, 5), "6-20d": (6, 20), "21-60d": (21, 60)}


def _cum_excess(px: pd.DataFrame, bench_daily: pd.Series, t0: pd.Timestamp,
                lo: int, hi: int) -> float:
    """Cumulative excess (stock-benchmark) return over [t0+lo, t0+hi] trading days."""
    dts = px.index[px.index >= t0]
    if len(dts) <= hi:
        return np.nan
    win = dts[lo : hi + 1]
    stock = (1 + px.loc[win, "ret"]).prod() - 1
    b = bench_daily.reindex(win).fillna(0.0)
    bench = (1 + b).prod() - 1
    return stock - bench


def event_study(
    earnings_dates: pd.DataFrame,      # ticker, report_date, fiscal_period
    prices: pd.DataFrame,              # date, ticker, ret
    bench_daily: pd.Series,            # daily benchmark returns, indexed by date
    revision_rank: pd.Series,          # (m, ticker) cross-sectional rank in [0,1]
    top_q: float = 0.2,
) -> pd.DataFrame:
    """
    For each earnings event, find the stock's most recent monthly revision rank,
    tag it top/bottom/mid, and compute post-event cumulative excess returns per
    window. Returns mean excess return by (rank_group, window).
    """
    px_by = {t: g.set_index("date").sort_index() for t, g in prices.groupby("ticker")}
    rank_by_month = {m: g.droplevel("m") for m, g in revision_rank.groupby(level="m")}
    months = sorted(rank_by_month)

    recs = []
    for _, ev in earnings_dates.iterrows():
        t, rd = str(ev["ticker"]), pd.Timestamp(ev["report_date"])
        if t not in px_by:
            continue
        # most recent monthly rank at or before the report
        prior = [m for m in months if m.to_timestamp("M") <= rd]
        if not prior:
            continue
        r = rank_by_month[prior[-1]].get(t, np.nan)
        if not np.isfinite(r):
            continue
        grp = "top" if r >= 1 - top_q else ("bottom" if r <= top_q else "mid")
        for wname, (lo, hi) in WINDOWS.items():
            xr = _cum_excess(px_by[t], bench_daily, rd, lo, hi)
            if np.isfinite(xr):
                recs.append({"group": grp, "window": wname, "xret": xr})
    if not recs:
        return pd.DataFrame()
    df = pd.DataFrame(recs)
    tab = df.groupby(["group", "window"])["xret"].agg(["mean", "median", "count"])
    return tab.reset_index()
