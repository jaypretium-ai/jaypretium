"""
Reporting: dump every result table to CSV + a single Excel workbook, render the
headline charts, and assemble the Q1-Q10 answer sheet from the computed numbers.
"""
from __future__ import annotations

import os

import numpy as np
import pandas as pd

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402


def _per_factor_table(results: dict, book: str) -> pd.DataFrame:
    rows = {}
    for fac, d in results["per_factor"].items():
        rows[fac] = d[book]
    return pd.DataFrame(rows).T


def export_all(results: dict, outdir: str, tag: str = "run") -> dict:
    os.makedirs(outdir, exist_ok=True)
    csv_dir = os.path.join(outdir, "csv")
    os.makedirs(csv_dir, exist_ok=True)
    written = {}

    tables = {
        "ranking": results.get("ranking", pd.DataFrame()),
        "long_only": _per_factor_table(results, "long_only"),
        "long_excess": _per_factor_table(results, "long_excess"),
        "long_short": _per_factor_table(results, "long_short"),
        "subperiods": results.get("subperiods", pd.DataFrame()),
        "cost_sensitivity": results.get("cost_sensitivity", pd.DataFrame()),
        "horizon_compare_season": results.get("horizon_compare_season", pd.DataFrame()),
    }
    if "fama_macbeth" in results:
        tables["fama_macbeth"] = results["fama_macbeth"]
    if isinstance(results.get("sector_neutral"), pd.DataFrame):
        tables["sector_neutral"] = results["sector_neutral"]
    if "event_time" in results and isinstance(results["event_time"], pd.DataFrame):
        tables["event_time"] = results["event_time"]

    # seasonality: season-vs-other summary across factors
    svo_rows = []
    for fac, s in results.get("seasonality", {}).items():
        d = s["season_vs_other"]
        svo_rows.append(
            {
                "factor": fac,
                "season_mean": d["season"]["mean"], "season_t": d["season"]["t_stat"],
                "season_win": d["season"]["win_rate"],
                "other_mean": d["other"]["mean"], "other_t": d["other"]["t_stat"],
                "season_minus_other": d["season_minus_other"],
                "boot_ci_lo": d["boot_ci95"][0], "boot_ci_hi": d["boot_ci95"][1],
                "boot_p_gt0": d["boot_p_diff_gt_0"],
            }
        )
    tables["season_vs_other"] = pd.DataFrame(svo_rows).set_index("factor") if svo_rows else pd.DataFrame()

    # calendar-month mean excess for the best factor by LS Sharpe
    if not results.get("ranking", pd.DataFrame()).empty:
        best = results["ranking"].index[0]
        tables["calendar_month_best"] = results["seasonality"][best]["by_month"]

    for name, df in tables.items():
        if isinstance(df, pd.DataFrame) and not df.empty:
            path = os.path.join(csv_dir, f"{tag}_{name}.csv")
            df.to_csv(path)
            written[name] = path

    # Excel workbook
    xlsx = os.path.join(outdir, f"{tag}_backtest_results.xlsx")
    try:
        with pd.ExcelWriter(xlsx, engine="openpyxl") as xw:
            for name, df in tables.items():
                if isinstance(df, pd.DataFrame) and not df.empty:
                    df.to_excel(xw, sheet_name=name[:31])
        written["xlsx"] = xlsx
    except Exception as e:  # pragma: no cover
        written["xlsx_error"] = str(e)
    return written


