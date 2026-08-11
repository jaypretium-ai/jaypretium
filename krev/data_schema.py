"""
Point-in-time data schema and validation.

The whole study stands or falls on look-ahead bias. Every input here is
indexed by the date on which the information was *knowable in the market*,
never by the date it refers to. Consensus estimates in particular must be the
value that was on the vendor's screen at ``asof`` — not a later restatement.

Three long/tidy panels are required.

------------------------------------------------------------------ CONSENSUS
``consensus``  (one row per security per as-of month-end per fiscal target)
    asof        : Timestamp   month-end snapshot date (point-in-time)
    ticker      : str         security id (e.g. '005930')
    fiscal      : str         which forward year the estimate targets:
                              'FY1' (nearest not-yet-reported annual) or 'FY2'
    fy_end      : Timestamp   the fiscal-year-end that FY1/FY2 points to.
                              REQUIRED — it is what lets us detect the annual
                              roll (FY1 jumping to a new fiscal year) and avoid
                              the spurious "revision" that roll creates.
    op          : float       consensus operating profit (영업이익), KRW
    np_ctrl     : float       consensus net profit attributable to controlling
                              shareholders (지배주주순이익), KRW
    eps         : float       consensus EPS, KRW/share
    tp          : float       consensus target price, KRW/share (may be NaN)
    n_est       : float       number of estimates in the consensus (breadth
                              denominator; NaN if unavailable)
    n_up_1m     : float       # of analysts who revised UP in the last month
                              (breadth numerator; NaN if unavailable)
    n_dn_1m     : float       # of analysts who revised DOWN in the last month
                              (optional; NaN if unavailable)

--------------------------------------------------------------------- PRICES
``prices``  (one row per security per trading day)
    date        : Timestamp   trading date
    ticker      : str
    close       : float       adjusted close (총수익 기준이면 더 좋음)
    ret         : float       daily total return (if absent, computed from close)
    mktcap      : float       market cap, KRW (float or full; be consistent)
    amount      : float       daily traded value 거래대금, KRW (liquidity filter)
    vwap        : float       daily VWAP, KRW (optional; fallback = close)

---------------------------------------------------------------------- META
``meta``  (one row per security per as-of month-end — status can change)
    asof        : Timestamp   month-end snapshot date
    ticker      : str
    name        : str
    market      : str         'KOSPI' | 'KOSDAQ'
    sector      : str         GICS or WICS sector code/name (sector-neutral)
    list_date   : Timestamp   listing date (for the 12-month seasoning filter)
    is_pref     : bool        preferred share (우선주) -> excluded
    is_spac     : bool        SPAC -> excluded
    is_reit     : bool        REIT -> excluded
    is_admin    : bool        관리종목 (administrative issue) -> excluded
    is_halt     : bool        거래정지 (trading halt) -> excluded
    shortable   : bool        borrow available (대차 가능) for the short book
    book_equity : float       controlling-shareholder equity, KRW (for PBR)
    ev          : float       enterprise value, KRW (for EV/EBIT); NaN ok
    ebit_fwd    : float       forward EBIT consensus, KRW (for EV/EBIT); NaN ok

Also supply a benchmark total-return series (KOSPI and/or KOSPI200) as a
``pd.Series`` of monthly returns indexed by month-end, plus an optional
``earnings_dates`` frame (ticker, report_date, fiscal_period) for the
event-time study, and a risk-free monthly series for Sharpe.
"""
from __future__ import annotations

import pandas as pd

CONSENSUS_COLS = {
    "asof": "datetime64[ns]",
    "ticker": "object",
    "fiscal": "object",
    "fy_end": "datetime64[ns]",
    "op": "float64",
    "np_ctrl": "float64",
    "eps": "float64",
    "tp": "float64",
    "n_est": "float64",
    "n_up_1m": "float64",
    "n_dn_1m": "float64",
}

PRICE_COLS = {
    "date": "datetime64[ns]",
    "ticker": "object",
    "close": "float64",
    "ret": "float64",
    "mktcap": "float64",
    "amount": "float64",
    "vwap": "float64",
}

