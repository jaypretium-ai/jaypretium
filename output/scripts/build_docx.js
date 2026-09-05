const fs = require("fs");
const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell, HeadingLevel, AlignmentType,
  WidthType, ShadingType, BorderStyle, LevelFormat, PageNumber, Footer, Header,
} = require("docx");

const D = JSON.parse(fs.readFileSync(__dirname + "/memo_data.json", "utf8"));
const OUT = process.argv[2];
const FONT = { ascii: "Arial", hAnsi: "Arial", eastAsia: "Malgun Gothic", cs: "Arial" };
const NAVY = "1F3864";

const run = (t, o = {}) => new TextRun({ text: t, font: FONT, size: o.size || 19, bold: o.bold, italics: o.italics, color: o.color });
const p = (t, o = {}) => new Paragraph({ children: Array.isArray(t) ? t : [run(t, o)], spacing: { after: o.after ?? 80, before: o.before ?? 0 }, alignment: o.align });
const h1 = (t) => new Paragraph({ heading: HeadingLevel.HEADING_1, children: [run(t, { size: 26, bold: true, color: NAVY })], spacing: { before: 240, after: 100 } });
const h2 = (t) => new Paragraph({ heading: HeadingLevel.HEADING_2, children: [run(t, { size: 21, bold: true, color: NAVY })], spacing: { before: 160, after: 60 } });
const bullet = (t, lvl = 0) => new Paragraph({ numbering: { reference: "bul", level: lvl }, children: Array.isArray(t) ? t : [run(t)], spacing: { after: 40 } });
const bb = (label, rest) => bullet([run(label, { bold: true }), run(rest)]);
const note = (t) => p(t, { size: 16, italics: true, color: "595959", after: 120 });
const pct0 = (x) => (x * 100).toFixed(0) + "%";
const pct1 = (x) => (x * 100).toFixed(1) + "%";

const border = { style: BorderStyle.SINGLE, size: 4, color: "BFBFBF" };
const borders = { top: border, bottom: border, left: border, right: border };
function table(headers, rows, widths, opts = {}) {
  const total = widths.reduce((a, b) => a + b, 0);
  const sz = opts.size || 15;
  const cell = (t, w, hdr) => new TableCell({
    width: { size: w, type: WidthType.DXA }, borders,
    shading: hdr ? { fill: NAVY, type: ShadingType.CLEAR, color: "auto" } : undefined,
    margins: { top: 30, bottom: 30, left: 60, right: 60 },
    children: [new Paragraph({ children: [run(String(t ?? ""), { size: sz, bold: hdr, color: hdr ? "FFFFFF" : undefined })], spacing: { after: 0 }, alignment: hdr ? AlignmentType.CENTER : undefined })],
  });
  return new Table({
    width: { size: total, type: WidthType.DXA }, columnWidths: widths,
    rows: [new TableRow({ tableHeader: true, children: headers.map((h, j) => cell(h, widths[j], true)) }),
      ...rows.map((r) => new TableRow({ children: r.map((v, j) => cell(v, widths[j], false)) }))],
  });
}

const n = (k) => D["nm_" + k];
const T = D.tier_table;
const tn = D.tier_n;
const kids = [];

// ---------------- Title ----------------
kids.push(new Paragraph({ children: [run("Billionfold Korea L/S — BBAS 유동성 리밋 기반 종목 유니버스 (v4)", { size: 30, bold: true, color: NAVY })], spacing: { after: 60 } }));
kids.push(p(`Screening Memo | 데이터 기준일 ${D.asof} (KRX 종가) | 작성 2026-09-05 | 첨부: Korea_Universe_BBAS_${D.asof}.xlsx`, { size: 17, color: "595959", after: 40 }));
kids.push(p("Rule 참고: BBAS Rule.xlsx (2026-07-31), Billionfold Junior Guide (2026-09-05). v4 변경: (1) DART 검증 우선순위 (2) expected alpha vs risk budget (3) 60D 공분산 기반 marginal/component VaR", { size: 17, color: "595959", after: 160 }));

