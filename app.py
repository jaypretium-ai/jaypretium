#!/usr/bin/env python3
"""
Korea Earnings-Revision Factor — interactive backtest app (Streamlit).

Run locally:      streamlit run app.py
Deploy (free):    push repo -> https://share.streamlit.io -> point at app.py

Two data modes:
  * Demo (synthetic): runs instantly with generated data so the app is usable
    with zero setup. Numbers are a plumbing demo, NOT findings about Korea.
  * Real: upload your point-in-time consensus CSV (schema: docs/CIQ_EXTRACTION.md)
    or let the app read data/consensus.csv committed to the repo. Prices/meta are
    uploaded too, or synthesized as a stand-in until you wire pykrx.

The heavy lifting is the same `krev` engine used by the CLI drivers.
"""
from __future__ import annotations

import io
import pandas as pd
import streamlit as st

from krev import adapters, report
from krev.config import BacktestConfig, UniverseConfig, CostConfig
from krev.run_backtest import run

st.set_page_config(page_title="Korea Earnings-Revision Backtest", layout="wide")


# --------------------------------------------------------------------------- #
# Data loading (cached)                                                         #
# --------------------------------------------------------------------------- #
@st.cache_data(show_spinner=False)
def load_demo(n_tickers: int, start: str, end: str):
    return adapters.make_synthetic(n_tickers=n_tickers, start=start, end=end)


@st.cache_data(show_spinner=True)
def run_backtest(_data_key: str, data: dict, universe: str, top_n: int,
                 illiq: float, long_bps: float, borrow: float, weighting: str,
                 start: str, end: str):
    cfg = BacktestConfig(
        start=start, end=end, benchmark="KOSPI",
        universe=UniverseConfig(definition=universe, illiquid_drop_pct=illiq,
                                top_n_by_mktcap=top_n if universe == "TOP500" else None),
        cost=CostConfig(long_cost_bps=(long_bps,), borrow_annual=(borrow,)),
        n_bootstrap=1500,
    )
    return run(data["consensus"], data["prices"], data["meta"],
               data["bench_monthly"], cfg,
               bench_daily=data.get("bench_daily"),
               earnings_dates=data.get("earnings_dates"))


# --------------------------------------------------------------------------- #
# Sidebar                                                                       #
# --------------------------------------------------------------------------- #
st.sidebar.title("⚙️ Settings")
mode = st.sidebar.radio("Data source", ["Demo (synthetic)", "Upload real CSVs"])

data = None
data_key = "demo"
if mode == "Demo (synthetic)":
    st.sidebar.caption("Generated data with a known signal — plumbing demo, not findings.")
    n_tickers = st.sidebar.slider("# synthetic tickers", 80, 300, 160, 20)
    data = load_demo(n_tickers, "2010-01-01", "2022-12-31")
    data_key = f"demo-{n_tickers}"
    start_default, end_default = "2011-01-01", "2022-12-31"
else:
    st.sidebar.caption("Consensus schema: see docs/CIQ_EXTRACTION.md")
    cfile = st.sidebar.file_uploader("consensus.csv (required)", type=["csv"])
    pfile = st.sidebar.file_uploader("prices.csv (optional; else synthetic proxy)", type=["csv"])
    mfile = st.sidebar.file_uploader("meta.csv (optional)", type=["csv"])
    if cfile is not None:
        consensus = adapters.data_schema.validate_consensus(pd.read_csv(cfile))
        demo = load_demo(len(consensus["ticker"].unique()) or 120, "2010-01-01", "2022-12-31")
        prices = (adapters.data_schema.validate_prices(pd.read_csv(pfile))
                  if pfile is not None else demo["prices"])
        meta = (adapters.data_schema.validate_meta(pd.read_csv(mfile))
                if mfile is not None else demo["meta"])
        data = {"consensus": consensus, "prices": prices, "meta": meta,
                "bench_monthly": demo["bench_monthly"], "bench_daily": demo["bench_daily"],
                "earnings_dates": demo.get("earnings_dates")}
        data_key = f"real-{cfile.name}-{getattr(cfile,'size',0)}"
        start_default, end_default = "2011-01-01", "2024-12-31"
    else:
        st.info("⬅️ Upload a consensus.csv to run on real data, or switch to Demo mode.")
        st.stop()

