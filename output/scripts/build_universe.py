"""Build Korean equity universe under Billionfold BBAS liquidity limits.

Data: FinanceData/marcap (KRX daily price/volume/amount/market cap, github, updated daily).
Latest date in file = as-of date. Output: universe.pkl for the Excel/Word builders.
"""
import re
import numpy as np
import pandas as pd

MARCAP_DIR = "/home/user/financedata/marcap/data"
MASTER = "/home/user/financedata/stock_master/stock_master.csv.gz"
OUTDIR = "/tmp/claude-0/-home-user-jaypretium/06541f7f-96c0-5594-af5f-280151700bf4/scratchpad"
EOK = 1e8  # 1억원

# ---------------- parameters (mirrors BBAS rule + guide section 5) ----------------
PART = 0.20        # daily order participation cap (compliance) - guide sec.5
DAYS = 3           # gross-cut period (BBAS 기타: Gross-Cut Period 3거래일)
STRESS = 0.50      # stressed ADV haircut (assumption)
POS_LIMIT = 0.06   # BBAS ② 종목 편입비 제한 1
EVENT_LIMIT = 0.10 # BBAS ③ Event Play
MCAP_MIN = 3000 * EOK   # BBAS ⑥ 3천억 미만 편입 불가
MCAP_MID = 7000 * EOK   # BBAS ⑥ 3천억~7천억 합산 7%
BOOKS = {"500": 500 * EOK, "1000": 1000 * EOK}
MIN_ALPHA_POS = 0.01    # minimum meaningful position (PM 확인: 1%까지 사이징 가능)
DTL = {"core": 3, "alpha": 5, "event": 10}   # sleeve별 청산 목표일수 (Core = Gross-cut 3일 / Alpha 5일 / Event Play 10일)

df = pd.concat([pd.read_parquet(f"{MARCAP_DIR}/marcap-2025.parquet"),
                pd.read_parquet(f"{MARCAP_DIR}/marcap-2026.parquet")])
df = df.sort_values(["Code", "Date"])
asof = df["Date"].max()
dates = np.sort(df["Date"].unique())
print("as of", asof.date(), "n dates", len(dates))

def lastn(n):
    return dates[-n:]

last = df[df["Date"] == asof].set_index("Code")
piv_close = df.pivot(index="Date", columns="Code", values="Close")
piv_amt = df.pivot(index="Date", columns="Code", values="Amount")
piv_mcap = df.pivot(index="Date", columns="Code", values="Marcap")
piv_ret = df.pivot(index="Date", columns="Code", values="ChangesRatio") / 100.0   # KRX daily % (split/spin adjusted)
piv_stk = df.pivot(index="Date", columns="Code", values="Stocks")

# adjusted price index (backward from latest close using KRX daily changes)
ret_f = piv_ret.fillna(0.0)
adj = piv_close.loc[asof] / (1 + ret_f).iloc[::-1].cumprod().iloc[::-1].shift(-1).fillna(1.0)
adj = adj.where(piv_close.notna())

def win(piv, n):
    return piv.loc[lastn(n)]

u = pd.DataFrame(index=last.index)
u["Name"] = last["Name"]
u["Market"] = last["Market"]
u["Dept"] = last["Dept"]
u["Close"] = last["Close"]
u["Stocks"] = last["Stocks"]
u["Mcap"] = last["Marcap"]
u["Mcap_1M"] = win(piv_mcap, 20).mean()

def adv(n):
    w = win(piv_amt, n)
    w = w.where(w > 0)          # trading days only (exclude halts)
    return w.mean()

u["ADV20"] = adv(20)
u["ADV60"] = adv(60)
u["ADV120"] = adv(120)
u["ADV_min"] = u[["ADV20", "ADV60"]].min(axis=1)
u["Halt5"] = (win(piv_amt, 5).fillna(0) == 0).sum()
u["ZeroDays60"] = (win(piv_amt, 60).fillna(0) == 0).sum()
u["Vol15_40D"] = (win(piv_ret, 40).abs() >= 0.15).sum()
u["Vol60_ann"] = win(piv_ret, 60).std() * np.sqrt(252)
u["Turnover_daily"] = u["ADV20"] / u["Mcap"]

def ret(n):
    w = adj.loc[lastn(n + 1)]
    return w.iloc[-1] / w.iloc[0] - 1