// ---------------- 0. 결론 ----------------
kids.push(h1("0. 핵심 결론"));
kids.push(bb("프레임: ", "BBAS에 ADV 하한 조항 없음. 하드 필터는 시총 3,000억(⑥)뿐. ADV는 유니버스 조건이 아니라 사이징 변수 → MaxPos = min(룰 한도, 참여율 20% × sleeve DTL × ADV / Book). Sleeve: Core/Hedge 3일, Alpha 5일, Event Play 10일(사전승인, 10%)."));
kids.push(bb("유니버스 = ", `${D.n_univ}종목 (시총 ≥ 3,000억 & 제외종목 아님 ${D.n_eligible_mcap} 중 Event sleeve 기준 1% 미만 ${D.n_illiquid} 제외). 시총 커버리지 ${pct0(D.univ_mcap_share)}. 500억 Book·Alpha sleeve 기준: L1 6% 가능 ${tn["L1 Full size (6% @5d)"]} / L2 3-6% ${tn["L2 Mid size (3-6% @5d)"]} / L3 1-3% ${tn["L3 Small size (1-3% @5d)"]} / L4 Event-only ${tn["L4 Event-only (≥1% @10d)"]}.`));
kids.push(bb("v2(3일 전량·2% 하한) 대비: ", `492 → ${D.n_univ}종목. 6% 풀사이즈 가능 종목 329(3일) → ${D.n6_500_alpha}(5일). 1,000억 Book은 6% 가능 ${D.n6_1000_alpha}, 1% 이상 ${D.n1_1000_alpha}. Gross capacity(Σ MaxPos, Alpha) 500억 ${pct0(D.cap_500_alpha)}p / 1,000억 ${pct0(D.cap_1000_alpha)}p.`));
kids.push(bb("포트 레벨 유동성 룰 2개로 종목 하한을 대체: ", "(1) DTL ≤ 3일 포지션 합계 ≥ Gross의 40% → Gross-cut 30%·Book-cut 33%가 겹쳐도 유동 sleeve에서 소화. (2) Trim 트리거: DTL이 목표의 2배를 10거래일 연속 초과 시 축소. PreTrade_Check 시트에 구현."));
kids.push(bb("Stress 실증: ", `12개월 rolling-20D ADV 저점 / 현재 ADV 중위 ${D.med_stab.toFixed(2)}x (${pct0(D.share_stab_lt50)}가 0.5x 미만). 저점 ADV·Alpha 5일 기준 6% 가능 ${D.n6_500_alpha_trough}종목(500억). 진입 사이즈는 min(20D,60D) ADV, 모니터링은 20D — 비대칭 적용 권장.`));
kids.push(bb("VaR (60D 공분산 기준으로 교체): ", `샘플 포트(Gross ${pct0(D.risk.gross)}, pair 중심) 1D 99% VaR = ${pct1(D.risk.port_var99)} — 무상관 가정 ${pct1(D.risk.zero_corr)}, 비분산 합 ${pct1(D.risk.sum_standalone)}. Pair hedge가 잡히면서 VaR가 23% 줄었으나 여전히 -1% 한도의 1.7배. 현 구조 유지 시 한도 내 Gross ≈ ${pct0(D.pt["Gross allowed at VaR limit (linear scale)"])}. 최대 기여는 삼성전기우(단독 leg 기준 포트 VaR의 48%) → pref leg 축소가 가장 효율적인 VaR 절감.`));
kids.push(bb("Expected alpha vs risk budget: ", `아이디어 11건 중 연환산 NAV 기여 ≥ 0.5%p는 ${11 - D.n_ideas_lowroi}건(저PBR basket)뿐. 6% 단일 한도 × E[ret] 2-9%에서 개별 아이디어 기여는 0.1-0.5%p. 500억 Book에서 연 5-8% alpha를 만들려면 동시 15-20건 필요 → 유니버스 폭보다 아이디어 회전율이 binding. 유니버스 ${D.n_lowroi_univ}종목은 MaxPos×30%로도 0.5%p 미만(Research ROI Low).`));
kids.push(bb("DART 검증 우선순위: ", `이벤트 태그 ${D.n_event}종목을 P1 ${D.dart_counts["1"]}(아이디어 사용 또는 actionable+정량 시그널) / P2 ${D.dart_counts["2"]}(actionable이나 시그널 없음 → 종료 가능성) / P3 ${D.dart_counts["3"]}(구조적 테마)로 분류. 확인할 공시 유형과 입력란은 DART_Verify 시트.`));
kids.push(bb("특수상황 하이라이트 ", `${D.n_special}종목 (이벤트 태그 ${D.n_event} + 정량 시그널 ${D.n_special - D.n_event}). 엑셀 Universe 시트 노란 배경.`));
kids.push(bb("밸류에이션·ROE·ROIC: ", "본 환경에서 Capital IQ/DART 접근 불가 → 엑셀에 CIQ 수식(IFERROR 래핑) 삽입. CIQ 연결 Excel에서 열면 종목별·Tier 평균 자동. 추정치 기재하지 않음."));
kids.push(bb("시장 regime: ", `유니버스 시총가중 YTD ${pct0(D.capw_ytd)}, YTD +100% 이상 ${D.n_ytd100}종목 vs -30% 이하 ${D.n_ytdm30}종목. 대형주 다수가 52주 고점 대비 -30~-50%. ±15% 일변동 2회 이상(Short cap -4%) ${D.n_vol15}종목(L1에서 ${D.n_vol15_L1}).`));
kids.push(bb("투자 아이디어 10건 (6장): ", "우선주 pair 2, 지주 NAV 2, spin/merger 3, PE 공개매수 1, 저PBR basket 1, 과열 short screen 1. 모두 CIQ 밸류 확인 전 가설 단계."));

