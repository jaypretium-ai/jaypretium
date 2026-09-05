"""Risk layer: 60D covariance (BBAS 3M window), component VaR for sample portfolio / ideas, DART verification priority."""
import numpy as np, pandas as pd, json
OUT = "/tmp/claude-0/-home-user-jaypretium/06541f7f-96c0-5594-af5f-280151700bf4/scratchpad"
MARCAP = "/home/user/financedata/marcap/data"
E = 1e8; Z = 2.326
u = pd.read_pickle(f"{OUT}/universe.pkl")
U = u[u.In_Universe].copy()
codes = U.Code.tolist()
df = pd.concat([pd.read_parquet(f"{MARCAP}/marcap-2025.parquet"), pd.read_parquet(f"{MARCAP}/marcap-2026.parquet")])
ret = (df.pivot(index="Date", columns="Code", values="ChangesRatio") / 100.0)[codes]
r60 = ret.iloc[-60:]
obs = r60.notna().sum()
cov = r60.fillna(0.0).cov()           # daily covariance, 60 obs (BBAS 3M window)
# names with < 40 observations (new listings / re-listings): covariance unreliable -> diagonal = tier-median variance, off-diagonal = 0
med_var = float(np.median(np.diag(cov.values)[(obs >= 40).values]))
short = obs[obs < 40].index.tolist()
for c in short:
    cov.loc[c, :] = 0.0; cov.loc[:, c] = 0.0; cov.loc[c, c] = med_var
U["Cov_obs"] = obs.reindex(U.Code).values
U["Cov_flag"] = np.where(U["Cov_obs"] < 40, "obs<40: tier-median var, zero corr", "")
print("short-history names:", short)
cov.to_pickle(f"{OUT}/cov60.pkl")
sig = np.sqrt(np.diag(cov))

# ---- sample portfolio (same as PreTrade sheet)
sample = [("009155", 0.06, "A"), ("009150", -0.04, "C"), ("005387", 0.05, "A"), ("005380", -0.05, "C"), ("402340", 0.04, "C"), ("000660", -0.04, "C"),
          ("028260", 0.04, "C"), ("005930", -0.02, "C"), ("207940", -0.02, "C"), ("0126Z0", 0.03, "A"), ("267270", 0.03, "A"), ("000150", 0.02, "A"),
          ("003550", 0.02, "A"), ("034730", 0.02, "C"), ("105560", 0.02, "C"), ("0220W0", 0.02, "E"), ("089860", 0.02, "E"), ("002990", -0.02, "A"), ("006340", -0.02, "A"), ("241560", 0.02, "A"),
          ("026960", 0.01, "E"), ("012630", 0.01, "E")]
def port_var(weights):
    w = pd.Series(0.0, index=codes)
    for c, x in weights.items():
        w[c] += x
    sw = cov.values @ w.values
    var = float(w.values @ sw); s = np.sqrt(var)
    mvar = Z * sw / s if s > 0 else sw * 0
    comp = w.values * mvar
    standalone = np.abs(w.values) * Z * sig
    return dict(sigma=s, var99=Z * s, mvar=pd.Series(mvar, index=codes), comp=pd.Series(comp, index=codes), standalone=pd.Series(standalone, index=codes), w=w)
pw = {c: x for c, x, _ in sample}
P = port_var(pw)
active = [c for c in codes if pw.get(c, 0) != 0]
tbl = pd.DataFrame({"Code": active, "Name": U.set_index("Code").Name.reindex(active).values, "w": [pw[c] for c in active],
                    "Standalone VaR": P["standalone"][active].values, "Marginal VaR": P["mvar"][active].values, "Component VaR": P["comp"][active].values})
tbl["% of total"] = tbl["Component VaR"] / P["var99"]
tbl["Diversification benefit"] = tbl["Standalone VaR"] - tbl["Component VaR"]
tbl.to_pickle(f"{OUT}/sample_var.pkl")
stats = dict(port_var99=P["var99"], port_sigma=P["sigma"], sum_standalone=float(P["standalone"].sum()),
             zero_corr=float(np.sqrt((P["standalone"] ** 2).sum())), gross=float(sum(abs(x) for x in pw.values())))
print("sample portfolio: VaR99 cov-based %.3f%%  sum standalone %.3f%%  zero-corr %.3f%%" % (stats["port_var99"] * 100, stats["sum_standalone"] * 100, stats["zero_corr"] * 100))
print(tbl.round(4).to_string())