u["Ret_1M"] = ret(20)
u["Ret_3M"] = ret(60)
u["Ret_6M"] = ret(120)
u["Ret_12M"] = ret(250)
ytd0 = [d for d in dates if pd.Timestamp(d).year == asof.year][0]
prev_ye = dates[list(dates).index(ytd0) - 1]
u["Ret_YTD"] = adj.loc[asof] / adj.loc[prev_ye] - 1
hi52 = win(adj, 250).max()
lo52 = win(adj, 250).min()
u["Pct_from_52wH"] = u["Close"] / hi52 - 1
u["Pct_from_52wL"] = u["Close"] / lo52 - 1
u["VolSpike"] = u["ADV20"] / u["ADV120"]
u["Days_listed"] = piv_close.notna().sum()
stk_f = (win(piv_stk, 250) / win(piv_stk, 250).shift(1))
u["ShareJump_250D"] = ((stk_f >= 1.3) | (stk_f <= 0.77)).sum()


# ---------------- liquidity stability (12M trough of rolling-20D ADV) & VaR proxy ----------------
amt_pos = piv_amt.where(piv_amt > 0)
roll20 = amt_pos.iloc[-250:].rolling(20, min_periods=15).mean()
u["ADV20_min12M"] = roll20.min().reindex(u.index)
u["ADV_Stability"] = u["ADV20_min12M"] / u["ADV_min"]
u["DailyVol60"] = win(piv_ret, 60).std()
u["VaR99_1D"] = 2.326 * u["DailyVol60"]          # parametric 1D 99% VaR per name (no correlation)
u["MaxPosPct_500_Trough"] = np.minimum(POS_LIMIT, PART * DAYS * u["ADV20_min12M"] / BOOKS["500"])
u["MaxPosPct_1000_Trough"] = np.minimum(POS_LIMIT, PART * DAYS * u["ADV20_min12M"] / BOOKS["1000"])

# ---------------- classification flags ----------------
name = u["Name"].fillna("")
u["Is_SPAC"] = name.str.contains("스팩") | u["Dept"].fillna("").str.contains("SPAC")
u["Is_REIT"] = name.str.contains("리츠") | name.str.contains("인프라")
pref_pat = r".*(우|우B|우C|[0-9]우|우\(전환\))$"
u["Is_Pref"] = name.str.match(pref_pat) & ~name.str.contains("한우|대우|우리|우진|우성|삼우|서우|평우|우주|우신|우양|우원|정우|경우|동우|현우|성우|주우")
u["Is_Foreign"] = u["Dept"].fillna("").str.contains("외국기업") | name.str.contains(r"Reg\.S")
u["Is_Managed"] = u["Dept"].fillna("").str.contains("관리종목|투자주의환기")
u["Is_KONEX"] = u["Market"] == "KONEX"
u["Is_Halted"] = u["Halt5"] >= 3
u["Recent_Halt"] = (~u["Is_Halted"]) & (u["ZeroDays60"] >= 3)
u["New_Listing"] = u["Days_listed"] < 120

# ---------------- sector (FinanceData/stock_master, 2018 snapshot -> partial coverage) ----------------
m = pd.read_csv(MASTER, dtype={"Symbol": str, "Industy_code": str}).drop_duplicates("Symbol").set_index("Symbol")
u["Sector"] = m["Sector"].reindex(u.index)
u["Industry"] = m["Industry"].reindex(u.index)

# ---------------- liquidity limits ----------------
u["MaxPos_Liq"] = PART * DAYS * u["ADV_min"]                 # KRW, 3-day exit at 20% participation
u["MaxPos_Liq_Stress"] = u["MaxPos_Liq"] * STRESS
for k, book in BOOKS.items():
    u[f"MaxPosPct_{k}"] = np.minimum(POS_LIMIT, u["MaxPos_Liq"] / book)
    u[f"MaxPosPct_{k}_Stress"] = np.minimum(POS_LIMIT, u["MaxPos_Liq_Stress"] / book)
    u[f"DTL6_{k}"] = POS_LIMIT * book / (PART * u["ADV_min"])
    u[f"DTL2_{k}"] = MIN_ALPHA_POS * book / (PART * u["ADV_min"])

for sl, d_ in DTL.items():
    for k, book in BOOKS.items():
        u[f"MaxPos_{k}_{sl}"] = np.minimum(POS_LIMIT if sl != "event" else EVENT_LIMIT, PART * d_ * u["ADV_min"] / book)
        u[f"MaxPos_{k}_{sl}_Trough"] = np.minimum(POS_LIMIT if sl != "event" else EVENT_LIMIT, PART * d_ * u["ADV20_min12M"] / book)

