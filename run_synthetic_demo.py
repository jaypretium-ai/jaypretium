#!/usr/bin/env python3
"""
Synthetic end-to-end self-test for the krev engine.

PURPOSE: prove every stage runs and the maths is wired correctly — NOT to say
anything about the Korean market. The synthetic data has a KNOWN revision->return
link baked in, so a correct engine should recover a positive, significant
revision Long-Short. That is a unit test of the plumbing, nothing more.

To run the REAL study, replace `adapters.make_synthetic()` with your loaders:
    consensus = adapters.load_consensus_csv("dataguide_export.csv", colmap={...})
    prices    = adapters.load_prices_pykrx("2005-01-01", "2026-08-01")
    meta      = adapters.load_meta_csv("meta.csv", colmap={...})
...keeping the same call to run_backtest.run(...).
"""
from __future__ import annotations

import pandas as pd

from krev import adapters, report
from krev.config import BacktestConfig, UniverseConfig
from krev.run_backtest import run


def latest_longs(results, factor, n=20):
    panel = results["panel"]
    if factor not in panel:
        return pd.DataFrame()
    s = panel[factor].dropna()
    last_m = s.index.get_level_values("m").max()
    top = s.xs(last_m, level="m").sort_values(ascending=False).head(n)
    return top.rename("factor_value").to_frame().assign(month=str(last_m))


def main():
    print("Generating synthetic panels (this is a plumbing test, not research)...")
    data = adapters.make_synthetic(n_tickers=160, start="2010-01-01", end="2022-12-31")

    cfg = BacktestConfig(
        start="2011-01-01",              # allow 12m warm-up for 12-1 momentum
        end="2022-12-31",
        universe=UniverseConfig(definition="ALL", illiquid_drop_pct=0.20),
        n_bootstrap=2000,
        outdir="outputs",
    )

    print("Running backtest...")
    results = run(
        data["consensus"], data["prices"], data["meta"], data["bench_monthly"],
        cfg, bench_daily=data["bench_daily"], earnings_dates=data["earnings_dates"],
    )

    print("\n=== FACTOR RANKING (Long-Short, net) ===")
    with pd.option_context("display.width", 160, "display.max_columns", 20):
        print(results["ranking"].round(3))

    print("\n=== 1M vs 3M in season months ===")
    print(results["horizon_compare_season"].round(4).to_string(index=False))

    print("\n=== Exporting tables + charts ===")
    written = report.export_all(results, cfg.outdir, tag="synthetic")
    charts = report.make_charts(results, cfg.outdir, tag="synthetic")
    for k, v in written.items():
        print(f"  {k}: {v}")
    for c in charts:
        print(f"  chart: {c}")

    ans = report.answer_sheet(results, synthetic=True)
    with open("outputs/synthetic_ANSWERS_Q1-Q10.md", "w") as f:
        f.write(ans)
    print("\n  answers: outputs/synthetic_ANSWERS_Q1-Q10.md")

    best = results["ranking"].index[0]
    print(f"\n=== Latest top-20 longs for {best} (SYNTHETIC tickers) ===")
    print(latest_longs(results, best).round(4).to_string())

    print("\nDONE. Synthetic self-test complete.")


if __name__ == "__main__":
    main()
