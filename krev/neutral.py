"""
Neutralization, valuation/momentum interactions, and cross-sectional regressions.

  * sector_neutralize / size_neutralize: demean a factor within sector or size
    bucket each month so the ranking is orthogonal to those exposures.
  * valuation_2x2: double-sort revision x cheapness.
  * fama_macbeth: month-by-month cross-sectional regressions of next-month return
    on revision + momentum + size + value + beta, then average the slopes with
    Newey-West standard errors — does revision survive the controls?
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import metrics


def demean_within(factor: pd.Series, group: pd.Series) -> pd.Series:
    """Cross-sectional demeaning of `factor` within `group` each month."""
    df = pd.DataFrame({"f": factor, "g": group}).dropna(subset=["f"])
    def _dm(x):
        return x - x.mean()
    return df.groupby([df.index.get_level_values("m"), "g"])["f"].transform(_dm)


def size_bucket(mktcap: pd.Series, n: int = 3, labels=("small", "mid", "large")) -> pd.Series:
    def _b(x):
        try:
            return pd.qcut(x, n, labels=labels)
        except ValueError:
            return pd.Series(index=x.index, dtype="object")
    return mktcap.groupby(level="m").transform(_b)


def valuation_2x2(
    revision: pd.Series,
    value: pd.Series,          # cheaper = better; pass e.g. -fwd_PER or E/P
    fwd_ret: pd.Series,
    rev_hi: float = 0.5,
    val_cheap: float = 0.5,
) -> pd.DataFrame:
    """
    2x2 double sort. Returns mean next-month return of each cell plus the
    'High-Revision & Cheap' minus 'Low-Revision & Expensive' spread.
    """
    df = pd.DataFrame({"rev": revision, "val": value, "r": fwd_ret}).dropna()
    def _tag(g):
        g = g.copy()
        g["rev_hi"] = g["rev"] >= g["rev"].quantile(1 - rev_hi)
        g["cheap"] = g["val"] >= g["val"].quantile(1 - val_cheap)
        return g
    df = df.groupby(level="m", group_keys=False).apply(_tag)
    df["cell"] = np.where(df["rev_hi"], "HighRev", "LowRev") + "_" + np.where(
        df["cheap"], "Cheap", "Expensive"
    )
    # equal-weight within cell each month, then time-average
    monthly = df.groupby([df.index.get_level_values("m"), "cell"])["r"].mean()
    cells = monthly.groupby(level=1).mean().rename("mean_monthly_ret")
    out = cells.to_frame()
    out["ann_ret"] = (1 + cells) ** 12 - 1
    return out


def cheap_revision_strategy(
    revision: pd.Series,
    value: pd.Series,          # higher = cheaper
    fwd_ret: pd.Series,
    rev_top_q: float = 0.2,
    val_cheap_half: float = 0.5,
) -> pd.Series:
    """'Top-20% revision, then keep the cheaper half' -> equal-weight monthly returns."""
    df = pd.DataFrame({"rev": revision, "val": value, "r": fwd_ret}).dropna()
    def _sel(g):
        top = g[g["rev"] >= g["rev"].quantile(1 - rev_top_q)]
        if top.empty:
            return pd.Series(dtype=float)
        cheap = top[top["val"] >= top["val"].quantile(1 - val_cheap_half)]
        return cheap["r"]
    return df.groupby(level="m", group_keys=True).apply(
        lambda g: _sel(g.droplevel("m")).mean()
    )


def fama_macbeth(
    panel: pd.DataFrame,       # index (m,ticker); cols include the regressors + 'fwd_ret'
    y: str,
    xs: list[str],
    nw_lags: int = 6,
) -> pd.DataFrame:
    """
    Cross-sectional regression each month; average slopes with NW t-stats.
    Regressors are cross-sectionally standardized within month for comparability.
    """
    d = panel.dropna(subset=[y] + xs).copy()
    for c in xs:
        d[c] = d.groupby(level="m")[c].transform(
            lambda x: (x - x.mean()) / x.std(ddof=0) if x.std(ddof=0) else x * 0
        )
    coefs = {c: [] for c in ["const"] + xs}
    idx = []
    for m, g in d.groupby(level="m"):
        if len(g) < len(xs) + 5:
            continue
        X = np.column_stack([np.ones(len(g))] + [g[c].values for c in xs])
        yv = g[y].values
        try:
            b, *_ = np.linalg.lstsq(X, yv, rcond=None)
        except np.linalg.LinAlgError:
            continue
        for i, c in enumerate(["const"] + xs):
            coefs[c].append(b[i])
        idx.append(m)
    rows = []
    for c in ["const"] + xs:
        s = pd.Series(coefs[c], index=idx)
        mu, t = metrics.newey_west_t(s, nw_lags)
        rows.append({"regressor": c, "avg_coef": mu, "NW_t": t, "n_months": len(s)})
    return pd.DataFrame(rows).set_index("regressor")


def rank01(factor: pd.Series) -> pd.Series:
    """Cross-sectional rank in [0,1] each month (for event-time grouping)."""
    return factor.groupby(level="m").transform(
        lambda x: x.rank(pct=True)
    )
