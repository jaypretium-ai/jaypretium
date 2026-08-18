# The app (`app.py`)

An interactive Streamlit front-end over the `krev` engine. Same computation as
the CLI drivers, but with sidebar controls, tables, charts, and an Excel export.

## Run locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

Opens at http://localhost:8501. It starts in **Demo (synthetic)** mode so it
works with zero data — the banner marks those numbers as a plumbing demo, not
Korea findings. Switch to **Upload real CSVs** and drop in your
`consensus.csv` (schema: `docs/CIQ_EXTRACTION.md`) for real results.

## Deploy (pick one)

| Host | How | Notes |
|---|---|---|
| **Streamlit Community Cloud** | share.streamlit.io → connect this GitHub repo → app file `app.py` | Free, redeploys on push. Easiest. |
| **Hugging Face Spaces** | New Space (Streamlit SDK) → push repo | Free tier fine for this. |
| **Fly.io / Render / Railway** | container from repo, run `streamlit run app.py` | If you want it behind your own auth. |

For **private** data, don't commit `consensus.csv` (it's gitignored). Either
upload it in the app each session, or wire the app to read from your Google
Drive / a private bucket.

## Tabs
- **Overview / Q1–Q10** — the auto-filled answer sheet
- **Factor ranking** — LS Sharpe/CAGR/MDD/NW-t table + equity curve
- **Seasonality** — calendar-month + Feb/May/Aug/Nov vs other
- **1M vs 3M** — the direct horizon test in season months
- **Costs** — cost/borrow sensitivity grid
- **Event-time & FM** — post-earnings drift + Fama-MacBeth
- **Long candidates** — latest top-20 for any factor

## Auto-refresh pipeline (optional)

Your existing Excel→export→GitHub pattern (the "Korean Fear & Greed" session's
`run_export.vbs`) can drop a fresh `consensus.csv` into the repo monthly. Point
the deployed app at that committed file (or a Drive copy) and every push
refreshes the app — a monthly-updating revision-factor dashboard.
