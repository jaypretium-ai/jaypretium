#!/usr/bin/env python3
"""
Real-data driver template.

Fill in the three loaders with YOUR point-in-time data (see docs/DATA_GUIDE.md),
then run. Everything downstream is identical to the synthetic self-test — the
same tables, charts, and Q1-Q10 answer sheet, but as real findings.

    python run_real_backtest.py

The three universe passes (ALL, TOP500, KOSPI200) run in a loop so you get the
primary result plus robustness in one shot.
"""
from __future__ import annotations

import pandas as pd

from krev import adapters, report
from krev.config import BacktestConfig, UniverseConfig, CostConfig
from krev.run_backtest import run


def load_inputs():
    """
    REPLACE these three lines with your real loaders. Each must return a
    schema-conforming frame (krev.data_schema). Example:

    consensus = adapters.load_consensus_csv("data/consensus_long.csv", colmap={
        "asof": "기준일", "ticker": "종목코드", "fiscal": "FY", "fy_end": "결산월",
        "op": "영업이익", "np_ctrl": "지배주주순이익", "eps": "EPS", "tp": "목표주가",
        "n_est": "추정기관수", "n_up_1m": "1M상향", "n_dn_1m": "1M하향",
    })
    prices = adapters.load_prices_pykrx("2005-01-01", "2026-08-01")
    meta   = adapters.load_meta_csv("data/meta.csv", colmap={...})
    bench_monthly = pd.read_csv("data/kospi200_tr.csv", parse_dates=["date"]) \
                      .set_index("date")["ret"]
    bench_daily   = pd.read_csv("data/kospi200_tr_daily.csv", parse_dates=["date"]) \
                      .set_index("date")["ret"]
    earnings_dates = pd.read_csv("data/earnings_dates.csv", parse_dates=["report_date"])
    """
    raise NotImplementedError(
        "Wire load_inputs() to your real point-in-time data. See docs/DATA_GUIDE.md.\n"
        "Until then, run `python run_synthetic_demo.py` to exercise the engine."
    )


def main():
    consensus, prices, meta, bench_monthly, bench_daily, earnings_dates = load_inputs()

    for uni in ("ALL", "TOP500", "KOSPI200"):
        cfg = BacktestConfig(
            start="2010-01-01",          # push to "2005-01-01" if data allows
            end=None,
            benchmark="KOSPI200",
            universe=UniverseConfig(
                definition=uni,
                min_listing_months=12,
                illiquid_drop_pct=0.20,
                top_n_by_mktcap=500 if uni == "TOP500" else None,
            ),
            cost=CostConfig(
                long_cost_bps=(15.0, 20.0, 25.0),   # 30/40/50bp round trip
                borrow_annual=(0.02, 0.05, 0.10),
            ),
            outdir=f"outputs/{uni.lower()}",
        )
        print(f"\n########## UNIVERSE = {uni} ##########")
        results = run(consensus, prices, meta, bench_monthly, cfg,
                      bench_daily=bench_daily, earnings_dates=earnings_dates)

        print(results["ranking"].round(3).to_string())
        report.export_all(results, cfg.outdir, tag=uni.lower())
        report.make_charts(results, cfg.outdir, tag=uni.lower())
        with open(f"{cfg.outdir}/ANSWERS_Q1-Q10.md", "w") as f:
            f.write(report.answer_sheet(results, synthetic=False))
        print(f"Wrote results + answers to {cfg.outdir}/")


if __name__ == "__main__":
    main()
