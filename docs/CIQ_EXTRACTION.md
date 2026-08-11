# Capital IQ (CIQ) extraction template → krev consensus panel

You have Capital IQ. This is the exact bridge from the CIQ Excel plugin to the
`krev` point-in-time consensus schema. The cloud backtest session cannot call the
CIQ plugin directly (it runs on your machine with your CIQ login), so the flow is:

**CIQ Excel → save workbook → Google Drive → I read it here → real backtest.**

---

## 0. What to pull

Per security, **month-end point-in-time snapshots** (as-of each past month-end),
for **FY1 and FY2** separately:

- Operating profit (영업이익) consensus
- Net income to controlling shareholders (지배주주순이익) consensus
- EPS consensus
- Target price consensus
- Number of estimates (and up/down revision counts if available)
- The fiscal-year-end each FY1/FY2 refers to

Prices / market cap / traded value / listing date / sector I add for free via
pykrx — **you only need the consensus fields from CIQ.**

## 1. CIQ Excel formula pattern (point-in-time)

The CIQ function retrieves an estimate for a relative fiscal period **as it stood
on a given as-of date** — that as-of date is what makes it look-ahead-free:

```
=CIQ( <identifier>, <mnemonic>, <asOfDate>, <relativePeriod> )
```

- `<identifier>` — e.g. `"IQ005930"` / a CIQ company ID / ticker+exchange
- `<asOfDate>` — the historical month-end cell (drag this down a monthly date column)
- `<relativePeriod>` — `"IQ_FY1"` for FY1, `"IQ_FY2"` for FY2

Estimate mnemonics (⚠️ **confirm the exact string in your plugin's Formula
Builder — CIQ mnemonic/period tokens vary by version/region**):

| Field | Typical CIQ mnemonic | Notes |
|---|---|---|
| Operating profit | `IQ_EBIT_EST` | For KR 영업이익, verify EBIT vs a dedicated OP line matches your definition |
| Net income (ctrl) | `IQ_NI_EST` | Consensus net income; confirm it's attributable-to-parent |
| EPS | `IQ_EPS_EST` | Consensus EPS |
| Target price | `IQ_TARGET_PRICE` | Consensus TP |
| # estimates | `IQ_NUM_EST_EPS` / `IQ_NUMBER_EST` | breadth denominator |
| FY end date | `IQ_PERIOD_DATE_EST` | the fiscal-year-end FY1/FY2 points to |

Point-in-time history: with the `asOfDate` argument populated from a **monthly
date column** (2005-01-31, 2005-02-28, …, current), each row is the consensus as
it was on that date. That is exactly the panel needed.

Tip: `=CIQRANGE(...)` pulls a whole time series in one array — faster than
one `=CIQ()` per cell if your plugin version supports estimate ranges with an
as-of/period axis.

## 2. Output layout to save

Either layout works — a normalizer for each is provided.

**(A) Long form (preferred)** — one row per `asof × ticker × FY`:

| asof | ticker | fiscal | fy_end | op | np_ctrl | eps | tp | n_est | n_up_1m | n_dn_1m |
|------|--------|--------|--------|----|---------|-----|----|-------|---------|---------|

**(B) Wide form** — one row per `asof × ticker`, FY1/FY2 in separate columns:

| asof | ticker | op_fy1 | op_fy2 | np_fy1 | np_fy2 | eps_fy1 | eps_fy2 | fy1_end | fy2_end | tp | n_est | n_up_1m |
|------|--------|--------|--------|--------|--------|---------|---------|---------|---------|----|-------|---------|

Save as `.xlsx` or `.csv`, put it in Google Drive (any folder), and tell me the
file name.

## 3. Loading it (what I run here)

Long form:
```python
from krev import adapters
consensus = adapters.load_consensus_csv("ciq_consensus_long.csv", colmap={
    "asof": "asof", "ticker": "ticker", "fiscal": "fiscal", "fy_end": "fy_end",
    "op": "op", "np_ctrl": "np_ctrl", "eps": "eps", "tp": "tp",
    "n_est": "n_est", "n_up_1m": "n_up_1m", "n_dn_1m": "n_dn_1m",
})
```

Wide form (auto-melted to FY1/FY2 rows):
```python
from krev import adapters
consensus = adapters.melt_ciq_wide("ciq_consensus_wide.csv", colmap={
    "asof": "asof", "ticker": "ticker",
    "op_fy1": "op_fy1", "op_fy2": "op_fy2",
    "np_fy1": "np_fy1", "np_fy2": "np_fy2",
    "eps_fy1": "eps_fy1", "eps_fy2": "eps_fy2",
    "fy1_end": "fy1_end", "fy2_end": "fy2_end",
    "tp": "tp", "n_est": "n_est", "n_up_1m": "n_up_1m",
})
```

Then `run_real_backtest.py` produces the full ALL / TOP500 / KOSPI200 results.

## 4. Coverage caveat (so we set expectations honestly)

CIQ's Korean estimate coverage is deep for large caps and generally solid from
the early/mid-2010s. Pre-2010 point-in-time consensus (especially KOSDAQ small
caps and 영업이익 vs EBIT mapping) can be thin or approximate. When the real data
loads, the engine reports per-year universe counts — if early years are sparse
we simply start the sample where coverage is real, rather than pretending.