// ---------------- 1. 데이터/방법론 ----------------
kids.push(h1("1. 데이터 · 방법론 · 한계"));
kids.push(bb("가격/거래대금/시총: ", "KRX 전종목시세(FinanceData/marcap, github 일별 갱신), 2025-01-02 ~ " + D.asof + ". 수익률은 KRX 등락률 기반(액면분할·분할재상장 조정). 시총은 최근 20영업일 평균."));
kids.push(bb("ADV: ", "min(20D, 60D) 평균 거래대금, 거래정지일 제외. 12개월 rolling-20D 저점을 stress 값으로 병기."));
kids.push(bb("제외: ", `KONEX ${D.excl["KONEX"]}, SPAC ${D.excl["SPAC"]}, 관리·투자주의환기 ${D.excl["관리/투자주의환기"]}, 거래정지 ${D.excl["거래정지"]}, 시총 3천억 미만 ${D.excl["시총<3000억 (BBAS ⑥)"].toLocaleString()}, Event sleeve 기준 1% 미만 ${D.n_illiquid}.`));
kids.push(bb("불가/미완: ", "(1) Capital IQ 미접근. (2) 이벤트 태그는 모델 지식 기반(2026년 중반 이전) → DART 검증 필수. (3) 섹터 2018 스냅샷(커버리지 75%). (4) 대차 가능 여부·비용 미반영."));

// ---------------- 2. 룰 매핑 ----------------
kids.push(h1("2. BBAS 룰 → 사이징 변수"));
kids.push(table(["BBAS 항목", "원문", "적용", "500억 Book", "1,000억 Book"], [
  ["② 편입비 제한 1", "±6%", "룰 한도 6% × Book", "30억", "60억"],
  ["③ Event Play", "±10%, 사전승인, 최장 40거래일", "Event sleeve: 한도 10%, DTL 10일, exit date", "50억", "100억"],
  ["④ 편입비 제한 3", "시총 1-2위 Long 8%", "삼성전자·SK하이닉스", "40억", "80억"],
  ["⑤ TOP5 합산", "25%", "PreTrade_Check 포트 체크", "125억", "250억"],
  ["⑥ 시총 구간", "3천억 미만 불가, 3천-7천억 합산 7%", "유일한 하드 필터. 1M 평균 시총", "B 합산 35억", "B 합산 70억"],
  ["Gross-Cut Period", "3거래일, 1일 1/3, TOP5 2/3", "Core sleeve DTL 3일 + 유동 sleeve ≥ 40% Gross", "6%: ADV ≥ 50억", "6%: ADV ≥ 100억"],
  ["ADV 20% (컴플라이언스)", "일일 주문 ADV 20%", "참여율 20% → MaxPos = 20% × DTL × ADV / Book", "Alpha 6%: ADV ≥ 30억", "Alpha 6%: ADV ≥ 60억"],
  ["최소 포지션 (PM)", "-", "1% → Alpha: ADV ≥ 5억, Event: ADV ≥ 2.5억", `1%+ ${D.n1_500_alpha} / ${D.n1_500_event}`, `1%+ ${D.n1_1000_alpha} / ${D.n1_1000_event}`],
  ["참고 (Short)", "40거래일 ±15% 2회 → -4%", "Short cap 열", `${D.n_vol15}종목`, ""],
], [1700, 2000, 2700, 1400, 1400]));
kids.push(note("Tier = 500억 Book·Alpha sleeve(5일) 기준 최대 사이즈 구간. L1 ≥6% / L2 3-6% / L3 1-3% / L4 Alpha 1% 미만이나 Event 10일 기준 1% 이상 / X Illiquid 10일 기준 1% 미만"));

