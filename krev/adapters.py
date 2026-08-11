"""
Data adapters.

Two kinds live here:

1. ``make_synthetic`` — a self-contained generator used ONLY to prove the engine
   runs end-to-end and the maths is wired correctly. The numbers it produces are
   MEANINGLESS as market research: a known revision->return link and a mild
   Feb/May/Aug/Nov kicker are baked in on purpose so the pipeline has something
   to find. Never present synthetic output as a finding about Korea.

2. Real-source loaders. Prices/universe for KRX are free (pykrx /
   FinanceDataReader). Point-in-time consensus is NOT free — it comes from a
   vendor export (FnGuide DataGuide, WISEfn, QuantiWise, Refinitiv I/B/E/S,
   Bloomberg). ``load_consensus_csv`` maps such an export onto krev's schema.
   See docs/DATA_GUIDE.md.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import data_schema


# --------------------------------------------------------------------------- #
# 1. Synthetic generator (plumbing test only)                                 #
# --------------------------------------------------------------------------- #
def make_synthetic(
    n_tickers: int = 180,
    start: str = "2010-01-01",
    end: str = "2023-12-31",
    seed: int = 20260811,
    season_kicker: float = 0.004,
    signal_strength: float = 0.020,
):
    """Generate schema-conforming synthetic panels with a KNOWN embedded signal."""
    rng = np.random.default_rng(seed)
    month_ends = pd.date_range(start, end, freq="ME")
    tickers = [f"{100000+i:06d}" for i in range(n_tickers)]
    sectors = rng.choice(
        ["Semis", "Auto", "Bank", "Chem", "Health", "Retail", "IT", "Steel"],
        size=n_tickers,
    )
    list_dates = pd.to_datetime("2005-01-01") + pd.to_timedelta(
        rng.integers(0, 365 * 4, n_tickers), unit="D"
    )
    base_cap = rng.lognormal(mean=26, sigma=1.1, size=n_tickers)  # KRW

    # latent monthly "true revision" per ticker drives both the estimate path and
    # (with a lag) the realized return — that is the signal the engine must find.
    cons_rows, price_rows, meta_rows = [], [], []
    daily_index = pd.date_range(start, end, freq="B")

    # persistent AR(1) revision state
    rev_state = np.zeros(n_tickers)
    op_level = base_cap * rng.uniform(0.03, 0.09, n_tickers)
    np_level = op_level * rng.uniform(0.6, 0.85, n_tickers)
    eps_level = np_level / (base_cap / rng.uniform(5000, 50000, n_tickers))
    tp_level = (base_cap / rng.uniform(5000, 50000, n_tickers)) * rng.uniform(1.0, 1.4, n_tickers)
    px_level = tp_level / rng.uniform(1.0, 1.5, n_tickers)

    monthly_true_rev = {}  # (month_end, ticker) -> latent revision used for return
    fy_end_now = pd.Timestamp("2010-12-31")

    for me in month_ends:
        # fiscal roll each December -> FY1 fiscal-year-end advances
        fy1_end = pd.Timestamp(f"{me.year}-12-31")
        fy2_end = pd.Timestamp(f"{me.year+1}-12-31")
        rev_state = 0.6 * rev_state + rng.normal(0, 0.03, n_tickers)
        is_season = me.month in (2, 5, 8, 11)
        for i, t in enumerate(tickers):
            drift = rev_state[i] + (season_kicker if is_season else 0.0) * (rev_state[i] > 0)
            op_level[i] *= 1 + drift
            np_level[i] *= 1 + drift * 1.05
            eps_level[i] *= 1 + drift * 1.05
            tp_level[i] *= 1 + 0.5 * drift
            monthly_true_rev[(me, t)] = drift
            for fiscal, fye, mult in (("FY1", fy1_end, 1.0), ("FY2", fy2_end, 1.12)):
                n_est = rng.integers(3, 25)
                n_up = rng.binomial(n_est, min(0.9, max(0.05, 0.5 + 6 * drift)))
                cons_rows.append(
                    {
                        "asof": me, "ticker": t, "fiscal": fiscal, "fy_end": fye,
                        "op": op_level[i] * mult, "np_ctrl": np_level[i] * mult,
                        "eps": eps_level[i] * mult, "tp": tp_level[i],
                        "n_est": float(n_est), "n_up_1m": float(n_up),
                        "n_dn_1m": float(n_est - n_up),
                    }
                )
        meta_rows.extend(
            {
                "asof": me, "ticker": t, "name": f"SYN{t}",
                "market": "KOSPI" if i % 3 else "KOSDAQ", "sector": sectors[i],
                "list_date": list_dates[i], "is_pref": False, "is_spac": False,
                "is_reit": False, "is_admin": False, "is_halt": False,
                "shortable": bool(i % 7 != 0), "book_equity": base_cap[i] * 0.8,
                "ev": base_cap[i] * 1.1, "ebit_fwd": op_level[i],
            }
            for i, t in enumerate(tickers)
        )

    # daily prices: realized return = beta*mkt + signal*(lagged true rev) + noise
    mkt = rng.normal(0.0003, 0.011, len(daily_index))
    betas = rng.uniform(0.6, 1.4, n_tickers)
    me_of_day = pd.Series(daily_index, index=daily_index).dt.to_period("M").dt.to_timestamp("M")
    for i, t in enumerate(tickers):
        px = np.empty(len(daily_index))
        p = px_level[i]
        for d, day in enumerate(daily_index):
            me = me_of_day.iloc[d]
            # last month's signal predicts this month's return (no look-ahead)
            prev_me = (me.to_period("M") - 1).to_timestamp("M")
            tr = monthly_true_rev.get((prev_me, t), 0.0)
            mu = betas[i] * mkt[d] + signal_strength * tr + rng.normal(0, 0.016)
            p *= 1 + mu
            px[d] = p
        cap = base_cap[i] * (px / px_level[i])
        amount = cap * rng.uniform(0.001, 0.02, len(daily_index))
        price_rows.append(
            pd.DataFrame(
                {
                    "date": daily_index, "ticker": t, "close": px,
                    "ret": np.concatenate([[0.0], np.diff(px) / px[:-1]]),
                    "mktcap": cap, "amount": amount, "vwap": px * (1 + rng.normal(0, 0.002, len(px))),
                }
            )
        )

    consensus = data_schema.validate_consensus(pd.DataFrame(cons_rows))
    prices = data_schema.validate_prices(pd.concat(price_rows, ignore_index=True))
    meta = data_schema.validate_meta(pd.DataFrame(meta_rows))

    # benchmark = cap-weighted market proxy, monthly
    bench_daily = pd.Series(mkt, index=daily_index)
    bench_m = (1 + bench_daily).groupby(bench_daily.index.to_period("M")).prod() - 1
    bench_m.index = bench_m.index.to_timestamp("M")

    # simple synthetic earnings dates: quarterly reports
    ed = []
    for t in tickers:
        for yr in range(2010, 2024):
            for mth, day in ((2, 15), (5, 15), (8, 14), (11, 14)):
                ed.append({"ticker": t, "report_date": pd.Timestamp(f"{yr}-{mth:02d}-{day}"),
                           "fiscal_period": f"{yr}Q{(mth-2)//3+1}"})
    earnings_dates = pd.DataFrame(ed)

    return {
        "consensus": consensus, "prices": prices, "meta": meta,
        "bench_monthly": bench_m, "bench_daily": bench_daily,
        "earnings_dates": earnings_dates,
    }


# --------------------------------------------------------------------------- #
# 2. Real-source loaders                                                       #
# --------------------------------------------------------------------------- #
def load_prices_pykrx(start: str, end: str, tickers=None) -> pd.DataFrame:  # pragma: no cover
    """
    Build the `prices` panel from pykrx (free KRX data). Requires `pip install pykrx`
    and outbound access to KRX. Returns a schema-valid price frame.
    """
    from pykrx import stock  # noqa: WPS433

    if tickers is None:
        tickers = stock.get_market_ticker_list(end, market="ALL")
    frames = []
    for t in tickers:
        df = stock.get_market_ohlcv(start, end, t)
        cap = stock.get_market_cap(start, end, t)
        if df.empty:
            continue
        out = pd.DataFrame(
            {
                "date": df.index, "ticker": t, "close": df["종가"].astype(float),
                "ret": df["종가"].pct_change(),
                "mktcap": cap["시가총액"].reindex(df.index).astype(float),
                "amount": df["거래대금"].astype(float), "vwap": df["종가"].astype(float),
            }
        )
        frames.append(out)
    return data_schema.validate_prices(pd.concat(frames, ignore_index=True))


def load_consensus_csv(path: str, colmap: dict | None = None) -> pd.DataFrame:
    """
    Load a vendor consensus export (DataGuide / WISEfn / QuantiWise / I/B/E/S)
    already reshaped to long form, mapping its columns onto krev's schema.

    `colmap` maps krev column -> your column name. Missing optional columns
    (tp, n_est, n_up_1m, n_dn_1m) are filled with NaN by the schema validator.
    Critical requirement: rows must be POINT-IN-TIME snapshots (the value on the
    vendor's screen at `asof`), never a later restatement, and `fy_end` must be
    present so the annual roll can be handled.
    """
    df = pd.read_csv(path)
    if colmap:
        df = df.rename(columns={v: k for k, v in colmap.items()})
    return data_schema.validate_consensus(df)


def load_meta_csv(path: str, colmap: dict | None = None) -> pd.DataFrame:
    df = pd.read_csv(path)
    if colmap:
        df = df.rename(columns={v: k for k, v in colmap.items()})
    return data_schema.validate_meta(df)
