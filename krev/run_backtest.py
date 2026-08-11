"""
End-to-end backtest driver.

Given the three validated panels + a benchmark, produces the full result set:
per-factor performance (long-only / long-excess / long-short, gross & net),
seasonality, the 1M-vs-3M season test, sub-period robustness, valuation and
momentum interactions, Fama-MacBeth, and (if earnings dates given) event-time.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import data_schema, factors, portfolio, metrics, seasonality, neutral, eventtime
from .config import BacktestConfig


def _to_month(ts) -> pd.Period:
    return pd.to_datetime(ts).to_period("M")


def build_monthly_price(prices: pd.DataFrame, liq_lookback: int) -> pd.DataFrame:
    """Month-end close/mktcap + trailing avg traded value; keyed by (ticker, m)."""
    p = prices.copy()
    p["m"] = p["date"].dt.to_period("M")
    p["amt_roll"] = (
        p.groupby("ticker")["amount"]
        .transform(lambda s: s.rolling(liq_lookback, min_periods=liq_lookback // 2).mean())
    )
    last = p.sort_values("date").groupby(["ticker", "m"]).tail(1)
    mp = last[["ticker", "m", "close", "mktcap", "amt_roll"]].reset_index(drop=True)
    return mp


def forward_returns(monthly_price: pd.DataFrame) -> pd.Series:
    """fwd_ret[(m,ticker)] = return over the month AFTER signal month m."""
    mp = monthly_price.sort_values(["ticker", "m"]).copy()
    mp["close_next"] = mp.groupby("ticker")["close"].shift(-1)
    mp["fwd"] = mp["close_next"] / mp["close"] - 1
    return mp.set_index(["m", "ticker"])["fwd"]


def eligibility(
    monthly_price: pd.DataFrame, meta: pd.DataFrame, cfg: BacktestConfig
) -> pd.Series:
    """Boolean (m, ticker) mask implementing every universe filter in the brief."""
    u = cfg.universe
    meta = meta.copy()
    meta["m"] = meta["asof"].dt.to_period("M")
    mp = monthly_price.merge(
        meta[
            ["m", "ticker", "market", "list_date", "is_pref", "is_spac",
             "is_reit", "is_admin", "is_halt"]
        ],
        on=["m", "ticker"], how="left",
    )
    ok = pd.Series(True, index=mp.index)
    for c in ("is_pref", "is_spac", "is_reit", "is_admin", "is_halt"):
        ok &= ~mp[c].fillna(False)
    # seasoning: >= min_listing_months since listing
    months_listed = (
        mp["m"].dt.to_timestamp("M") - mp["list_date"]
    ).dt.days / 30.44
    ok &= months_listed >= u.min_listing_months
    # liquidity: drop illiquid tail within each month
    if u.illiquid_drop_pct and u.illiquid_drop_pct > 0:
        thr = mp.groupby("m")["amt_roll"].transform(
            lambda x: x.quantile(u.illiquid_drop_pct)
        )
        ok &= mp["amt_roll"] >= thr
    if u.mktcap_floor:
        ok &= mp["mktcap"] >= u.mktcap_floor
    # universe definition
    if u.definition == "TOP500":
        n = u.top_n_by_mktcap or 500
        rank = mp.groupby("m")["mktcap"].rank(ascending=False, method="first")
        ok &= rank <= n
    elif u.definition == "KOSPI200":
        kospi = mp["market"].eq("KOSPI")
        rank = mp[kospi].groupby("m")["mktcap"].rank(ascending=False, method="first")
        r = pd.Series(np.inf, index=mp.index)
        r.loc[rank.index] = rank
        ok &= kospi & (r <= 200)
    mp["ok"] = ok.values
    return mp.set_index(["m", "ticker"])["ok"]


def _aux_factors(consensus, monthly_price):
    """Momentum (12-1), value (E/P from FY1 EPS), size — for regressions/interactions."""
    mp = monthly_price.sort_values(["ticker", "m"]).copy()
    mp["ret_m"] = mp.groupby("ticker")["close"].pct_change()
    # 12-1 momentum: cumulative return from m-12 to m-1
    logret = np.log1p(mp["ret_m"].fillna(0))
    mom = (
        mp.assign(lr=logret)
        .groupby("ticker")["lr"]
        .transform(lambda s: s.shift(1).rolling(11, min_periods=6).sum())
    )
    mp["MOM"] = np.expm1(mom)
    mp["SIZE"] = np.log(mp["mktcap"])
    fy1 = consensus[consensus["fiscal"] == "FY1"].copy()
    fy1["m"] = fy1["asof"].dt.to_period("M")
    fy1 = fy1.sort_values("asof").drop_duplicates(["ticker", "m"], keep="last")
    val = mp.merge(fy1[["ticker", "m", "eps"]], on=["ticker", "m"], how="left")
    val["EP"] = val["eps"] / val["close"]        # earnings yield; higher = cheaper
    idx = ["m", "ticker"]
    return (
        mp.set_index(idx)["MOM"],
        val.set_index(idx)["EP"],
        mp.set_index(idx)["SIZE"],
    )


def run(consensus, prices, meta, bench_monthly, cfg: BacktestConfig,
        bench_daily=None, earnings_dates=None) -> dict:
    consensus, prices, meta = data_schema.validate_all(consensus, prices, meta)
    bench_monthly = bench_monthly.copy()
    bench_monthly.index = pd.PeriodIndex(
        pd.to_datetime(bench_monthly.index).to_period("M"), name="m"
    )
    rf_m = (1 + cfg.rf_annual) ** (1 / 12) - 1

    mp = build_monthly_price(prices, cfg.universe.liquidity_lookback)
    fwd = forward_returns(mp)
    elig = eligibility(mp, meta, cfg)
    mktcap = mp.set_index(["m", "ticker"])["mktcap"]
    shortable = meta.assign(m=meta["asof"].dt.to_period("M")).set_index(["m", "ticker"])[
        "shortable"
    ]

    panel = factors.build_factor_panel(consensus, mp[["ticker", "m", "close"]], cfg.factor)
    mom, ep, size = _aux_factors(consensus, mp)

    # window mask
    start_p = _to_month(cfg.start)
    end_p = _to_month(cfg.end) if cfg.end else fwd.index.get_level_values("m").max()

    def _win(s):
        m = s.index.get_level_values("m")
        return s[(m >= start_p) & (m <= end_p)]

    fac_cols = [c for c in panel.columns if not c.startswith("z") or c == "COMPOSITE_z"]
    # keep primary raw factors + composite for the main tables; z-versions used in regressions
    primary = [
        c for c in panel.columns
        if c in {
            "OP_1M", "OP_3M", "NP_1M", "NP_3M", "EPS_1M", "EPS_3M",
            "OPBL_1M", "NPBL_1M", "OPR12_1M", "NPR12_1M",
            "BREADTH", "BREADTH_NET", "TP_1M", "TP_DISPARITY", "COMPOSITE_z",
        }
    ]

    results = {"per_factor": {}, "series": {}, "config": cfg}
    bench_al = bench_monthly.reindex(sorted(set(fwd.index.get_level_values("m"))))

    base_cost = float(np.mean(list(cfg.cost.long_cost_bps)))
    base_borrow = float(np.median(list(cfg.cost.borrow_annual)))

    for fac in primary:
        f = _win(panel[fac])
        if f.dropna().empty:
            continue
        book = portfolio.build_book(
            f, elig, mktcap, cfg.portfolio.quantile, cfg.portfolio.weighting, shortable
        )
        if book.empty:
            continue
        rr = portfolio.run_book(book, fwd, base_cost, cfg.cost.short_extra_bps, base_borrow)
        rr = rr[rr.index.map(lambda m: start_p <= m <= end_p)]
        b = bench_monthly.reindex(rr.index)
        long_excess = rr["long_net"] - b
        turnover = rr["long_to"].mean()
        results["per_factor"][fac] = {
            "long_only": metrics.summary(rr["long_net"], b, rf_m, turnover, cfg.newey_west_lags),
            "long_excess": metrics.summary(long_excess, b, rf_m, turnover, cfg.newey_west_lags),
            "long_short": metrics.summary(rr["ls_net"], b, rf_m, turnover, cfg.newey_west_lags),
            "long_gross": metrics.summary(rr["long_gross"], b, rf_m, turnover, cfg.newey_west_lags),
            "ls_gross": metrics.summary(rr["ls_gross"], b, rf_m, turnover, cfg.newey_west_lags),
        }
        results["series"][fac] = {
            "long_net": rr["long_net"], "long_excess": long_excess,
            "ls_net": rr["ls_net"], "ls_gross": rr["ls_gross"],
        }

    # ---- factor ranking table ---------------------------------------------
    rank_rows = []
    for fac, d in results["per_factor"].items():
        s = d["long_short"]
        le = d["long_excess"]
        rank_rows.append(
            {
                "factor": fac,
                "LS_CAGR": s["CAGR"], "LS_Sharpe": s["Sharpe"], "LS_MaxDD": s["MaxDD"],
                "LS_NW_t": s["NW_tstat"], "LongExcess_IR": le.get("IR", np.nan),
                "Long_CAGR": d["long_only"]["CAGR"], "WinRate": s["MonthlyWinRate"],
                "Turnover": s.get("Turnover", np.nan),
            }
        )
    results["ranking"] = (
        pd.DataFrame(rank_rows).set_index("factor").sort_values("LS_Sharpe", ascending=False)
        if rank_rows else pd.DataFrame()
    )

    # ---- seasonality (on LS-net of each factor) ---------------------------
    results["seasonality"] = {}
    for fac, s in results["series"].items():
        r = s["ls_net"]
        results["seasonality"][fac] = {
            "by_month": seasonality.by_calendar_month(r),
            "season_vs_other": seasonality.season_vs_other(
                r, cfg.season_months, cfg.n_bootstrap, cfg.seed
            ),
            "per_season_month": seasonality.per_season_month(r, cfg.season_months),
        }
    ls_series = {f: results["series"][f]["ls_net"] for f in results["series"]}
    results["horizon_compare_season"] = seasonality.compare_horizons_in_season(
        ls_series, season_months=cfg.season_months
    )

    # ---- sub-period robustness (LS Sharpe / CAGR per factor) --------------
    subrows = []
    for fac, s in results["series"].items():
        r = s["ls_net"]
        row = {"factor": fac}
        for (a, b0) in cfg.subperiods:
            pa, pb = _to_month(a), _to_month(b0)
            sub = r[[pa <= m <= pb for m in r.index]]
            row[f"{a[:4]}-{b0[:4]}_Sharpe"] = metrics.sharpe(sub) if len(sub) > 6 else np.nan
        subrows.append(row)
    results["subperiods"] = pd.DataFrame(subrows).set_index("factor") if subrows else pd.DataFrame()

    # ---- cost sensitivity (LS net) for the top factor ---------------------
    results["cost_sensitivity"] = _cost_grid(
        panel, primary, elig, mktcap, shortable, fwd, bench_monthly, cfg, start_p, end_p
    )

    # ---- valuation & momentum interactions --------------------------------
    results["interactions"] = _interactions(
        panel, ep, mom, size, fwd, cfg, start_p, end_p, elig, mktcap
    )

    # ---- sector-neutral comparison ----------------------------------------
    sector_map = meta.assign(m=meta["asof"].dt.to_period("M")).set_index(
        ["m", "ticker"]
    )["sector"]
    results["sector_neutral"] = {}
    for fac in [c for c in ("OP_1M", "NP_1M", "EPS_1M", "COMPOSITE_z") if c in panel]:
        raw = _win(panel[fac])
        sn = neutral.demean_within(raw, sector_map.reindex(raw.index))
        if sn.dropna().empty:
            continue
        book = portfolio.build_book(
            sn, elig, mktcap, cfg.portfolio.quantile, cfg.portfolio.weighting, shortable
        )
        if book.empty:
            continue
        rr = portfolio.run_book(book, fwd, base_cost, cfg.cost.short_extra_bps, base_borrow)
        rr = rr[rr.index.map(lambda m: start_p <= m <= end_p)]
        raw_ls = results["series"].get(fac, {}).get("ls_net")
        results["sector_neutral"][fac] = {
            "raw_LS_Sharpe": metrics.sharpe(raw_ls) if raw_ls is not None else np.nan,
            "neutral_LS_Sharpe": metrics.sharpe(rr["ls_net"]),
            "raw_LS_CAGR": metrics.cagr(raw_ls) if raw_ls is not None else np.nan,
            "neutral_LS_CAGR": metrics.cagr(rr["ls_net"]),
            "neutral_LS_NW_t": metrics.newey_west_t(rr["ls_net"], cfg.newey_west_lags)[1],
        }
    results["sector_neutral"] = pd.DataFrame(results["sector_neutral"]).T

    # ---- Fama-MacBeth ------------------------------------------------------
    reg_panel = pd.DataFrame(
        {
            "fwd_ret": fwd, "REV": panel.get("NP_1M"), "MOM": mom,
            "SIZE": size, "VALUE": ep,
        }
    ).dropna()
    reg_panel = reg_panel[
        [start_p <= m <= end_p for m in reg_panel.index.get_level_values("m")]
    ]
    if not reg_panel.empty:
        results["fama_macbeth"] = neutral.fama_macbeth(
            reg_panel, "fwd_ret", ["REV", "MOM", "SIZE", "VALUE"], cfg.newey_west_lags
        )

    # ---- event-time (optional) --------------------------------------------
    if earnings_dates is not None and bench_daily is not None and "NP_1M" in panel:
        rk = neutral.rank01(_win(panel["NP_1M"]))
        results["event_time"] = eventtime.event_study(
            earnings_dates, prices, bench_daily, rk, cfg.portfolio.quantile
        )

    results["panel"] = panel
    return results


def _cost_grid(panel, primary, elig, mktcap, shortable, fwd, bench, cfg, sp, ep):
    """LS-net Sharpe under each (long cost, borrow) scenario for each factor."""
    rows = []
    for fac in primary:
        f = panel[fac]
        f = f[[sp <= m <= ep for m in f.index.get_level_values("m")]]
        if f.dropna().empty:
            continue
        book = portfolio.build_book(f, elig, mktcap, cfg.portfolio.quantile,
                                    cfg.portfolio.weighting, shortable)
        book_real = portfolio.build_book(f, elig, mktcap, cfg.portfolio.quantile,
                                         cfg.portfolio.weighting, shortable, short_realistic=True)
        for lc in cfg.cost.long_cost_bps:
            for bor in cfg.cost.borrow_annual:
                rr = portfolio.run_book(book, fwd, lc, cfg.cost.short_extra_bps, bor)
                rr = rr[[sp <= m <= ep for m in rr.index]]
                rrr = portfolio.run_book(book_real, fwd, lc, cfg.cost.short_extra_bps, bor)
                rrr = rrr[[sp <= m <= ep for m in rrr.index]]
                rows.append(
                    {
                        "factor": fac, "long_cost_bps": lc, "borrow_annual": bor,
                        "LS_Sharpe": metrics.sharpe(rr["ls_net"]),
                        "LS_CAGR": metrics.cagr(rr["ls_net"]),
                        "LS_Sharpe_shortable_only": metrics.sharpe(rrr["ls_net"]),
                        "LongOnly_Sharpe": metrics.sharpe(rr["long_net"]),
                    }
                )
    return pd.DataFrame(rows)


def _interactions(panel, ep, mom, size, fwd, cfg, sp, ep_period, elig, mktcap):
    out = {}
    rev = panel.get("NP_1M")
    if rev is None:
        return out
    win = lambda s: s[[sp <= m <= ep_period for m in s.index.get_level_values("m")]]
    rev_w, ep_w, mom_w, fwd_w = win(rev), win(ep), win(mom), win(fwd)
    out["valuation_2x2_EP"] = neutral.valuation_2x2(rev_w, ep_w, fwd_w)
    out["cheap_revision_strategy"] = metrics.summary(
        neutral.cheap_revision_strategy(rev_w, ep_w, fwd_w).dropna()
    )
    # momentum correlation
    corr_df = pd.DataFrame({"REV": rev_w, "MOM": mom_w}).dropna()
    out["rev_mom_corr"] = (
        corr_df.groupby(level="m").apply(lambda g: g["REV"].corr(g["MOM"])).mean()
    )
    # sector-neutral vs raw (needs sector; approximated via size bucket if no sector col here)
    return out