// ---------------- 3. 결과 ----------------
kids.push(h1("3. 유니버스 결과"));
kids.push(table(["Tier (Alpha 5d @500억)", "#", "중위 시총(억)", "중위 ADV20(억)", "60D Vol", "YTD 중위", "6% OK Core 3d", "6% OK Alpha 5d", "6% OK Alpha @1,000억", "특수상황"], T, [2100, 500, 1000, 1000, 800, 800, 900, 900, 1000, 800], { size: 14 }));
kids.push(p(""));
kids.push(bb("사이즈 분포(500억 Book): ", `Alpha sleeve 기준 6% 가능 ${D.n6_500_alpha} / 3%+ ${D.n3_500_alpha} / 1%+ ${D.n1_500_alpha}. Event sleeve 기준 1%+ ${D.n1_500_event}. 1,000억 Book은 6% ${D.n6_1000_alpha} / 3%+ ${D.n3_1000_alpha} / 1%+ ${D.n1_1000_alpha}.`));
kids.push(bb("시총 구간: ", `≥7천억 ${D.bucket["A ≥7000억"][0]} 중 ${D.bucket["A ≥7000억"][1]} 편입, 3천-7천억 ${D.bucket["B 3000-7000억"][0]} 중 ${D.bucket["B 3000-7000억"][1]} 편입 (v2 138 → ${D.bucket["B 3000-7000억"][1]}: mid-cap alpha 공간이 실질적으로 열림). 단 합산 7% bucket은 유지 → 500억 Book 35억, 1-2% 포지션 3-5개.`));
kids.push(bb("집중도: ", `L1이 유니버스 시총의 ${pct0(D.mcap_share_L1)}, 상위 10종목 ${pct0(D.top10_share)}. L2-L4 ${tn["L2 Mid size (3-6% @5d)"] + tn["L3 Small size (1-3% @5d)"] + tn["L4 Event-only (≥1% @10d)"]}종목이 Special-Sit 후보의 주 무대이나 개별 1-3%·합산 7%로 포트 기여는 제한.`));
kids.push(bb("시총 3천억 미만: ", `ADV20 ≥ 30억인 종목 ${D.n_small_liquid}개 — 유동성은 충분하나 ⑥으로 편입 불가. 3천억 미만 Event Play 허용 여부(가이드 P7)가 확정되면 Event sleeve로 편입 검토.`));

// ---------------- 4. 특수상황 ----------------
kids.push(h1("4. 특수상황(Special Situation) 하이라이트"));
kids.push(note(`이벤트 태그 ${D.n_event}종목 (모델 지식 기반, 검증 필요) + 정량 시그널 ${D.n_special - D.n_event}종목 (거래정지 이력·주식수 급변·신규상장·거래대금 급증·1M 급등락·우선주). 전체 목록은 엑셀 Special_Situations 시트.`));
kids.push(h2("4-1. 이벤트 태그 종목 (시총순)"));
kids.push(table(["P", "종목", "Tier", "유형", "내용 (검증 필요)", "시총(억)", "ADV20(억)", "YTD", "MaxPos Alpha"],
  D.special_event.map(r => [r[9], r[0], r[2], r[3], r[4], r[5], r[6], r[7], r[8]]), [350, 1200, 400, 1000, 3450, 800, 700, 600, 600], { size: 13 }));
kids.push(note("P = DART 검증 우선순위 (P1 즉시 / P2 종료 여부 먼저 / P3 최근 공시만). 전체 목록·확인 공시 유형·입력란은 DART_Verify 시트."));
kids.push(h2("4-2. 정량 시그널만 있는 종목 (상위 25, 시총순)"));
kids.push(table(["종목", "Tier", "시그널", "시총(억)", "ADV20(억)", "YTD", "1M"],
  D.special_quant.map(r => [r[0], r[2], r[3], r[4], r[5], r[6], r[7]]), [1300, 500, 4000, 900, 800, 700, 700], { size: 13 }));
kids.push(h2("4-3. 우선주-보통주 괴리율 (우선주 ADV20 ≥ 5억, 괴리 큰 순)"));
kids.push(table(["우선주", "보통주", "괴리율", "우선주 ADV20(억)", "우선주 Tier", "보통주 Tier"], D.prefs, [2000, 1800, 1000, 1400, 1300, 1300], { size: 14 }));
kids.push(note(`${D.n_pref_pairs}쌍 중위 괴리율 ${pct0(D.pref_med_disc)}. Pair 전략은 BBAS상 편입비 제한 없음(양 leg 차이 4% 이내), 우선주 leg 유동성이 binding.`));
kids.push(h2("4-4. 지주사 상장자회사 커버리지 (지분율 = 근사 입력값, 순차입금·비상장 제외)"));
kids.push(table(["지주", "Tier", "시총(억)", "상장지분가치(억)", "커버리지", "내재 디스카운트", "ADV20(억)"], D.holdco, [1800, 600, 1200, 1400, 1000, 1400, 1000], { size: 14 }));

