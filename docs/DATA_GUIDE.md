# Data acquisition guide — Korea earnings-revision backtest

The engine is complete and tested. The one thing it cannot manufacture is the
input that the whole study depends on: **point-in-time (look-ahead-free)
consensus estimates for KOSPI + KOSDAQ**. This note tells you exactly what to
get, from where, and how to shape it into `krev`'s schema.

## Why you cannot download this for free

Free Korean data sources (KRX, Naver/Daum, pykrx, FinanceDataReader, yfinance)
give you **prices, market cap, traded value, listing dates, sector tags** — all
of which the engine already knows how to load. None of them give you a
**historical, point-in-time consensus revision panel**: the FY1/FY2 operating
profit / net profit / EPS / target-price consensus *as it stood on each past
month-end*, together with the number of contributing analysts. That panel is a
paid, licensed product. Using a *current* consensus snapshot to backfill the
past is the classic look-ahead trap and will fabricate alpha — do not do it.

## Where to get a point-in-time consensus panel (pick one)

| Source | Product | Notes |
|---|---|---|
| **FnGuide** | DataGuide / FnGuide Consensus | The Korean market standard. Has 컨센서스 시계열 (consensus time series) with as-of dates back to ~2000s. Ask for "point-in-time 추정치 시계열". |
| **WISEfn** | WiseReport / WISEfn DB | Widely used by Korean asset managers; consensus history + revision counts. |
| **QuantiWise (FnGuide)** | QuantiWise | Quant-oriented; exports factor-ready consensus panels. |
| **Refinitiv / LSEG** | I/B/E/S Estimates (KR) | Global standard; I/B/E/S has genuine point-in-time snapshots and per-broker revisions. Best for analyst-count breadth. |
| **Bloomberg** | BEst (EEO/EE) | `BEst_EPS`, `BEst_OPP`, `BEst_Target_Price` with `OVERRIDE=BEST_FPERIOD_OVERRIDE=1FY/2FY`; pull historical snapshots via BQL/`=BDH` on estimate fields. |

Any of these can produce the three panels below. FnGuide/QuantiWise is usually
the least friction for a Korea-only study; I/B/E/S is best if you also want
per-analyst revision counts (breadth).

## What to request, precisely

Ask the vendor for **monthly (month-end) point-in-time snapshots**, per
security, from **2005-01 (or earliest available) to now**, of:

1. FY1 and FY2 **operating profit** (영업이익) consensus
2. FY1 and FY2 **net profit attributable to controlling shareholders**
   (지배주주순이익) consensus
3. FY1 and FY2 **EPS** consensus
4. Consensus **target price** (목표주가)
5. **Number of estimates** in the consensus, and if possible the count of
   analysts who **revised up / down in the trailing month** (for breadth)
6. The **fiscal-year-end date** each FY1/FY2 figure refers to — **mandatory**,
   this is what lets the engine handle the annual FY1 roll without inventing a
   fake revision.

Plus, from the same or a free source:

7. Daily **prices, market cap, traded value, VWAP** (pykrx / FinanceDataReader)
8. Security **metadata**: market (KOSPI/KOSDAQ), sector (GICS or WICS), listing
   date, and flags for 우선주/SPAC/REIT/관리종목/거래정지, plus 대차가능 (shortable)
9. **Earnings announcement dates** (실적 발표일) for the event-time study
10. **KOSPI / KOSPI200 total-return** index for the benchmark

## Shaping it into the schema

Reshape the consensus export to **long form** — one row per
`(asof, ticker, fiscal)` — with columns matching `krev.data_schema`:

```
asof, ticker, fiscal(FY1|FY2), fy_end, op, np_ctrl, eps, tp, n_est, n_up_1m, n_dn_1m
```

Then load with a column map:

```python
from krev import adapters
consensus = adapters.load_consensus_csv(
    "fnguide_consensus_long.csv",
    colmap={
        "asof": "기준일", "ticker": "종목코드", "fiscal": "FY", "fy_end": "결산월",
        "op": "영업이익_컨센서스", "np_ctrl": "지배주주순이익_컨센서스",
        "eps": "EPS_컨센서스", "tp": "목표주가", "n_est": "추정기관수",
        "n_up_1m": "1M상향수", "n_dn_1m": "1M하향수",
    },
)
```

If your export is **wide** (FY1 and FY2 in separate columns on one row), melt it
into two rows per `(asof, ticker)` first — one `fiscal='FY1'`, one `'FY2'` —
carrying each one's own `fy_end`.

### Prices & metadata (free)

```python
prices = adapters.load_prices_pykrx("2005-01-01", "2026-08-01")   # needs pykrx + KRX access
meta   = adapters.load_meta_csv("meta.csv", colmap={...})
```

(You can also build `prices` from FinanceDataReader; any frame matching
`PRICE_COLS` works.)

## Then run the real study

Copy `run_real_backtest.py`, point it at your loaders, and it produces the exact
same tables/charts/answer-sheet as the synthetic demo — but as real findings.
Nothing else in the engine changes.

## Point-in-time hygiene checklist

- [ ] Each consensus row is the value that was **on the screen at `asof`**, not a
      later restatement.
- [ ] `fy_end` is populated so the FY1 annual roll is linked, not double-counted.
- [ ] Prices are **adjusted** for splits/rights; ideally total-return.
- [ ] Metadata flags (관리종목/거래정지/우선주/SPAC/REIT) are **as-of**, not current.
- [ ] `shortable` reflects historical **대차 가능** status if you trust the short book.
- [ ] Benchmark is **total return**, matched in frequency (monthly) to the book.
