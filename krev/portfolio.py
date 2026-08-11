"""
Portfolio construction and cost accounting.

Timing convention (look-ahead-free):
  * Factor is measured at the close of signal month ``m``.
  * We hold the resulting book through month ``m+1`` and book that month's
    return. ``fwd_ret[(m, ticker)]`` therefore means "the return earned during
    the month AFTER signal month m". At monthly resolution this already imposes
    the >=1 trading-day lag; the intra-month exec price/lag knobs (config) refine
    the fill but never let month-m information touch a month-m return.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .config import PortfolioConfig


def _leg_weights(sub: pd.DataFrame, weighting: str) -> pd.Series:
    if weighting == "mktcap" and sub["mktcap"].notna().any():
        w = sub["mktcap"].clip(lower=0).fillna(0.0)
        if w.sum() > 0:
            return w / w.sum()
    n = len(sub)
    return pd.Series(1.0 / n, index=sub.index) if n else pd.Series(dtype=float)


def build_book(
    factor: pd.Series,
    elig: pd.Series,
    mktcap: pd.Series,
    quantile: float,
    weighting: str,
    shortable: pd.Series | None = None,
    short_realistic: bool = False,
) -> pd.DataFrame:
    """
    For each month, assign long/short weights. Returns a long frame with columns
    [m, ticker, w_long, w_short]. Long = top `quantile` by factor, short = bottom.
    If short_realistic, drop non-shortable names from the short leg and renormalize.
    """
    df = pd.DataFrame({"f": factor}).join(pd.DataFrame({"elig": elig})).join(
        pd.DataFrame({"mktcap": mktcap})
    )
    if shortable is not None:
        df = df.join(pd.DataFrame({"shortable": shortable}))
    df = df[df["elig"].fillna(False)]
    df = df[df["f"].notna()]
    rows = []
    for m, g in df.groupby(level="m"):
        g = g.droplevel("m")
        n = len(g)
        if n < 5:
            continue
        k = max(1, int(np.floor(n * quantile)))
        order = g["f"].rank(method="first", ascending=False)
        longs = g[order <= k]
        shorts = g[order > n - k]
        if short_realistic and "shortable" in g.columns:
            shorts = shorts[shorts["shortable"].fillna(False)]
        wl = _leg_weights(longs, weighting)
        ws = _leg_weights(shorts, weighting)
        for t, w in wl.items():
            rows.append((m, t, w, 0.0))
        for t, w in ws.items():
            rows.append((m, t, 0.0, w))
    book = pd.DataFrame(rows, columns=["m", "ticker", "w_long", "w_short"])
    return book.set_index(["m", "ticker"])


def _turnover(book: pd.DataFrame, col: str) -> pd.Series:
    """One-sided traded fraction per rebalance for leg weight column `col`."""
    w = book[col].unstack("ticker").fillna(0.0).sort_index()
    dw = w.diff().abs().sum(axis=1)
    dw.iloc[0] = w.iloc[0].abs().sum()  # initial build
    return dw  # fraction of notional traded that month


def run_book(
    book: pd.DataFrame,
    fwd_ret: pd.Series,
    long_cost_bps: float = 0.0,
    short_extra_bps: float = 0.0,
    borrow_annual: float = 0.0,
) -> pd.DataFrame:
    """
    Turn a weight book into monthly return series (gross and net of costs).

    Returns a frame indexed by month with columns:
        long_gross, short_gross, ls_gross,
        long_net,   short_net,   ls_net,
        long_to, short_to  (turnover, one-sided fraction)
    """
    fr = fwd_ret.rename("r")
    j = book.join(fr, how="left")
    j["r"] = j["r"].fillna(0.0)
    grp = j.groupby(level="m")
    long_gross = grp.apply(lambda x: (x["w_long"] * x["r"]).sum())
    short_gross = grp.apply(lambda x: (x["w_short"] * x["r"]).sum())

    long_to = _turnover(book, "w_long")
    short_to = _turnover(book, "w_short")

    # costs: bps on traded notional each rebalance
    lc = long_cost_bps / 1e4
    sc = (long_cost_bps + short_extra_bps) / 1e4
    borrow_m = (1 + borrow_annual) ** (1 / 12) - 1
    short_gross_exposure = book["w_short"].groupby(level="m").sum()

    long_net = long_gross - long_to.reindex(long_gross.index).fillna(0) * lc
    short_cost = short_to.reindex(short_gross.index).fillna(0) * sc
    short_borrow = short_gross_exposure.reindex(short_gross.index).fillna(0) * borrow_m
    # short leg P&L to the L/S book = -(stock return) - costs - borrow
    short_net_contrib = -short_gross - short_cost - short_borrow
    ls_gross = long_gross - short_gross
    ls_net = long_net + short_net_contrib

    out = pd.DataFrame(
        {
            "long_gross": long_gross,
            "short_gross": short_gross,
            "ls_gross": ls_gross,
            "long_net": long_net,
            "short_net": short_net_contrib,
            "ls_net": ls_net,
            "long_to": long_to,
            "short_to": short_to,
        }
    ).sort_index()
    return out