// ---------------- 5. 밸류에이션 / stress / VaR ----------------
kids.push(h1("5. 밸류에이션 · Stress · VaR"));
kids.push(bb("밸류에이션·ROE·ROIC: ", "Universe 시트에 종목별 =IFERROR(CIQ(ticker,\"IQ_PE_EXCL\"),\"\") 등 10개 필드(P/E LTM·NTM, P/BV, TEV/EBITDA, ROE, ROIC, 매출·EPS 성장률, 배당수익률, 순차입금). Summary에 Tier별 AVERAGEIFS. CIQ 플러그인 Excel에서 Refresh. Ticker KOSE:A005930 / KOSDAQ:A247540. Bloomberg BDP 매핑은 CIQ_Fields 시트."));
kids.push(h2("5-1. 유동성 Stress 실증 (12개월 ADV 저점)"));
kids.push(table(["Tier", "ADV 저점/현재 (중위)", "해석"], [
  ["L1", D.stab_by_tier["L1 Full size (6% @5d)"].toFixed(2) + "x", "급등락 국면 거래대금 팽창 → 정상화 시 절반"],
  ["L2", D.stab_by_tier["L2 Mid size (3-6% @5d)"].toFixed(2) + "x", "상대적으로 안정"],
  ["L3", D.stab_by_tier["L3 Small size (1-3% @5d)"].toFixed(2) + "x", "원래 거래가 적어 변동 작음"],
  ["L4", D.stab_by_tier["L4 Event-only (≥1% @10d)"].toFixed(2) + "x", "구조적 저유동성. Event exit date 필수"],
], [1200, 2000, 5800], { size: 14 }));
kids.push(bb("적용: ", `저점 ADV 기준 Alpha 6% 가능 ${D.n6_500_alpha_trough}종목, 1%+ ${D.n1_500_alpha_trough}종목(500억). 저점을 편입 기준으로 쓰면 과잉 → 진입 사이즈는 min(20D,60D), 저점은 'Trough' 열로 모니터링·Trim 판단에만 사용.`));
kids.push(h2("5-2. VaR — 60D 공분산 기반 marginal / component VaR"));
kids.push(bb("방법: ", "유니버스 659종목 60D 일수익률 공분산(BBAS 3M 윈도우, Cov 시트 내장). 포트 σ = (w'Σw)^0.5, VaR99 = 2.326σ. Marginal VaR_i = 2.326(Σw)_i/σ, Component VaR_i = w_i × MVaR_i (합 = 포트 VaR). PreTrade_Check에서 임의 포트에 대해 자동 계산. obs<40 신규상장은 중위 분산·무상관 처리."));
kids.push(table(["샘플 포트 (Gross " + pct0(D.risk.gross) + ")", "1D 99% VaR", "vs -1% 한도"], [
  ["비분산 합 (Σ|w|×VaR_i)", pct1(D.risk.sum_standalone), (D.risk.sum_standalone / 0.01).toFixed(1) + "x"],
  ["무상관 (√Σ(w×VaR_i)²)", pct1(D.risk.zero_corr), (D.risk.zero_corr / 0.01).toFixed(1) + "x"],
  ["공분산 기준 (w'Σw)", pct1(D.risk.port_var99), (D.risk.port_var99 / 0.01).toFixed(1) + "x"],
  ["한도 내 Gross (선형 스케일)", pct0(D.pt["Gross allowed at VaR limit (linear scale)"]), "현 구조 유지 시"],
], [3600, 1800, 1800], { size: 14 }));
kids.push(p(""));
kids.push(table(["종목", "w", "Standalone VaR", "Marginal VaR", "Component VaR", "% of VaR"], D.comp_top.concat(D.comp_bottom), [2000, 800, 1300, 1300, 1300, 1000], { size: 13 }));
kids.push(bb("해석: ", "삼성전기우 6%가 포트 VaR의 절반. 보통주 short(-4%, ±15% cap)가 hedge로 잡히지만 60D 창에서 pref/common 상관이 낮아 잔여 VaR가 큼. 현대차 pair는 component가 음수(순 hedge). 무상관 proxy 대비 공분산 VaR가 23% 낮음 = pair hedge benefit이 실제로 존재하나 -1%를 맞추기엔 부족."));
kids.push(bb("시사점: ", "VaR 예산은 종목 수가 아니라 잔여 팩터(pref-common spread, 지주-자회사 spread) 변동성에 의해 소비됨. 60D 창이 급등락 국면이라 과대 추정 가능성 — 250D 창으로 재계산 시 VaR proxy 중위가 11% → 10%로 소폭 하락에 그침. BBAS ②-1 Target Vol 8% 보정이 유일한 완충."));
kids.push(h2("5-3. PreTrade_Check 시트"));
kids.push(bullet("입력: Code / Side / Weight / Sleeve(C·A·E). 종목별: 룰 한도(6/8/10%, Short -4%), sleeve DTL 목표, 다이나믹 한도 = min(룰, 20%×DTL×ADV/Book), DTL, 저점 DTL, Trim 트리거, Gross-cut 30% 시 Day-1 매도액과 ADV 참여율."));
kids.push(bullet("포트: Gross, Net vs Min(10%×Gross,15%), TOP5 ≤ 25%, 3천-7천억 합산 ≤ 7%(Event 제외), Event sleeve 합산, 유동 sleeve(DTL≤3일) ≥ 40%, 다이나믹 한도 초과·Trim 건수, VaR proxy 2종."));

