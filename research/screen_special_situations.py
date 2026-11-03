"""Korea special-situation screen: good fundamentals + growth + low valuation + under-covered.

Reads data produced by the trends-screener app (path = argv[1]).
Outputs research/output/special_screen.csv and a cross-check of the qualitative list.
"""
import os, sys
import numpy as np
import pandas as pd

ROOT = sys.argv[1] if len(sys.argv) > 1 else "/home/user/trends-screener"
D = os.path.join(ROOT, "data")
R = os.path.join(D, "results")
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")
os.makedirs(OUT, exist_ok=True)
z = lambda s: s.astype(str).str.split(".").str[0].str.zfill(6)

# universe + latest market cap
fs = pd.read_csv(os.path.join(R, "factor_scores_latest.csv"), dtype={"ticker": str})
fs["code"] = z(fs["ticker"])
df = fs[["code", "name", "sector", "marcap", "liq", "momentum_score"]].copy()
df["mcap_eok"] = df["marcap"] / 1e8

# CIQ export, rebased to latest market cap
c = pd.read_csv(os.path.join(D, "korea_value_screener.csv"), dtype={"code": str})
c["code"] = z(c["code"])
df = df.merge(c[["code", "PBR", "PER_NTM", "EV_EBITDA_NTM", "EV_Sales_NTM", "PSR_NTM",
                 "FCF_yield", "div_yield", "mktcap_eok", "roic_fy0", "roe_fy0", "sales_g_fy0"]],
              on="code", how="left")
r = (df["mcap_eok"] / df["mktcap_eok"]).where(lambda x: x.between(0.2, 5))
df["px_chg_since_ciq"] = r - 1
ev_old = df["EV_Sales_NTM"] / df["PSR_NTM"] * df["mktcap_eok"]
ev_new = ev_old + (df["mcap_eok"] - df["mktcap_eok"])
df["netcash_pct"] = (df["mcap_eok"] - ev_new) / df["mcap_eok"]          # >0 = net cash
df["ev_ebitda_adj"] = df["EV_EBITDA_NTM"] * ev_new / ev_old
df["per_ntm_adj"] = df["PER_NTM"] * r
df["pbr_adj"] = df["PBR"] * r

# consensus (latest snapshot)
cf = pd.read_parquet(os.path.join(D, "earnings_revision", "consensus_fine.parquet"))
cf = cf[cf["asof"] == cf["asof"].max()].copy()
cf["code"] = z(cf["ticker"]); cf["fy"] = pd.to_datetime(cf["fy_end"]).dt.year
pv = cf.pivot_table(index="code", columns="fy", values=["np_ctrl", "op", "rev"], aggfunc="last")
pv.columns = [f"{a}_{b}" for a, b in pv.columns]
df = df.merge(pv.reset_index(), on="code", how="left")
cp = pd.read_parquet(os.path.join(D, "earnings_revision", "consensus_panel.parquet"))
cp = cp[(cp["asof"] == cp["asof"].max()) & (cp["fiscal"] == "FY1")]
cp["code"] = z(cp["ticker"])
df = df.merge(cp[["code", "n_est", "tp"]], on="code", how="left")
fl = pd.read_csv(os.path.join(D, "earnings_revision", "factor_latest.csv"), dtype={"ticker": str})
fl["code"] = z(fl["ticker"])
df = df.merge(fl[["code", "NP_3M", "OP_3M", "TP_DISPARITY"]], on="code", how="left")
for y in (2026, 2027, 2028):
    df[f"np_{y}"] = df.get(f"np_ctrl_{y}") / 1e8
df["fper_27"] = df["mcap_eok"] / df["np_2027"].where(df["np_2027"] > 0)
df["np_cagr_26_28"] = (df["np_2028"] / df["np_2026"]) ** 0.5 - 1
df.loc[(df["np_2026"] <= 0) | (df["np_2028"] <= 0), "np_cagr_26_28"] = np.nan
df["rev_g_27"] = df.get("rev_2027") / df.get("rev_2026") - 1