def bucket(x):
    if x < MCAP_MIN:
        return "C <3000억"
    if x < MCAP_MID:
        return "B 3000-7000억"
    return "A ≥7000억"

u["Mcap_Bucket"] = u["Mcap_1M"].apply(bucket)

def excl_reason(r):
    if r["Is_KONEX"]:
        return "KONEX"
    if r["Is_SPAC"]:
        return "SPAC"
    if r["Is_Managed"]:
        return "관리/투자주의환기"
    if r["Is_Halted"]:
        return "거래정지"
    if r["Mcap_1M"] < MCAP_MIN:
        return "시총<3000억 (BBAS ⑥)"
    return ""

u["Excl_Reason"] = u.apply(excl_reason, axis=1)

def tier(r):
    """Liquidity class at Book1(500억), Alpha sleeve standard (DTL 5d, 20% participation)."""
    if r["Excl_Reason"] in ("KONEX", "SPAC", "관리/투자주의환기", "거래정지"):
        return "X Excluded"
    if r["Mcap_1M"] < MCAP_MIN:
        return "C <3000억 (BBAS ⑥ 편입불가)"
    a, e = r["MaxPos_500_alpha"], r["MaxPos_500_event"]
    if a >= POS_LIMIT - 1e-9:
        return "L1 Full size (6% @5d)"
    if a >= 0.03:
        return "L2 Mid size (3-6% @5d)"
    if a >= MIN_ALPHA_POS:
        return "L3 Small size (1-3% @5d)"
    if e >= MIN_ALPHA_POS:
        return "L4 Event-only (≥1% @10d)"
    return "X Illiquid (<1% @10d)"

u["Tier"] = u.apply(tier, axis=1)
u["In_Universe"] = u["Tier"].str.match(r"^L[1-4]")
u["Short_Cap"] = np.where(u["Vol15_40D"] >= 2, -0.04, -0.06)

# ---------------- special-situation flags (data-driven) ----------------
flags = []
for code, r in u.iterrows():
    f = []
    if r["Recent_Halt"]:
        f.append("거래정지이력(분할/합병 재상장 추정)")
    if r["ShareJump_250D"] >= 1:
        f.append("주식수 급변(분할/합병/액면/증자)")
    if r["New_Listing"]:
        f.append("신규상장<120일")
    if r["VolSpike"] >= 2.5:
        f.append("거래대금 급증(20D/120D≥2.5x)")
    if r["Vol15_40D"] >= 2:
        f.append("±15%일 2회+ (Short cap -4%)")
    if r["Pct_from_52wH"] <= -0.5:
        f.append("52wH 대비 -50% 이상")
    if r["Ret_1M"] >= 0.5 or r["Ret_1M"] <= -0.3:
        f.append("1M ±30%/50% 급등락")
    if r["Is_Pref"]:
        f.append("우선주")
    if r["Is_Managed"]:
        f.append("관리/환기종목")
    flags.append("; ".join(f))
u["Quant_Flags"] = flags