kids.push(h2("5-4. Expected alpha vs risk budget (Alpha_Risk 시트)"));
kids.push(note("Upside/Downside/확률/기간은 가정 입력(파란색). E[ret] = p×up + (1−p)×dn. NAV 기여 p.a. = notional × E[ret] × 12/기간. Solo VaR = 아이디어 단독 공분산 VaR. Research ROI 기준 0.5%p p.a. (Params 조정 가능)."));
kids.push(table(["#", "아이디어", "Notional", "Up", "Dn", "P", "기간", "E[ret]", "NAV p.a.", "Solo VaR", "Comp VaR", "Alpha/VaR", "ROI"], D.ideas_risk.map(r => r.map(String)), [300, 2000, 650, 500, 500, 450, 500, 600, 700, 700, 700, 700, 500], { size: 12 }));
kids.push(bb("결과: ", `11건 중 ROI OK ${11 - D.n_ideas_lowroi}건. 6% 한도에서 pair 아이디어의 연 NAV 기여는 0.3-0.5%p, 단일 3% 포지션은 0.1-0.2%p. 1% Event 포지션(#11)은 0.08%p → 리서치 시간 대비 비효율이 수치로 확인됨.`));
kids.push(bb("Alpha/VaR 관점: ", "저PBR basket(1.06x), 현대차 pair(1.44x), 삼성전기 pair(0.80x)가 상위. SK스퀘어/하이닉스(0.24x)·삼성물산(0.29x)은 spread vol 대비 기대수익이 낮아 사이징 축소 대상. 기준: Alpha p.a./VaR ≥ 1.0x면 리스크 예산 효율적."));
kids.push(bb("Book 운영 함의: ", "연 5-8% NAV alpha 목표라면 동시 15-20건 아이디어 필요 → 파이프라인 회전(월 3-5건 신규)이 핵심 KPI. 유니버스 확대보다 idea velocity와 6% 한도 내 conviction sizing이 성과를 결정."));