META_COLS = {
    "asof": "datetime64[ns]",
    "ticker": "object",
    "name": "object",
    "market": "object",
    "sector": "object",
    "list_date": "datetime64[ns]",
    "is_pref": "bool",
    "is_spac": "bool",
    "is_reit": "bool",
    "is_admin": "bool",
    "is_halt": "bool",
    "shortable": "bool",
    "book_equity": "float64",
    "ev": "float64",
    "ebit_fwd": "float64",
}

_REQUIRED = {
    "consensus": ["asof", "ticker", "fiscal", "fy_end", "op", "np_ctrl", "eps"],
    "prices": ["date", "ticker", "close", "mktcap", "amount"],
    "meta": ["asof", "ticker", "market", "sector", "list_date"],
}


class SchemaError(ValueError):
    """Raised when an input panel does not satisfy the required schema."""


def _check(df: pd.DataFrame, name: str) -> pd.DataFrame:
    if not isinstance(df, pd.DataFrame):
        raise SchemaError(f"{name}: expected a DataFrame, got {type(df)!r}")
    missing = [c for c in _REQUIRED[name] if c not in df.columns]
    if missing:
        raise SchemaError(f"{name}: missing required columns {missing}")
    return df


def validate_consensus(df: pd.DataFrame) -> pd.DataFrame:
    df = _check(df, "consensus").copy()
    df["asof"] = pd.to_datetime(df["asof"])
    df["fy_end"] = pd.to_datetime(df["fy_end"])
    df["ticker"] = df["ticker"].astype(str)
    for c in ("tp", "n_est", "n_up_1m", "n_dn_1m"):
        if c not in df.columns:
            df[c] = float("nan")
    bad = ~df["fiscal"].isin(["FY1", "FY2"])
    if bad.any():
        raise SchemaError(
            f"consensus.fiscal must be 'FY1' or 'FY2'; found {df.loc[bad,'fiscal'].unique()[:5]}"
        )
    dup = df.duplicated(["asof", "ticker", "fiscal"]).sum()
    if dup:
        raise SchemaError(f"consensus has {dup} duplicate (asof,ticker,fiscal) rows")
    return df.sort_values(["ticker", "fiscal", "asof"]).reset_index(drop=True)


def validate_prices(df: pd.DataFrame) -> pd.DataFrame:
    df = _check(df, "prices").copy()
    df["date"] = pd.to_datetime(df["date"])
    df["ticker"] = df["ticker"].astype(str)
    if "ret" not in df.columns:
        df["ret"] = (
            df.sort_values(["ticker", "date"])
            .groupby("ticker")["close"]
            .pct_change()
        )
    if "vwap" not in df.columns:
        df["vwap"] = df["close"]
    return df.sort_values(["ticker", "date"]).reset_index(drop=True)


def validate_meta(df: pd.DataFrame) -> pd.DataFrame:
    df = _check(df, "meta").copy()
    df["asof"] = pd.to_datetime(df["asof"])
    df["list_date"] = pd.to_datetime(df["list_date"])
    df["ticker"] = df["ticker"].astype(str)
    for c in ("is_pref", "is_spac", "is_reit", "is_admin", "is_halt"):
        if c not in df.columns:
            df[c] = False
        df[c] = df[c].fillna(False).astype(bool)
    if "shortable" not in df.columns:
        df["shortable"] = True
    df["shortable"] = df["shortable"].fillna(True).astype(bool)
    for c in ("book_equity", "ev", "ebit_fwd"):
        if c not in df.columns:
            df[c] = float("nan")
    if "name" not in df.columns:
        df["name"] = df["ticker"]
    return df.sort_values(["asof", "ticker"]).reset_index(drop=True)


def validate_all(consensus, prices, meta):
    """Validate and normalize all three panels together. Returns a tuple."""
    return validate_consensus(consensus), validate_prices(prices), validate_meta(meta)