# ---------------- knowledge-based event tags (as of model knowledge; VERIFY on DART/CIQ) ----------------
K = {
    "010130": ("경영권 분쟁", "고려아연 vs 영풍/MBK 경영권 분쟁·공개매수·자사주 매입 후속. 유상증자/집중투표 등 법적 분쟁 지속 여부 확인"),
    "000670": ("경영권 분쟁", "고려아연 분쟁 상대측. 고려아연 지분가치 vs 시총 괴리"),
    "008930": ("경영권 분쟁", "한미약품그룹 경영권 분쟁(가족·라데팡스 등). 거래대금 급증으로 이벤트 진행 중 시사"),
    "128940": ("경영권 분쟁", "한미사이언스 자회사. 지배구조 정리 시 재평가"),
    "000880": ("분할/재상장", "2026-08 인적분할 후 재상장(한화머시너리앤서비스홀딩스 신설). 승계·구조개편 이벤트"),
    "0220W0": ("분할/신규상장", "한화 분할 신설법인 재상장 8일차. post-spin 수급 왜곡 구간"),
    "012450": ("지배구조/증자", "대규모 유상증자(2025)·그룹 승계 관련. 방산 슈퍼사이클 core"),
    "000150": ("지주/합병", "두산밥캣-두산로보틱스 합병 무산(2024) 이후 재추진 리스크. 두산에너빌리티 지분 NAV 디스카운트"),
    "034020": ("구조개편", "두산 그룹 리밸런싱 핵심. 원전 사이클"),
    "454910": ("합병", "두산밥캣 합병 재추진 가능성. 합병비율 논란 재발 리스크"),
    "241560": ("합병", "두산 구조개편 대상. 저PBR·밸류업 후보"),
    "034730": ("지주/리밸런싱", "SK 그룹 리밸런싱(자회사 매각·합병). 지주 NAV 디스카운트"),
    "402340": ("지주/NAV", "SK하이닉스 지분 NAV 대비 디스카운트. 자사주 소각·주주환원"),
    "017670": ("구조조정", "해킹 사태(2025) 후유증·주주환원 정책"),
    "096770": ("합병/구조조정", "SK E&S 합병 후 SK온 구조조정. 배터리 downcycle"),
    "028260": ("지주/NAV", "삼성전자·삼성바이오 지분 NAV 디스카운트. 지배구조 개편 시나리오"),
    "032830": ("규제", "보험업법 개정 시 삼성전자 지분 매각 리스크/기회"),
    "207940": ("분할", "2025-11 인적분할(삼성에피스홀딩스 신설). post-spin 재평가"),
    "0126Z0": ("분할/신규상장", "삼성바이오로직스 인적분할 신설법인(2025-11). 바이오시밀러 순수 exposure"),
    "005930": ("주주환원", "10조 자사주 매입/소각(2024-25). 우선주 디스카운트"),
    "005380": ("밸류업", "TSR 35% 밸류업·자사주 소각. 지배구조 개편 잠재"),
    "012330": ("지배구조", "현대차그룹 순환출자 해소 시나리오 핵심. 자사주 소각"),
    "086280": ("지배구조", "총수일가 지분 핵심 계열사. 승계 이벤트"),
    "003550": ("지주/NAV", "지주 디스카운트·자사주 소각. 상법개정 수혜"),
    "051910": ("지분매각", "LGES 지분 일부 매각 옵션. 배터리 downcycle"),
    "066570": ("상장자회사", "인도법인 IPO(2025-10) 후 지분가치 재평가"),
    "004990": ("지주/구조조정", "롯데 그룹 유동성·자산매각 구조조정"),
    "011170": ("구조조정", "롯데케미칼 자산매각·구조조정"),
    "089860": ("PE인수/공개매수", "어피너티 인수(2025) 후 잔여지분 공개매수/상폐 가능성. YTD +68%·거래대금 급증"),
    "004170": ("계열분리", "신세계-이마트 계열분리(2025). 자산가치 재평가"),
    "139480": ("계열분리/JV", "알리바바 JV·계열분리. 저PBR"),
    "035720": ("구조조정", "비핵심 계열사 매각·지배구조 이슈"),
    "035420": ("M&A", "두나무 지분교환(NAVER파이낸셜) 딜 진행 여부 확인. 자사주 소각"),
    "105560": ("밸류업", "총주주환원 50%·자사주 소각 core"),
    "055550": ("밸류업", "자사주 소각·주주환원 확대"),
    "086790": ("밸류업", "자사주 소각·주주환원 확대"),
    "316140": ("밸류업/M&A", "동양·ABL생명 인수 후 통합. 자본비율"),
    "138040": ("밸류업", "자사주 소각 모범 사례"),
    "068270": ("합병/자사주", "셀트리온제약 합병 논의·대규모 자사주 소각"),
    "068760": ("합병", "셀트리온 합병 대상 논의"),
    "003490": ("합병/통합", "아시아나 합병(2024-12) 후 통합 시너지·부채"),
    "180640": ("경영권", "아시아나 통합·호반 지분 매입(2025) 경영권 이슈"),
    "020560": ("합병/상폐", "대한항공 자회사 편입. 합병·상폐 일정 확인"),
    "267270": ("합병", "HD현대건설기계+HD현대인프라코어 합병(2026-01 완료). post-merger 시너지"),
    "267250": ("지주/NAV", "조선·전력기기 자회사 NAV 디스카운트"),
    "011200": ("민영화", "산은·해진공 지분 매각(민영화) 이벤트"),
    "030200": ("주주환원", "자사주 소각·현대차 최대주주 구도"),
    "033780": ("행동주의", "FCP 등 행동주의·자사주 소각"),
    "001040": ("지주/승계", "올리브영 IPO/합병·CJ4우(전환) 2029 보통주 전환"),
    "00104K": ("전환우선주", "2029 보통주 전환 예정. 보통주 대비 괴리율 -1%"),
    "010120": ("액면분할", "2026-04 액면분할(5:1). 데이터센터 전력기기 사이클"),
    "018880": ("M&A", "한국앤컴퍼니 인수(2024-25) 후 구조조정·증자"),
    "005490": ("밸류업", "철강 구조조정·자사주 소각"),
    "003240": ("행동주의", "트러스톤 등 행동주의·자사주 이슈. 유동성 낮음"),
    "026960": ("저유동성 우량", "대주주 지분 높고 유동성 낮음"),
    "002990": ("급등/거래대금", "YTD +290%·±15%일 7회. 건설주 테마 과열, Short cap -4%"),
    "047040": ("급등", "YTD +350%. 건설주 테마·중흥그룹"),
    "183300": ("분할/자본변동", "2026 주식수 급변 2회·거래정지 이력. 분할/합병 구조 확인"),
    "036800": ("분할/자본변동", "2026-08 주식수 5배·거래정지 이력. 액면분할/분할 확인"),
    "298040": ("분할", "효성 그룹 계열분리(HS효성) 이후"),
    "004800": ("분할/지주", "효성-HS효성 계열분리. 저유동성"),
    "271560": ("지주구조", "오리온홀딩스 지주 디스카운트"),
    "001800": ("지주/NAV", "오리온 지분 NAV 디스카운트. 저유동성"),
    "005935": ("우선주", "삼성전자 우선주 괴리율 -26%"),
    "005387": ("우선주", "현대차 2우B 괴리율 -52%, 유동성 양호"),
    "009155": ("우선주", "삼성전기 우선주 괴리율 -63%, 유동성 양호"),
    "066575": ("우선주", "LG전자 우선주 괴리율 -63%"),
    "000155": ("우선주", "두산 우선주 괴리율 -64%"),
    "00680K": ("우선주", "미래에셋증권 2우B 괴리율 -68%"),
}
u["Event_Type"] = [K.get(c, ("", ""))[0] for c in u.index]
u["Event_Note"] = [K.get(c, ("", ""))[1] for c in u.index]
u["Is_SpecialSit"] = (u["Event_Type"] != "") | (u["Quant_Flags"] != "")