# ---- ideas: legs, weights, expected return assumptions (inputs), horizon
ideas = [
    dict(n=1, name="삼성전기우 / 삼성전기", legs={"009155": 0.06, "009150": -0.04}, up=0.35, dn=-0.19, p=0.50, hz=12, sleeve="A/C"),
    dict(n=2, name="현대차2우B / 현대차", legs={"005387": 0.05, "005380": -0.05}, up=0.25, dn=-0.13, p=0.50, hz=12, sleeve="A/C"),
    dict(n=3, name="SK스퀘어 / SK하이닉스", legs={"402340": 0.04, "000660": -0.04}, up=0.18, dn=-0.18, p=0.55, hz=12, sleeve="C/C"),
    dict(n=4, name="삼성물산 / 삼성 basket", legs={"028260": 0.04, "005930": -0.02, "207940": -0.02}, up=0.175, dn=-0.125, p=0.50, hz=12, sleeve="C/C"),
    dict(n=5, name="삼성에피스홀딩스", legs={"0126Z0": 0.03}, up=0.25, dn=-0.20, p=0.50, hz=9, sleeve="A"),
    dict(n=6, name="한화머시너리앤서비스홀딩스", legs={"0220W0": 0.02}, up=0.20, dn=-0.15, p=0.50, hz=2, sleeve="E"),
    dict(n=7, name="롯데렌탈 (조건부)", legs={"089860": 0.02}, up=0.15, dn=-0.25, p=0.60, hz=6, sleeve="E"),
    dict(n=8, name="HD건설기계", legs={"267270": 0.03}, up=0.25, dn=-0.20, p=0.55, hz=9, sleeve="A"),
    dict(n=9, name="저PBR 지주·금융 basket (선물 hedge 제외)", legs={"000150": 0.02, "003550": 0.02, "034730": 0.02, "105560": 0.02}, up=0.275, dn=-0.10, p=0.50, hz=12, sleeve="C"),
    dict(n=10, name="과열 테마 Short (금호건설·대원전선)", legs={"002990": -0.02, "006340": -0.02}, up=0.40, dn=-0.30, p=0.45, hz=3, sleeve="A"),
    dict(n=11, name="저유동성 지배구조 1% (동서·HDC)", legs={"026960": 0.01, "012630": 0.01}, up=0.30, dn=-0.10, p=0.35, hz=12, sleeve="E"),
]
rows = []
for d in ideas:
    gross = sum(abs(x) for x in d["legs"].values())
    stand = P["standalone"][list(d["legs"])].sum()
    comp = P["comp"][list(d["legs"])].sum()
    solo = port_var(d["legs"])["var99"]
    er = d["p"] * d["up"] + (1 - d["p"]) * d["dn"]                 # expected return on idea notional (long-leg basis)
    notional = max(sum(x for x in d["legs"].values() if x > 0), sum(-x for x in d["legs"].values() if x < 0))
    nav = notional * er; nav_ann = nav * 12 / d["hz"]
    rows.append(dict(n=d["n"], idea=d["name"], sleeve=d["sleeve"], gross=gross, notional=notional, up=d["up"], dn=d["dn"], p=d["p"], hz=d["hz"], er=er, nav=nav, nav_ann=nav_ann,
                     standalone=stand, solo_var=solo, comp=comp, alpha_per_var=nav_ann / solo if solo > 0 else np.nan, alpha_per_comp=nav_ann / comp if comp > 0 else np.nan))
I = pd.DataFrame(rows)
I.to_pickle(f"{OUT}/ideas_risk.pkl")
print(I.round(4).to_string())