// ---------------- 6. 투자 아이디어 ----------------
kids.push(h1("6. 투자 아이디어 (룰 내 실행 가능성 기준)"));
kids.push(note("업사이드/다운사이드는 괴리율·커버리지 등 관측치 기반 시나리오 가정. 모든 건은 CIQ 밸류·DART 공시 확인 후 사이징. Sizing은 500억 Book·sleeve 기준."));
const ideas = [
  ["1", "삼성전기우 / 삼성전기", "Long pref / Short common (A/C)", `괴리율 ${D.disc_009155}. 우 ADV ${n("009155").adv}억 → Alpha 6% OK. 보통주 YTD ${n("009150").ytd} 과열, ±15%일 ${n("009150").vol15}회 → Short cap -4%. 자사주 소각 의무화·배당 확대 촉매.`, "-63%→-50%: +35% / -70%: -19%", "괴리율 수년간 -50~-65% 박스. 촉매 부재 시 carry만."],
  ["2", "현대차2우B / 현대차", "Long pref / Short common (A/C)", `괴리율 ${D.disc_005387}, 2우B ADV ${n("005387").adv}억. TSR 35% 밸류업·자사주 소각 우선주 동일 적용.`, "-52%→-40%: +25% / -58%: -13%", "2021년 이후 이미 좁혀짐."],
  ["3", "SK스퀘어 / SK하이닉스", "Long holdco / Short sub (C/C)", `하이닉스 20.1% 지분가치 = 스퀘어 시총의 ${D.sq_cov}. 스퀘어 ±15%일 ${n("402340").vol15}회 → Short leg 시 -4% cap.`, "45→35%: +18% / 55%: -18%", "지주 디스카운트 구조적. 랠리 시 lag."],
  ["4", "삼성물산 / 삼성 basket", "Long holdco / Short subs (C/C)", "상장지분 커버리지 2.0x(추정). 지배구조·보험업법·자사주 소각 촉매. YTD +55% 일부 반영.", "+15~20% / -10~15%", "2015년 이후 구조적."],
  ["5", "삼성에피스홀딩스", "Long (A)", `2025-11 분할 신설. YTD ${n("0126Z0").ytd}, 52wH 대비 ${n("0126Z0").h52}. ADV ${n("0126Z0").adv}억 → 6% OK.`, "+20~30% / -20%", "대형 spin 아노말리 약함. 10개월 경과."],
  ["6", "한화 분할 / 한화머시너리앤서비스홀딩스", "Event (E)", `재상장 8영업일, 시총 ${n("0220W0").mcap}억, ADV ${n("0220W0").adv}억 → Event 10% OK. 지수 강제매도 구간.`, "+15~25% / -15%", "승계 최적화 목적 → 소액주주와 이해상충."],
  ["7", "롯데렌탈 잔여지분", "Event arb (E, 조건부)", `PE 인수 후 YTD ${n("089860").ytd}, 거래대금 ${n("089860").spike}. ADV ${n("089860").adv}억 → Event ${n("089860").maxpos_ev}, Alpha ${n("089860").maxpos}. 공개매수 공고 전 monitor.`, "+10~20% / -20~30%", "이미 +60% 반영."],
  ["8", "HD건설기계 post-merger", "Long (A)", `합병 2026-01 완료. ADV ${n("267270").adv}억, YTD ${n("267270").ytd}. 시너지 확인 2-3분기.`, "+20~30% / -20%", "사이클 산업."],
  ["9", "저PBR 지주·금융 basket vs K200", "Long basket / Short futures (C)", "2차 상법개정·자사주 소각 의무화 수혜. 전 종목 L1. 선물 hedge로 Net·Gross-cut 대응.", "+25~30% / -10%(hedged)", "3년째 테마, 일부 반영. 팩터 crowding."],
  ["10", "과열 테마 Short screen", "Short (A, -2~-4%)", `금호건설 YTD ${n("002990").ytd}(±15%일 ${n("002990").vol15}회), 대우건설 ${n("047040").ytd}, 대원전선·가온전선 ±15%일 5회.`, "-30~50% / +30%(테마 연장)", "Book-cut 주범. 섹터 hedge가 룰 친화적."],
  ["11", "저유동성 지배구조 (동서·HDC 등)", "Event 1% (E)", `v3에서 신규 편입 가능: 동서 ADV ${n("026960").adv}억 → Event ${n("026960").maxpos_ev}, HDC ADV ${n("012630").adv}억 → ${n("012630").maxpos_ev}. 1% 사이즈로 지배구조 이벤트 대기.`, "이벤트 시 +20~40% / 장기 dead money", "1%는 alpha 기여 0.2-0.4%p. 리서치 시간 대비 비효율."],
];
kids.push(table(["#", "아이디어", "방향 (sleeve)", "근거 (데이터)", "Upside / Downside (가정)", "Devil's advocate"], ideas, [300, 1500, 1300, 3200, 1500, 1700], { size: 13 }));
kids.push(h2("6-1. 종합 스탠스"));
kids.push(bb("Long bias: ", "우선주 pair(1,2), 지주 NAV pair(3,4) — 시장 중립, Net·VaR 소모 적고 Core sleeve로 3일 청산. 1순위."));
kids.push(bb("Neutral/Monitor: ", "spin/merger(5,6,8), PE 이벤트(7), 저유동성 지배구조(11) — 밸류·공시 확인 전 사이징 보류. Event sleeve 합산 한도(5-10%) 확정 선행."));
kids.push(bb("Short: ", "10번은 pair의 short leg 또는 섹터 hedge로만. 급등주 단독 short은 VaR 2회 이탈(Gross 30% cut) 리스크가 기대수익 대비 큼."));