def make_charts(results: dict, outdir: str, tag: str = "run") -> list[str]:
    os.makedirs(outdir, exist_ok=True)
    paths = []
    rk = results.get("ranking", pd.DataFrame())
    if rk.empty:
        return paths
    best = rk.index[0]

    # 1) cumulative LS equity for top factors
    fig, ax = plt.subplots(figsize=(9, 5))
    for fac in rk.index[:5]:
        r = results["series"][fac]["ls_net"].dropna()
        eq = (1 + r).cumprod()
        ax.plot(eq.index.to_timestamp(), eq.values, label=fac)
    ax.set_title("Long-Short (net) cumulative growth — top factors [SYNTHETIC if demo]")
    ax.set_ylabel("Growth of 1"); ax.legend(fontsize=8); ax.grid(alpha=0.3)
    p = os.path.join(outdir, f"{tag}_ls_equity.png"); fig.tight_layout(); fig.savefig(p, dpi=110)
    plt.close(fig); paths.append(p)

    # 2) calendar-month bar for best factor
    bm = results["seasonality"][best]["by_month"]
    fig, ax = plt.subplots(figsize=(9, 4))
    colors = ["#c0392b" if m in results["config"].season_months else "#2980b9"
              for m in bm.index]
    ax.bar(bm.index, bm["mean"], color=colors)
    ax.axhline(0, color="k", lw=0.8)
    ax.set_title(f"Mean monthly LS return by calendar month — {best} (red = Feb/May/Aug/Nov)")
    ax.set_xlabel("Month"); ax.set_ylabel("Mean monthly return")
    p = os.path.join(outdir, f"{tag}_seasonality_{best}.png"); fig.tight_layout(); fig.savefig(p, dpi=110)
    plt.close(fig); paths.append(p)

    # 3) factor Sharpe ranking bar
    fig, ax = plt.subplots(figsize=(9, 5))
    rk2 = rk.sort_values("LS_Sharpe")
    ax.barh(rk2.index, rk2["LS_Sharpe"], color="#27ae60")
    ax.set_title("Long-Short Sharpe by factor"); ax.grid(alpha=0.3, axis="x")
    p = os.path.join(outdir, f"{tag}_sharpe_ranking.png"); fig.tight_layout(); fig.savefig(p, dpi=110)
    plt.close(fig); paths.append(p)
    return paths


def _fmt(x, pct=False):
    if x is None or (isinstance(x, float) and not np.isfinite(x)):
        return "n/a"
    return f"{x*100:.2f}%" if pct else f"{x:.2f}"