# LTM actuals (DART)
cash = pd.read_csv(os.path.join(R, "cashflow.csv"), dtype={"stock_code": str})
cash["code"] = z(cash["stock_code"])
cash = cash.sort_values("year").groupby("code").tail(1)
df = df.merge(cash[["code", "np", "op", "fcf", "sales_growth"]], on="code", how="left")
df["per_ltm"] = df["mcap_eok"] / (df["np"] / 1e8).where(df["np"] > 0)

# events: special situations, insider buying, ownership
ss = pd.read_csv(os.path.join(R, "special_situations.csv"), dtype={"code": str})
ss["code"] = z(ss["code"])
ev = ss.groupby("code").agg(events=("category", lambda s: "|".join(sorted(set(s)))),
                            activist=("activist", "max"), ev_score=("score", "max")).reset_index()
df = df.merge(ev, on="code", how="left")
ins = pd.read_csv(os.path.join(R, "insider_flow_stocks.csv"), dtype={"code": str})
ins["code"] = z(ins["code"])
df = df.merge(ins.groupby("code")["mktcap_ratio"].sum().rename("insider_buy_pct").reset_index(), on="code", how="left")
ms = pd.read_csv(os.path.join(R, "deep_value_major_holder.csv"), dtype={"code": str})
ms["code"] = z(ms["code"])
df = df.merge(ms[["code", "대주주지분", "최대주주명"]], on="code", how="left")

# scoring
def pr(s, asc=True):
    return s.rank(pct=True, ascending=asc)
growth = pd.concat([pr(df["np_cagr_26_28"]), pr(df["rev_g_27"]), pr(df["sales_g_fy0"]),
                    pr(df["sales_growth"])], axis=1).mean(axis=1)
value = pd.concat([pr(df["fper_27"], False), pr(df["per_ntm_adj"], False),
                   pr(df["ev_ebitda_adj"], False), pr(df["per_ltm"], False)], axis=1).mean(axis=1)
quality = pd.concat([pr(df["roe_fy0"]), pr(df["roic_fy0"]), pr(df["FCF_yield"])], axis=1).mean(axis=1)
misund = pd.concat([pr(df["n_est"].fillna(0), False), pr(df["netcash_pct"])], axis=1).mean(axis=1)
catalyst = (df["events"].fillna("").str.contains("주주환원|행동주의|인적분할|경영권분쟁|공개매수|M&A").astype(float) * 0.5
            + df["activist"].fillna(False).astype(float) * 0.3 + (df["insider_buy_pct"] > 0).astype(float) * 0.2
            + (df["NP_3M"] > 0.03).astype(float) * 0.3)
df["score"] = (0.30 * value.fillna(0.3) + 0.30 * growth.fillna(0.3) + 0.20 * quality.fillna(0.3)
               + 0.10 * misund.fillna(0.3) + 0.10 * catalyst.clip(upper=1))

# pattern gate: cheap + growing + profitable, minimal liquidity
cheap = (df["fper_27"] <= 12) | (df["per_ntm_adj"] <= 12) | ((df["per_ltm"] <= 10) & df["fper_27"].isna())
grow = (df["np_cagr_26_28"] >= 0.15) | (df["rev_g_27"] >= 0.15) | (df["sales_g_fy0"] >= 15) | (df["sales_growth"] >= 15)
prof = (df["roe_fy0"] >= 8) | (df["np_2027"] > 0)
liq = df["liq"] >= 3e8  # avg traded value ≥ 3억/day
df["gate"] = cheap & grow & prof & liq
cols = ["code", "name", "sector", "mcap_eok", "score", "fper_27", "per_ntm_adj", "per_ltm", "ev_ebitda_adj",
        "pbr_adj", "netcash_pct", "np_cagr_26_28", "rev_g_27", "sales_g_fy0", "sales_growth", "roe_fy0",
        "FCF_yield", "div_yield", "n_est", "NP_3M", "TP_DISPARITY", "events", "activist", "insider_buy_pct",
        "대주주지분", "px_chg_since_ciq", "gate"]
df = df.sort_values("score", ascending=False)
df[cols].to_csv(os.path.join(OUT, "special_screen_all.csv"), index=False, encoding="utf-8-sig")
df[df["gate"]][cols].to_csv(os.path.join(OUT, "special_screen_pass.csv"), index=False, encoding="utf-8-sig")
print("universe", len(df), "pass", int(df["gate"].sum()))