start = st.sidebar.text_input("Start", start_default)
end = st.sidebar.text_input("End", end_default)
universe = st.sidebar.selectbox("Universe", ["ALL", "TOP500", "KOSPI200"])
top_n = st.sidebar.number_input("TOP-N (for TOP500)", 100, 1000, 500, 50)
illiq = st.sidebar.slider("Drop illiquid bottom %", 0.0, 0.4, 0.20, 0.05)
weighting = st.sidebar.selectbox("Weighting", ["equal", "mktcap"])
long_bps = st.sidebar.slider("Long cost (bp, one-way)", 0, 50, 20, 5)
borrow = st.sidebar.select_slider("Borrow (annual)", [0.0, 0.02, 0.05, 0.10], 0.05)

# --------------------------------------------------------------------------- #
# Run                                                                           #
# --------------------------------------------------------------------------- #
st.title("🇰🇷 Korea Earnings-Revision Factor — Backtest")
if mode == "Demo (synthetic)":
    st.warning("SYNTHETIC DEMO — numbers are a plumbing test, not findings about Korea. "
               "Upload a real point-in-time consensus panel for real results.")

with st.spinner("Running backtest…"):
    results = run_backtest(data_key, data, universe, int(top_n), illiq,
                           float(long_bps), float(borrow), weighting, start, end)

rk = results.get("ranking", pd.DataFrame())
if rk.empty:
    st.error("No factor results — check data coverage / date range.")
    st.stop()

tabs = st.tabs(["Overview / Q1–Q10", "Factor ranking", "Seasonality",
                "1M vs 3M", "Costs", "Event-time & FM", "Long candidates"])

with tabs[0]:
    st.markdown(report.answer_sheet(results, synthetic=(mode == "Demo (synthetic)")))

with tabs[1]:
    st.subheader("Factor ranking (Long-Short, net)")
    st.dataframe(rk.round(3), width='stretch')
    st.bar_chart(rk["LS_Sharpe"])
    best = rk.index[0]
    eq = (1 + results["series"][best]["ls_net"]).cumprod()
    eq.index = eq.index.to_timestamp()
    st.line_chart(eq, height=280)
    st.caption(f"Cumulative Long-Short (net) growth — {best}")

with tabs[2]:
    best = rk.index[0]
    st.subheader(f"Seasonality — {best}")
    bm = results["seasonality"][best]["by_month"]
    st.bar_chart(bm["mean"])
    st.dataframe(bm.round(4), width='stretch')
    svo = report._per_factor_table  # noqa: keep import warm
    st.markdown("**Season (Feb/May/Aug/Nov) vs other months**")
    rows = []
    for fac, s in results["seasonality"].items():
        d = s["season_vs_other"]
        rows.append({"factor": fac, "season_mean": d["season"]["mean"],
                     "other_mean": d["other"]["mean"],
                     "diff": d["season_minus_other"],
                     "boot_p_gt0": d["boot_p_diff_gt_0"]})
    st.dataframe(pd.DataFrame(rows).set_index("factor").round(4), width='stretch')

with tabs[3]:
    st.subheader("1M vs 3M revision (season months)")
    st.dataframe(results.get("horizon_compare_season", pd.DataFrame()).round(4),
                 width='stretch')

with tabs[4]:
    st.subheader("Cost / borrow sensitivity")
    st.dataframe(results.get("cost_sensitivity", pd.DataFrame()).round(3),
                 width='stretch')

with tabs[5]:
    st.subheader("Event-time (post-earnings drift by revision group)")
    et = results.get("event_time")
    if isinstance(et, pd.DataFrame) and not et.empty:
        st.dataframe(et.round(4), width='stretch')
    st.subheader("Fama-MacBeth (next-month return on revision + controls)")
    fm = results.get("fama_macbeth")
    if isinstance(fm, pd.DataFrame):
        st.dataframe(fm.round(4), width='stretch')

with tabs[6]:
    best = st.selectbox("Factor", list(results["series"].keys()))
    panel = results["panel"]
    s = panel[best].dropna()
    last_m = s.index.get_level_values("m").max()
    top = s.xs(last_m, level="m").sort_values(ascending=False).head(20)
    st.subheader(f"Latest top-20 by {best} ({last_m})")
    st.dataframe(top.rename("factor_value").to_frame(), width='stretch')
    if mode == "Demo (synthetic)":
        st.caption("Synthetic tickers — not real names.")

# download
buf = io.BytesIO()
with pd.ExcelWriter(buf, engine="openpyxl") as xw:
    rk.to_excel(xw, sheet_name="ranking")
    report._per_factor_table(results, "long_short").to_excel(xw, sheet_name="long_short")
    report._per_factor_table(results, "long_only").to_excel(xw, sheet_name="long_only")
st.sidebar.download_button("⬇️ Download results (xlsx)", buf.getvalue(),
                           file_name="krev_results.xlsx")