def answer_sheet(results: dict, synthetic: bool) -> str:
    """Assemble the Q1-Q10 answers from computed numbers (markdown text)."""
    rk = results.get("ranking", pd.DataFrame())
    L = []
    banner = (
        "> ⚠️ SYNTHETIC PLUMBING RUN — numbers below are from generated test data "
        "and are NOT findings about the Korean market. Replace with a real "
        "point-in-time consensus panel (see docs/DATA_GUIDE.md) to get real answers."
        if synthetic else
        "> Results computed from the supplied point-in-time consensus panel."
    )
    L.append(banner + "\n")
    if rk.empty:
        L.append("No factors produced results — check data coverage.")
        return "\n".join(L)

    best = rk.index[0]
    best_row = rk.loc[best]
    # 1M vs 3M
    hz = results.get("horizon_compare_season", pd.DataFrame())

    L.append("## Q1. Does the earnings-revision factor work long-term in Korea?")
    L.append(
        f"Best factor by Long-Short Sharpe: **{best}** "
        f"(LS Sharpe {_fmt(best_row['LS_Sharpe'])}, LS CAGR {_fmt(best_row['LS_CAGR'], True)}, "
        f"NW t {_fmt(best_row['LS_NW_t'])}, MaxDD {_fmt(best_row['LS_MaxDD'], True)}). "
        "Verdict follows the sign/significance of these on YOUR data.\n"
    )

    L.append("## Q2. OP vs NP vs EPS — which is best?")
    fam = {k: rk.loc[k, "LS_Sharpe"] for k in ("OP_1M", "NP_1M", "EPS_1M") if k in rk.index}
    if fam:
        winner = max(fam, key=fam.get)
        L.append("Long-Short Sharpe (1M horizon): "
                 + ", ".join(f"{k}={_fmt(v)}" for k, v in fam.items())
                 + f" → **{winner}**.\n")

    L.append("## Q3. 1M vs 3M — which horizon is stronger?")
    for base in ("OP", "NP", "EPS"):
        a, b = f"{base}_1M", f"{base}_3M"
        if a in rk.index and b in rk.index:
            L.append(f"- {base}: 1M Sharpe {_fmt(rk.loc[a,'LS_Sharpe'])} vs "
                     f"3M {_fmt(rk.loc[b,'LS_Sharpe'])}")
    L.append("")

    L.append("## Q4. Is there Feb/May/Aug/Nov seasonality?")
    svo = results["seasonality"][best]["season_vs_other"]
    L.append(
        f"For {best}: season-month mean {_fmt(svo['season']['mean'], True)} "
        f"(t {_fmt(svo['season']['t_stat'])}) vs other {_fmt(svo['other']['mean'], True)} "
        f"(t {_fmt(svo['other']['t_stat'])}); diff {_fmt(svo['season_minus_other'], True)}, "
        f"bootstrap 95% CI [{_fmt(svo['boot_ci95'][0], True)}, {_fmt(svo['boot_ci95'][1], True)}], "
        f"P(diff>0)={_fmt(svo['boot_p_diff_gt_0'])}.\n"
    )

    L.append("## Q5. Are revisions especially strong right after earnings?")
    if not hz.empty:
        for _, row in hz.iterrows():
            L.append(f"- {row['pair']} (season months): 1M {_fmt(row['1M_mean'], True)} "
                     f"(t {_fmt(row['1M_t'])}) vs 3M {_fmt(row['3M_mean'], True)} "
                     f"(t {_fmt(row['3M_t'])}) → winner {row['winner']}")
    if "event_time" in results and isinstance(results["event_time"], pd.DataFrame) \
            and not results["event_time"].empty:
        L.append("\nEvent-time post-report excess returns (top vs bottom revision):")
        L.append(results["event_time"].to_string(index=False))
    L.append("")

    L.append("## Q6. Does alpha survive sector-neutralization?")
    sn = results.get("sector_neutral")
    if isinstance(sn, pd.DataFrame) and not sn.empty:
        for fac, row in sn.iterrows():
            L.append(f"- {fac}: raw LS Sharpe {_fmt(row.get('raw_LS_Sharpe'))} → "
                     f"sector-neutral {_fmt(row.get('neutral_LS_Sharpe'))} "
                     f"(NW t {_fmt(row.get('neutral_LS_NW_t'))})")
        L.append("If the sector-neutral Sharpe stays clearly positive, the alpha "
                 "is not just a sector bet (e.g. semis).\n")
    else:
        L.append("Provide a `sector` column in `meta` to enable this test.\n")

    L.append("## Q7. Does Long-Short survive costs + borrow?")
    cs = results.get("cost_sensitivity", pd.DataFrame())
    if not cs.empty:
        sub = cs[cs["factor"] == best]
        worst = sub.sort_values("LS_Sharpe").iloc[0] if not sub.empty else None
        if worst is not None:
            L.append(
                f"For {best}, worst-case scenario (long {worst['long_cost_bps']}bp, "
                f"borrow {worst['borrow_annual']:.0%}): LS Sharpe {_fmt(worst['LS_Sharpe'])}; "
                f"shortable-only LS Sharpe {_fmt(worst['LS_Sharpe_shortable_only'])}; "
                f"long-only Sharpe {_fmt(worst['LongOnly_Sharpe'])}.\n"
            )

    L.append("## Q8. Most realistic long-only form?")
    lo = _per_factor_table(results, "long_only")
    if not lo.empty and "Sharpe" in lo.columns:
        blo = lo["Sharpe"].idxmax()
        L.append(f"Highest long-only Sharpe: **{blo}** ({_fmt(lo.loc[blo,'Sharpe'])}), "
                 f"CAGR {_fmt(lo.loc[blo,'CAGR'], True)}, turnover "
                 f"{_fmt(lo.loc[blo,'Turnover']) if 'Turnover' in lo.columns else 'n/a'}.\n")

    L.append("## Q9. Revision + Value vs standalone revision?")
    inter = results.get("interactions", {})
    if "cheap_revision_strategy" in inter:
        crs = inter["cheap_revision_strategy"]
        L.append(f"'Top-20% revision, cheaper half' Sharpe {_fmt(crs.get('Sharpe'))}, "
                 f"CAGR {_fmt(crs.get('CAGR'), True)}. Compare with standalone "
                 f"{best} long-only Sharpe above.")
    if "valuation_2x2_EP" in inter:
        L.append("\n2x2 (revision x cheapness) annualized returns:")
        L.append(inter["valuation_2x2_EP"].to_string())
    if "rev_mom_corr" in inter:
        L.append(f"\nAvg cross-sectional corr(revision, 12-1 momentum) = "
                 f"{_fmt(inter['rev_mom_corr'])} (low ⇒ revision isn't just momentum).")
    if "fama_macbeth" in results:
        fm = results["fama_macbeth"]
        if "REV" in fm.index:
            L.append(f"\nFama-MacBeth: revision slope {_fmt(fm.loc['REV','avg_coef'])} "
                     f"(NW t {_fmt(fm.loc['REV','NW_t'])}) after controlling for "
                     "momentum, size, value.")
    L.append("")

    L.append("## Q10. Current long candidates")
    L.append("Run `run_synthetic_demo.py`/your driver with `dump_latest_longs=True` "
             "to print the most recent month's top-quintile names for the chosen factor. "
             "(On synthetic data these are meaningless tickers.)\n")

    return "\n".join(L)