// ---------------- 7. Devil's advocate ----------------
kids.push(h1("7. 반대 관점 · 리스크"));
kids.push(bb("다이나믹 사이징의 procyclicality: ", "이벤트 진입 시점에 거래대금이 부풀어 상한이 관대하게 나오고, 축소 트리거는 거래가 마른 최악 시점에 걸림. 진입은 min(20D,60D), 모니터링은 20D로 비대칭 적용해도 완전히 제거 안 됨."));
kids.push(bb("1% 포지션의 경제성: ", `L3·L4 ${tn["L3 Small size (1-3% @5d)"] + tn["L4 Event-only (≥1% @10d)"]}종목은 1-3%만 가능. 1% 포지션이 +30% 나도 NAV 기여 0.3%p. 리서치 시간은 6% 포지션과 동일 → 유니버스 확대가 곧 alpha 확대는 아님.`));
kids.push(bb("RM 커뮤니케이션: ", "\"ADV ≥ X\"가 \"k × ADV / Book\"보다 설명이 쉬움. 미팅에서는 리서치 하한(Alpha ADV 5억, Event 2.5억)을 소프트 기준으로, 실제 제약은 다이나믹 공식 + 유동 sleeve 40%로 정리."));
kids.push(bb("Book-cut·Gross-cut 중첩: ", "3일에 Gross 40-50% 축소 상황에서 유동 sleeve 40%는 빠듯. sleeve 하한을 50%로 올리면 L2-L4 여지가 줄어듦 — trade-off는 BBAS 미팅에서 Gross Cap 확정 후 결정."));
kids.push(bb("데이터 regime: ", `시총가중 YTD ${pct0(D.capw_ytd)}에 대형주 다수가 고점 대비 -40~50%. ADV·변동성 모두 급등락 국면 값. 정상화 시 ADV 절반(저점 실증 ${D.med_stab.toFixed(2)}x)이 base case.`));
kids.push(bb("이벤트 태그 신뢰도: ", `모델 지식 기반이므로 완료·무산된 이벤트 포함 가능. P2 ${D.dart_counts["2"]}종목은 정량 시그널이 없어 종료 가능성이 높음 — 검증 전 아이디어 사이징 금지.`));
kids.push(bb("공분산 VaR의 한계: ", "60D 창·파라메트릭. 실제 BBAS는 히스토리컬 P&L 기반이라 fat tail(±15%일)에서 차이. Cov 시트는 정적이므로 데이터 갱신 시 build_risk.py 재실행 필요. Alpha_Risk의 E[ret]은 시나리오 가정이며 백테스트 아님."));

// ---------------- 8. Next steps ----------------
kids.push(h1("8. 다음 단계 · BBAS 미팅 확인사항"));
kids.push(bullet(`DART_Verify P1 ${D.dart_counts["1"]}종목 먼저 검증 → 결과 입력 후 아이디어 사이징 확정. P2는 종료 여부만 확인.`));
kids.push(bullet("Alpha_Risk 입력값(up/dn/p/기간)을 CIQ 밸류·공시 확인 후 교체. Alpha/VaR < 0.5x 아이디어는 제외 또는 축소."));
kids.push(bullet("CIQ 연결 Excel에서 Refresh → Tier별 평균 P/E·P/BV·ROE·ROIC·성장률 확정."));
kids.push(bullet("ADV 20% 룰: 주문 vs 보유 기준, lookback, 매수/매도 범위 확정. 보유 기준이면 다이나믹 프레임 자체가 무효 → Params 참여율·DTL 재설정."));
kids.push(bullet("Sleeve DTL(3/5/10일)·유동 sleeve 40%·Event 합산 5-10%를 strategy-specific operating box로 제안. 3천억 미만 Event Play 허용 여부(P7)."));
kids.push(bullet(`이벤트 태그 ${D.n_event}종목 DART 대조. 대차 가능 종목·비용 확인(아이디어 1-4, 10).`));
kids.push(bullet("PreTrade_Check 샘플을 실제 MP로 교체 → 선물 hedge 규모, VaR 예산 대비 Gross 상한, 유동 sleeve 비중 산출."));
kids.push(bullet("데이터 갱신: build_universe.py → build_risk.py → build_xlsx.py → export_memo_data.py → build_docx.js (repo output/scripts)."));

const doc = new Document({
  creator: "Billionfold Analyst", title: "Korea Universe under BBAS Liquidity Limits",
  styles: { default: { document: { run: { font: FONT, size: 19 } } } },
  numbering: { config: [{ reference: "bul", levels: [
    { level: 0, format: LevelFormat.BULLET, text: "-", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 360, hanging: 240 } } } },
    { level: 1, format: LevelFormat.BULLET, text: "·", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 720, hanging: 240 } } } },
  ] }] },
  sections: [{
    properties: { page: { size: { width: 11906, height: 16838 }, margin: { top: 1000, bottom: 1000, left: 1100, right: 1100 } } },
    headers: { default: new Header({ children: [p("Billionfold — Korea L/S Universe (BBAS) v3 — " + D.asof, { size: 14, color: "808080", align: AlignmentType.RIGHT })] }) },
    footers: { default: new Footer({ children: [new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ children: [PageNumber.CURRENT], font: FONT, size: 14, color: "808080" })] })] }) },
    children: kids,
  }],
});
Packer.toBuffer(doc).then(buf => { fs.writeFileSync(OUT, buf); console.log("wrote", OUT, buf.length); });
