# Methodology

How each requirement in the brief is implemented, and where to find it.

## Point-in-time / look-ahead control
- Every factor is computed from month-end consensus snapshots keyed by `asof`
  (the date the value was knowable), never by the fiscal date it refers to.
- Portfolios formed on the signal at month `m` earn the return of month `m+1`
  (`run_backtest.forward_returns`). At monthly resolution this is already a
  ≥1-trading-day lag; `PortfolioConfig.exec_lag_days` / `exec_price` refine the
  fill (next-day close or VWAP) without ever letting month-`m` info touch a
  month-`m` return.

## FY1 annual-roll handling (the flagged problem)
`factors._lagged_same_fy` performs **within-fiscal-year linking**: each
consensus row carries `fy_end`, so a 1M/3M revision compares the current FY1
fiscal year's estimate today against *that same fiscal year's* estimate 1/3
months ago — even if the vendor labelled it FY2 back then. The spurious jump at
the December roll never enters the ratio. Two robustness variants are also built:
- **blended forward** `w·FY1 + (1−w)·FY2` (`fy1_blend_weight`),
- **rolling-12m forward** `FY1·(m/12) + FY2·(1−m/12)`, `m` = months to FY1 end.

## Factor family (`factors.build_factor_panel`)
OP/NP/EPS 1M & 3M revisions; blended (`*BL`) and rolling-12m (`*R12`) revisions;
revision **breadth** (`n_up_1m/n_est`) and net breadth; **target-price**
disparity and 1M/3M TP revision; a **z-score composite**
`mean(z(OP_1M), z(NP_1M), z(TP_1M))`. Distorted percentage revisions (loss→profit
sign flips, near-zero denominators) are guarded, cross-sectionally winsorized at
1/99%, and offered in standardized (cross-sectional z) form.

## Universe & filters (`run_backtest.eligibility`)
KOSPI+KOSDAQ (ALL), Top-500 by cap, or KOSPI200 proxy; ≥12-month seasoning;
exclude 우선주/SPAC/REIT/관리종목/거래정지; drop bottom-20% by trailing-60-day
average traded value; optional market-cap floor (e.g. 1,000억).

## Portfolio & costs (`portfolio.py`)
Top/bottom quintile, equal- or cap-weighted; Long-only, Long−Benchmark, and
Long-Short books. Costs applied on traded notional each rebalance with a
30/40/50bp round-trip long sensitivity; short leg adds transaction + **borrow**
(2%/5%/10% annual) scenarios and a **shortable-only** realistic variant.

## Statistics (`metrics.py`, `seasonality.py`)
CAGR, ann. vol, Sharpe, Sortino, IR, MaxDD, hit/win rate, avg/median monthly,
downside vol, beta, best/worst month, turnover, holding period. Significance via
**Newey-West** HAC t-stats and **bootstrap** CIs.

## Seasonality
Calendar-month breakdown; **Feb/May/Aug/Nov vs other** with bootstrap CI on the
difference; per-season-month split; and the **direct 1M-vs-3M season-month test**
(`compare_horizons_in_season`) — the core US hypothesis that the freshest 1M
revision dominates right after earnings season.

## Event-time (`eventtime.py`)
Aligns each stock's daily excess return to its own report date; averages
post-report cumulative excess return over 0-5 / 6-20 / 21-60 trading days,
split by whether the name was a top- or bottom-revision stock at the report.

## Neutralization & regressions (`neutral.py`)
Sector- and size-neutral (within-group demeaning); valuation 2×2 (revision ×
cheapness) and the "top-revision, cheaper-half" strategy; revision↔momentum
correlation; and **Fama-MacBeth** cross-sectional regressions of next-month
return on revision + momentum + size + value (+beta), with NW t-stats — does
revision survive the controls?

## Outputs (`report.py`)
All tables to CSV + one Excel workbook; headline charts (LS equity, calendar-month
seasonality, Sharpe ranking); and an auto-filled **Q1–Q10 answer sheet**.
