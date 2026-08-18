# Korea Earnings-Revision Factor — Backtest Engine

A point-in-time, look-ahead-free backtest framework for testing whether the
**earnings-revision anomaly** (buy stocks whose forward consensus is being
revised up) works in the Korean market — KOSPI + KOSDAQ — over the longest
history your data allows.

It implements the full research brief: OP/NP/EPS revisions at 1M and 3M
horizons, FY1-roll handling, breadth and target-price factors, quintile
Long-only / Long−Benchmark / Long-Short books, realistic Korean costs + borrow,
Feb/May/Aug/Nov seasonality with bootstrap + Newey-West significance, event-time
analysis around earnings dates, sector/size neutralization, valuation and
momentum interactions, Fama-MacBeth regressions, and Excel/CSV/chart output with
an auto-filled Q1–Q10 answer sheet.

---

## ⚠️ Read this first: the honest status

**The engine is complete and verified. It has not yet been run on real Korean
data, because that data is not present in this repo and cannot be obtained for
free.**

The entire study depends on one input: **point-in-time consensus estimates for
KOSPI/KOSDAQ back to 2005–2010** (FY1/FY2 operating profit, net profit, EPS,
target price, analyst counts, *as they stood on each past month-end*). That is a
licensed, paid dataset — FnGuide DataGuide, WISEfn, QuantiWise, Refinitiv
I/B/E/S, or Bloomberg. Free sources give prices and market cap but **not** a
historical consensus-revision panel, and using today's consensus to backfill the
past manufactures fake alpha (look-ahead bias).

So this repository deliberately does **not** ship invented Sharpe ratios,
seasonality t-stats, or a "current top longs" list. Fabricated numbers are the
one output that would actively mislead a real allocation decision — and the brief
explicitly asks not to bend Korea's results toward the US prior. Instead you get:

1. **A complete, tested engine** (`krev/`) implementing every part of the brief.
2. **A synthetic self-test** (`run_synthetic_demo.py`) that runs the whole
   pipeline on generated data with a *known* embedded signal, proving the maths
   is wired correctly. Its numbers are meaningless as market research.
3. **A one-file path to the real study**: drop in a vendor consensus export
   (`docs/DATA_GUIDE.md`) and run `run_real_backtest.py` — same tables, real
   answers.

The Q1–Q10 answer sheet is generated **from whatever data you feed it**. On
synthetic data it is labelled as such; on your real panel it becomes the study.

---

## Quick start (self-test — no market data needed)

```bash
pip install -r requirements.txt
python run_synthetic_demo.py
```

This writes to `outputs/`: per-factor ranking, Long-only/Long-excess/Long-Short
tables, seasonality, 1M-vs-3M season comparison, sub-period robustness, cost
sensitivity, Fama-MacBeth, event-time, an Excel workbook, three charts, and a
`synthetic_ANSWERS_Q1-Q10.md`. Because the synthetic data has a real
revision→return link baked in, a correct engine recovers a positive, significant
revision Long-Short and a monotonic post-earnings drift — that is the unit test.

## Interactive app

```bash
pip install -r requirements.txt
streamlit run app.py      # opens a dashboard; starts in synthetic demo mode
```

Sidebar controls (universe, factor, cost/borrow, weighting, dates), tabbed
tables/charts, Q1–Q10 answer sheet, and an Excel download. Switch to "Upload
real CSVs" to run on your consensus panel. Deploy free on Streamlit Community
Cloud / Hugging Face Spaces — see [docs/APP.md](docs/APP.md).

## Running the real study

1. Obtain a point-in-time consensus panel — see **[docs/DATA_GUIDE.md](docs/DATA_GUIDE.md)**.
2. Reshape it to `krev.data_schema` (long form, one row per `asof×ticker×FY`,
   `fy_end` mandatory).
3. Wire `load_inputs()` in `run_real_backtest.py` to your loaders.
4. `python run_real_backtest.py` → results for ALL / TOP500 / KOSPI200 universes.

## What each question maps to

| Q | Where it's answered |
|---|---|
| Q1 long-term validity | `ranking`, LS Sharpe/CAGR/NW-t per factor |
| Q2 OP vs NP vs EPS | `ranking` (1M family) |
| Q3 1M vs 3M | `ranking` + `horizon_compare_season` |
| Q4 Feb/May/Aug/Nov | `season_vs_other`, `calendar_month_best`, bootstrap CI |
| Q5 post-earnings strength | `horizon_compare_season` + `event_time` |
| Q6 sector-neutral | sector-demeaned re-run (`neutral.demean_within`) |
| Q7 costs + borrow | `cost_sensitivity` (incl. shortable-only) |
| Q8 realistic long-only | `long_only` table |
| Q9 revision + value | `interactions` (2×2, cheap-revision, Fama-MacBeth) |
| Q10 current longs | latest top-quintile dump for the chosen factor |

## Layout

```
krev/
  data_schema.py   # the point-in-time input contract + validation
  config.py        # universe / portfolio / cost / factor knobs
  factors.py       # revisions, FY1-roll linking, blended/rolling fwd, breadth, TP, composite
  portfolio.py     # quintile books, weighting, turnover, costs, borrow
  metrics.py       # CAGR/Sharpe/Sortino/IR/MaxDD/... , Newey-West, bootstrap
  seasonality.py   # calendar month, season-vs-other, 1M-vs-3M season test
  eventtime.py     # post-earnings-announcement drift by revision group
  neutral.py       # sector/size neutral, 2x2 value, momentum, Fama-MacBeth
  report.py        # CSV + Excel + charts + Q1-Q10 answer sheet
  adapters.py      # synthetic generator + pykrx / vendor-CSV loaders
run_synthetic_demo.py   # end-to-end self-test (no data needed)
run_real_backtest.py    # template: plug in real data, get real answers
docs/DATA_GUIDE.md      # how/where to get the consensus panel for Korea
docs/METHODOLOGY.md     # how each brief requirement is implemented
```

## Design choices worth knowing

- **FY1 roll** is handled by within-fiscal-year linking (compare the *same*
  fiscal year across months), not naive current-FY1/lagged-FY1. See
  `docs/METHODOLOGY.md`.
- **Timing**: signal at month `m`, return over `m+1` — a built-in ≥1-day lag.
- **Significance** everywhere uses Newey-West HAC t-stats and bootstrap CIs, not
  naive t-tests, because monthly factor returns are autocorrelated.
- **No data mining toward a conclusion**: the engine reports what the data says.
  If revision doesn't work in Korea, or only works in some regimes, the tables
  will show exactly that.