u = u.reset_index()
u["Ticker_BBG"] = u.apply(lambda r: f"{r['Code']} {'KQ' if r['Market'].startswith('KOSDAQ') else 'KS'} Equity", axis=1)
u["Ticker_CIQ"] = u.apply(lambda r: f"{'KOSDAQ' if r['Market'].startswith('KOSDAQ') else 'KOSE'}:A{r['Code']}", axis=1)
u.attrs["asof"] = str(asof.date())
u.attrs["params"] = dict(PART=PART, DAYS=DAYS, STRESS=STRESS, POS_LIMIT=POS_LIMIT, EVENT_LIMIT=EVENT_LIMIT,
                        MCAP_MIN=MCAP_MIN, MCAP_MID=MCAP_MID, MIN_ALPHA_POS=MIN_ALPHA_POS, DTL=DTL)
u.to_pickle(f"{OUTDIR}/universe.pkl")

# ---------------- pref pairs ----------------
byname = u.set_index("Name")
rows = []
for _, r in u[u["Is_Pref"]].iterrows():
    base = re.sub(r"(2우B|3우B|3우C|4우\(전환\)|1우B|1우|2우|우B|우C|우)$", "", r["Name"])
    if base in byname.index:
        b = byname.loc[base]
        if isinstance(b, pd.DataFrame):
            b = b.iloc[0]
        rows.append(dict(Pref=r["Name"], PrefCode=r["Code"], Common=base, CommonCode=b["Code"],
                         PrefPx=r["Close"], ComPx=b["Close"], Discount=r["Close"] / b["Close"] - 1,
                         PrefMcap=r["Mcap"], PrefADV20=r["ADV20"], ComMcap=b["Mcap"], ComADV20=b["ADV20"],
                         PrefTier=r["Tier"], ComTier=b["Tier"], PrefMaxPos500=r["MaxPosPct_500"], ComMaxPos500=b["MaxPosPct_500"]))
p = pd.DataFrame(rows).sort_values("Discount")
p.to_pickle(f"{OUTDIR}/prefs.pkl")

print(u["Tier"].value_counts())
print("universe", u["In_Universe"].sum(), "special", (u["In_Universe"] & u["Is_SpecialSit"]).sum(), "event-tag", (u["In_Universe"] & (u["Event_Type"] != "")).sum())
print(u[u.Code.isin(["010120", "207940", "000880", "002990", "047040"])][["Name", "Ret_YTD", "Ret_1M", "Pct_from_52wH", "Tier"]])
