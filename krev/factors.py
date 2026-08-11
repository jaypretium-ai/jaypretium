"""
Factor construction.

The headache the brief calls out explicitly: FY1 changes discontinuously at the
annual roll. If on 2020-12-31 "FY1" means fiscal-2020 and on 2021-01-31 "FY1"
means fiscal-2021, then a naive current-FY1 / lagged-FY1 ratio compares two
*different* fiscal years and manufactures a revision that never happened.

We solve it by *within-fiscal-year linking*. Every consensus row carries
``fy_end``. We reshape into a per-(ticker, fy_end) time series, so the estimate
for a fixed fiscal year can be tracked across months regardless of whether the
vendor labelled it FY1 or FY2 at the time. A "1-month revision" then compares
the current FY1 fiscal year's estimate today vs. that *same fiscal year's*
estimate one month ago. No roll contamination, fully point-in-time.

We additionally provide:
  * blended forward  = w*FY1 + (1-w)*FY2               (config.fy1_blend_weight)
  * rolling-12m fwd  = FY1*(m/12) + FY2*(1-m/12), m=months to FY1 fiscal-end
  * winsorized ratios and cross-sectional z-scores (standardized revision)
  * revision breadth = n_up_1m / n_est
  * target-price disparity and TP 1m revision
  * a z-score composite  z(OP1M)+z(NP1M)+z(TP1M)
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .config import FactorConfig

_METRICS = ["op", "np_ctrl", "eps"]
_SHORT = {"op": "OP", "np_ctrl": "NP", "eps": "EPS"}


def _month_index(s: pd.Series) -> pd.Series:
    """Normalize an asof series to month-end period keys for aligned shifting."""
    return pd.to_datetime(s).dt.to_period("M")


def _fixed_fy_series(consensus: pd.DataFrame, metric: str) -> pd.DataFrame:
    """
    Wide table: index=(ticker, month), columns=fy_end, value=metric estimate.
    Lets us look up 'the fiscal-year-X estimate as of month m' for any m.
    """
    c = consensus[["ticker", "asof", "fy_end", metric]].copy()
    c["m"] = _month_index(c["asof"])
    # a fiscal year can appear as FY1 and later; keep the latest asof per month
    c = c.sort_values("asof").drop_duplicates(["ticker", "m", "fy_end"], keep="last")
    return c


def _lagged_same_fy(fixed: pd.DataFrame, metric: str, lag: int) -> pd.Series:
    """
    For each (ticker, month) return the estimate for that month's FY1 fiscal-year
    as it stood `lag` months earlier (same fiscal year — the roll-safe linkage).
    """
    fixed = fixed.copy()
    # current-month value keyed by the fiscal year it belongs to
    fixed["m_lag"] = fixed["m"] + lag
    left = fixed.rename(columns={metric: "cur"})[["ticker", "m", "fy_end", "cur"]]
    right = fixed.rename(columns={metric: "lag_val", "m": "m_src"})[
        ["ticker", "m_src", "fy_end", "lag_val"]
    ]
    # join current (ticker,m,fy_end) to the same fy_end `lag` months before
    left = left.assign(m_src=left["m"] - lag)
    merged = left.merge(right, on=["ticker", "fy_end", "m_src"], how="left")
    return merged.set_index(["ticker", "m", "fy_end"])["lag_val"]


def _fy1_map(consensus: pd.DataFrame) -> pd.DataFrame:
    """Which fy_end is FY1 at each (ticker, month), plus months-to-fiscal-end."""
    fy1 = consensus[consensus["fiscal"] == "FY1"].copy()
    fy1["m"] = _month_index(fy1["asof"])
    fy1 = fy1.sort_values("asof").drop_duplicates(["ticker", "m"], keep="last")
    mtd = (fy1["fy_end"].dt.to_period("M") - fy1["m"]).apply(
        lambda x: getattr(x, "n", np.nan)
    )
    fy1["months_to_fyend"] = mtd.clip(lower=0, upper=12)
    return fy1[["ticker", "m", "fy_end", "months_to_fyend"]]


def _fy2_end(consensus: pd.DataFrame) -> pd.DataFrame:
    fy2 = consensus[consensus["fiscal"] == "FY2"].copy()
    fy2["m"] = _month_index(fy2["asof"])
    fy2 = fy2.sort_values("asof").drop_duplicates(["ticker", "m"], keep="last")
    return fy2[["ticker", "m", "fy_end"]].rename(columns={"fy_end": "fy2_end"})


def _winsorize_xs(s: pd.Series, lo: float, hi: float) -> pd.Series:
    """Cross-sectional winsorize within each month (index level 'm')."""
    def _w(x):
        ql, qh = x.quantile(lo), x.quantile(hi)
        return x.clip(ql, qh)

    return s.groupby(level="m").transform(_w)


def _zscore_xs(s: pd.Series) -> pd.Series:
    def _z(x):
        mu, sd = x.mean(), x.std(ddof=0)
        return (x - mu) / sd if sd and np.isfinite(sd) else x * 0.0

    return s.groupby(level="m").transform(_z)


def build_factor_panel(
    consensus: pd.DataFrame,
    monthly_price: pd.DataFrame | None,
    cfg: FactorConfig,
) -> pd.DataFrame:
    """
    Returns a long factor panel indexed by (m, ticker) with one column per
    factor. `monthly_price` (columns: m, ticker, close) is only needed for the
    target-price disparity factor; pass None to skip it.
    """
    fy1 = _fy1_map(consensus)  # ticker,m,fy_end(=FY1),months_to_fyend
    key = fy1.set_index(["ticker", "m"])

    out = {}
    # ---- clean within-fiscal-year revisions for OP / NP / EPS ---------------
    for metric in _METRICS:
        fixed = _fixed_fy_series(consensus, metric)
        # current FY1 value
        cur = (
            fixed.merge(fy1[["ticker", "m", "fy_end"]], on=["ticker", "m", "fy_end"])
            .set_index(["ticker", "m", "fy_end"])[metric]
        )
        for lag in (1, 3):
            lagged = _lagged_same_fy(fixed, metric, lag)
            aligned = cur.to_frame("cur").join(lagged.to_frame("lag"))
            # revision ratio; guard against sign flips / near-zero denominators
            denom = aligned["lag"].abs()
            rev = np.where(
                (denom > 0) & np.isfinite(aligned["cur"]) & np.isfinite(aligned["lag"]),
                aligned["cur"] / aligned["lag"] - 1.0,
                np.nan,
            )
            s = pd.Series(rev, index=aligned.index).reset_index()
            s = s.set_index(["m", "ticker"])[0]
            out[f"{_SHORT[metric]}_{lag}M"] = s

    # ---- blended-forward & rolling-12m estimates & their revisions ----------
    fy2e = _fy2_end(consensus)
    for metric in _METRICS:
        fixed = _fixed_fy_series(consensus, metric)
        # FY1 & FY2 current values
        base = fy1.merge(fy2e, on=["ticker", "m"], how="left")
        v1 = fixed.rename(columns={metric: "v1"})[["ticker", "m", "fy_end", "v1"]]
        v2 = fixed.rename(columns={metric: "v2", "fy_end": "fy2_end"})[
            ["ticker", "m", "fy2_end", "v2"]
        ]
        base = base.merge(v1, on=["ticker", "m", "fy_end"], how="left")
        base = base.merge(v2, on=["ticker", "m", "fy2_end"], how="left")
        w = cfg.fy1_blend_weight
        base["blend"] = w * base["v1"] + (1 - w) * base["v2"]
        r = base["months_to_fyend"].fillna(6) / 12.0
        base["roll12"] = r * base["v1"] + (1 - r) * base["v2"]
        for kind in ("blend", "roll12"):
            ser = base.set_index(["ticker", "m"])[kind]
            for lag in (1, 3):
                lagged = ser.groupby(level="ticker").shift(lag)
                rev = np.where(
                    lagged.abs() > 0, ser / lagged - 1.0, np.nan
                )
                name = f"{_SHORT[metric]}{'BL' if kind=='blend' else 'R12'}_{lag}M"
                out[name] = pd.Series(rev, index=ser.index).swaplevel().sort_index()

    # ---- breadth ------------------------------------------------------------
    br = consensus[consensus["fiscal"] == "FY1"].copy()
    br["m"] = _month_index(br["asof"])
    br = br.sort_values("asof").drop_duplicates(["ticker", "m"], keep="last")
    denom = br["n_est"].replace(0, np.nan)
    br["BREADTH"] = br["n_up_1m"] / denom
    br["BREADTH_NET"] = (br["n_up_1m"] - br["n_dn_1m"].fillna(0)) / denom
    out["BREADTH"] = br.set_index(["m", "ticker"])["BREADTH"]
    out["BREADTH_NET"] = br.set_index(["m", "ticker"])["BREADTH_NET"]

    # ---- target price: disparity & 1m revision ------------------------------
    tp = consensus[consensus["fiscal"] == "FY1"].copy()
    tp["m"] = _month_index(tp["asof"])
    tp = tp.sort_values("asof").drop_duplicates(["ticker", "m"], keep="last")
    tp_ser = tp.set_index(["ticker", "m"])["tp"]
    for lag in (1, 3):
        lagged = tp_ser.groupby(level="ticker").shift(lag)
        rev = np.where(lagged.abs() > 0, tp_ser / lagged - 1.0, np.nan)
        out[f"TP_{lag}M"] = pd.Series(rev, index=tp_ser.index).swaplevel().sort_index()
    if monthly_price is not None:
        mp = monthly_price.rename(columns={"close": "px"})[["ticker", "m", "px"]]
        d = tp.merge(mp, on=["ticker", "m"], how="left")
        d["TP_DISPARITY"] = np.where(d["px"] > 0, d["tp"] / d["px"] - 1.0, np.nan)
        out["TP_DISPARITY"] = d.set_index(["m", "ticker"])["TP_DISPARITY"]

    panel = pd.DataFrame(out)
    panel.index.set_names(["m", "ticker"], inplace=True)

    # ---- winsorize + standardized (z) versions ------------------------------
    lo, hi = cfg.winsor
    raw_cols = list(panel.columns)
    for c in raw_cols:
        panel[c] = _winsorize_xs(panel[c], lo, hi)
    if cfg.standardize:
        for c in raw_cols:
            panel[f"z{c}"] = _zscore_xs(panel[c])
        # z-composite: earnings + TP revision, 1M horizon
        comp_parts = [f"z{k}" for k in ("OP_1M", "NP_1M", "TP_1M") if f"z{k}" in panel]
        if comp_parts:
            panel["COMPOSITE_z"] = panel[comp_parts].mean(axis=1)

    panel = panel.dropna(how="all")
    panel.attrs["fy1_key"] = key
    return panel


def factor_list(panel: pd.DataFrame) -> list[str]:
    """Names of usable factor columns (exclude helper index)."""
    return [c for c in panel.columns]