# ---- DART verification priority for event-tagged names
actionable = {"경영권 분쟁", "분할/재상장", "분할/신규상장", "분할", "합병", "합병/통합", "합병/상폐", "합병/자사주", "PE인수/공개매수", "M&A", "민영화", "지분매각", "지배구조/증자", "합병/구조조정", "분할/자본변동", "지주/합병", "계열분리", "계열분리/JV", "전환우선주", "액면분할", "규제", "상장자회사", "구조조정", "구조개편", "지주/구조조정", "밸류업/M&A", "급등/거래대금", "급등"}
structural = {"밸류업", "주주환원", "지주/NAV", "우선주", "행동주의", "저유동성 우량", "지주구조", "지주/리밸런싱", "지주/승계", "지배구조", "분할/지주"}
filing = {"경영권 분쟁": "최대주주 변경·5% 보고·주총 소집·공개매수신고서", "분할/재상장": "분할결정·분할종료보고·재상장 완료, 분할비율", "분할/신규상장": "분할 신주 상장·지수 편입 일정", "분할": "분할결정·분할종료보고", "합병": "합병결정·합병종료보고, 합병비율·주식매수청구", "합병/통합": "합병종료보고·통합 시너지 공시", "합병/상폐": "합병·상장폐지 일정", "합병/자사주": "합병 논의 공시·자기주식 소각 결정", "PE인수/공개매수": "공개매수신고서·결과보고서·상장폐지 신청", "M&A": "타법인 주식 취득/처분·주식교환 결정", "민영화": "최대주주 지분 매각 공고", "지분매각": "타법인 주식 처분 결정", "지배구조/증자": "유상증자 결정·납입·최대주주 변경", "합병/구조조정": "자회사 매각·합병 종료", "분할/자본변동": "분할·액면분할·증자 결정 (주식수 변동 원인)", "지주/합병": "합병 재추진 공시", "계열분리": "계열분리 승인·지분 정리", "계열분리/JV": "JV 설립·계열분리", "전환우선주": "전환 조건·일정", "액면분할": "액면분할 완료 확인", "규제": "보험업법 개정 진행", "상장자회사": "자회사 IPO 공시", "구조조정": "자산매각·자회사 매각 결정", "구조개편": "리밸런싱 공시", "지주/구조조정": "자산매각·유동성 확보 공시", "밸류업/M&A": "인수 완료·자본비율", "급등/거래대금": "조회공시 답변·유상증자·대주주 매도", "급등": "조회공시 답변·대주주 매도",
          "밸류업": "밸류업 공시·자기주식 소각 결정", "주주환원": "자기주식 취득/소각 결정", "지주/NAV": "자기주식 소각·자회사 지분 변동", "우선주": "배당 결정·우선주 소각 포함 여부", "행동주의": "주주제안·주총 안건", "저유동성 우량": "대주주 지분 변동", "지주구조": "지주 전환·지분 변동", "지주/리밸런싱": "자회사 매각·합병 공시", "지주/승계": "합병·IPO 공시", "지배구조": "자기주식 소각·순환출자 해소 공시", "분할/지주": "계열분리 완료"}
idea_map = {}
for d in ideas:
    for c in d["legs"]:
        idea_map.setdefault(c, []).append(str(d["n"]))
rows = []
for _, r in U[U.Event_Type != ""].iterrows():
    sig_ = []
    if r.VolSpike >= 1.5: sig_.append(f"거래대금 {r.VolSpike:.1f}x")
    if r.Recent_Halt: sig_.append("거래정지 이력")
    if r.ShareJump_250D >= 1: sig_.append("주식수 급변")
    if r.New_Listing: sig_.append("신규상장")
    if abs(r.Ret_1M) >= 0.15: sig_.append(f"1M {r.Ret_1M:+.0%}")
    corro = len(sig_) > 0
    in_idea = r.Code in idea_map
    et = r.Event_Type
    if in_idea or (et in actionable and corro):
        pr = 1
    elif et in actionable:
        pr = 2
    else:
        pr = 3
    completed = any(k in r.Event_Note for k in ["2024", "2025", "완료", "무산", "이후"])
    note = []
    if in_idea: note.append("아이디어 #" + "/".join(idea_map[r.Code]))
    if completed: note.append("과거 시점 이벤트 → 완료/무산 여부·후속 이벤트 확인")
    if not corro and et in actionable: note.append("정량 시그널 없음 → 이벤트 종료 가능성")
    rows.append(dict(Priority=pr, Code=r.Code, Name=r.Name, Tier=r.Tier.split(" ")[0], Event_Type=et, Event_Note=r.Event_Note, Signals="; ".join(sig_), Idea="/".join(idea_map.get(r.Code, [])),
                     Filing=filing.get(et, "최근 주요사항보고서"), Flag="; ".join(note), Mcap=r.Mcap / E, ADV20=r.ADV20 / E, MaxPos=r.MaxPos_500_alpha))
Dv = pd.DataFrame(rows).sort_values(["Priority", "Mcap"], ascending=[True, False])
Dv.to_pickle(f"{OUT}/dart_verify.pkl")
print(Dv.Priority.value_counts().sort_index().to_dict())
stats["dart_p"] = {int(k): int(v) for k, v in Dv.Priority.value_counts().items()}
# universe research-ROI columns
u.loc[U.index, "Cov_obs"] = U["Cov_obs"]; u.loc[U.index, "Cov_flag"] = U["Cov_flag"]
u.to_pickle(f"{OUT}/universe.pkl")
U["NAV_impact_30"] = U.MaxPos_500_alpha * 0.30
U["VaR_at_MaxPos"] = U.MaxPos_500_alpha * U.VaR99_1D
stats["n_lowroi"] = int((U.NAV_impact_30 < 0.005).sum())
json.dump(stats, open(f"{OUT}/risk_stats.json", "w"), indent=1)
print(stats)
