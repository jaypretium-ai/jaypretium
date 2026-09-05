const fs = require("fs");
const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell, HeadingLevel, AlignmentType,
  WidthType, ShadingType, BorderStyle, PageBreak, LevelFormat, PageNumber, Footer, Header, TabStopType,
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

const border = { style: BorderStyle.SINGLE, size: 4, color: "BFBFBF" };
const borders = { top: border, bottom: border, left: border, right: border };
function table(headers, rows, widths, opts = {}) {
  const total = widths.reduce((a, b) => a + b, 0);
  const sz = opts.size || 15;
  const cell = (t, w, hdr, i) => new TableCell({
    width: { size: w, type: WidthType.DXA }, borders,
    shading: hdr ? { fill: NAVY, type: ShadingType.CLEAR, color: "auto" } : (opts.hl && opts.hl(i) ? { fill: "FFF2CC", type: ShadingType.CLEAR, color: "auto" } : undefined),
    margins: { top: 30, bottom: 30, left: 60, right: 60 },
    children: [new Paragraph({ children: [run(String(t ?? ""), { size: sz, bold: hdr, color: hdr ? "FFFFFF" : undefined })], spacing: { after: 0 }, alignment: hdr ? AlignmentType.CENTER : undefined })],
  });
  return new Table({
    width: { size: total, type: WidthType.DXA }, columnWidths: widths,
    rows: [new TableRow({ tableHeader: true, children: headers.map((h, j) => cell(h, widths[j], true)) }),
      ...rows.map((r, i) => new TableRow({ children: r.map((v, j) => cell(v, widths[j], false, i)) }))],
  });
}
const sp = () => p("", { after: 60 });

const n = (k) => D["nm_" + k];
const tierRows = D.tier_table;
const kids = [];

// ---------------- Title ----------------
kids.push(new Paragraph({ children: [run("Billionfold Korea L/S — BBAS 유동성 리밋 기반 종목 유니버스", { size: 30, bold: true, color: NAVY })], spacing: { after: 60 } }));
kids.push(p(`Screening Memo | 데이터 기준일 ${D.asof} (KRX 종가) | 작성 2026-09-05 | 첨부: Korea_Universe_BBAS_${D.asof}.xlsx`, { size: 17, color: "595959", after: 40 }));
kids.push(p("Rule 참고: BBAS Rule.xlsx (2026-07-31), Billionfold Junior Guide (2026-09-05)", { size: 17, color: "595959", after: 160 }));

// ---------------- 0. 결론 ----------------
kids.push(h1("0. 핵심 결론"));
kids.push(bb("유니버스 = ", `${D.n_univ}종목 (KRX 상장 ${D.n_all.toLocaleString()}종목의 ${(D.n_univ / D.n_all * 100).toFixed(0)}%, 시총 커버리지 ${(D.univ_mcap_share * 100).toFixed(0)}%). Tier A1 ${tierRows[0][1]} / A2 ${tierRows[1][1]} / A3 ${tierRows[2][1]} / B(3천억-7천억) ${tierRows[3][1]}.`));
kids.push(bb("실질 운용 유니버스는 더 좁음: ", `500억 Book 기준 6% 풀사이즈(30억)를 3거래일 내 청산 가능한 종목 ${tierRows[4][7]}개, 1,000억 Book(60억)은 ${tierRows[4][8]}개. Stress(ADV -50%) 시 ${D.n_stress500}개.`));
kids.push(bb("특수상황 하이라이트 ", `${D.n_special}종목 (이벤트 태그 ${D.n_event} + 정량 시그널 ${D.n_special - D.n_event}). 엑셀 Universe 시트 노란 배경.`));
kids.push(bb("Mid-cap Alpha(B) bucket의 구조적 제약: ", `${tierRows[3][1]}종목이 후보이나 합산 7% = 500억 Book에서 35억 → 실질 2-3포지션. Korea Special-Sit alpha는 Event Play(10%, 40거래일) 승인 경로 없이는 scale 불가.`));
kids.push(bb("밸류에이션·ROE·ROIC: ", "본 환경에서 Capital IQ/DART 접근 불가 → 엑셀에 CIQ 수식(IFERROR 래핑) 삽입. CIQ 연결 Excel에서 열면 종목별·Tier 평균이 자동 채워짐. 본 메모의 밸류 평균은 미산출(추정치 기재하지 않음)."));
kids.push(bb("시장 regime 주의: ", `유니버스 시총가중 YTD ${(D.capw_ytd * 100).toFixed(0)}%, YTD +100% 이상 ${D.n_ytd100}종목 vs -30% 이하 ${D.n_ytdm30}종목. 대형주 다수가 52주 고점 대비 -30~-50% → 급등 후 급락 regime. 40거래일 내 ±15% 일변동 2회 이상(Short cap -4%) 종목이 유니버스 내 ${D.n_vol15}개(A1에서 ${D.n_vol15_A1}개).`));
kids.push(bb("투자 아이디어 10건 (7장): ", "우선주-보통주 pair 2건, 지주 NAV 2건, spin/merger 3건, PE 공개매수 1건, 저PBR basket 1건, 과열 short screen 1건. 방향·사이징·업사이드/다운사이드 범위·반대논거 포함. 모두 CIQ 밸류 확인 전 '가설' 단계."));

// ---------------- 1. 데이터/방법론 ----------------
kids.push(h1("1. 데이터 · 방법론 · 한계"));
kids.push(bb("가격/거래대금/시총: ", "KRX 전종목시세(FinanceData/marcap, github 일별 갱신), 2025-01-02 ~ " + D.asof + ". 수익률은 KRX 등락률 기반(액면분할·분할재상장 조정), 시총은 최근 20영업일 평균(BBAS 참고: 1개월 평균 시총 적용 가능)."));
kids.push(bb("ADV: ", "min(20D, 60D) 평균 거래대금, 거래정지일 제외. 가이드 5장의 ADV 20% lookback 미확정 → 보수적으로 두 값 중 작은 값."));
kids.push(bb("제외: ", `KONEX ${D.excl["KONEX"]}, SPAC ${D.excl["SPAC"]}, 관리·투자주의환기 ${D.excl["관리/투자주의환기"]}, 거래정지 ${D.excl["거래정지"]}, 시총 3천억 미만 ${D.excl["시총<3000억 (BBAS ⑥)"].toLocaleString()} → 잔여 ${D.excl["(유동성 부족 또는 포함)"]}에 유동성 필터 적용.`));
kids.push(bb("불가/미완 항목: ", "(1) Capital IQ 미접근: 재무·컨센서스 없음. (2) 이벤트 태그는 모델 지식 기반(2026년 중반 이전) → DART 검증 필수. (3) 섹터는 2018 스냅샷(커버리지 75%). (4) 대차 가능 여부·비용 미반영."));

// ---------------- 2. 룰 매핑 ----------------
kids.push(h1("2. BBAS 룰 → 스크린 변수"));
kids.push(table(["BBAS 항목", "원문", "스크린 적용", "500억 Book", "1,000억 Book"], [
  ["② 편입비 제한 1", "±6%", "Position cap = 6% × Book", "30억", "60억"],
  ["③ Event Play", "±10%, 사전승인, 최장 40거래일", "별도 bucket (C tier 편입 경로)", "50억", "100억"],
  ["④ 편입비 제한 3", "시총 1-2위 Long 8%", "삼성전자·SK하이닉스", "40억", "80억"],
  ["⑤ TOP5 합산", "25%", "포트 구성 제약 (스크린 미적용)", "125억", "250억"],
  ["⑥ 시총 구간", "3천억 미만 불가, 3천-7천억 합산 7%", "1M 평균 시총 → Tier C / B", "B 합산 35억", "B 합산 70억"],
  ["Gross-Cut Period", "3거래일, 1일 최소 1/3", "3일 내 청산 = 20%×3일×ADV = 60%×ADV", "ADV ≥ 50억 → 6% OK", "ADV ≥ 100억 → 6% OK"],
  ["ADV 20% (컴플라이언스)", "일일 주문 ADV 20% 이내", "참여율 20% (Params 조정 가능)", "-", "-"],
  ["참고 (Short)", "40거래일 ±15% 2회 → -4%", "Vol15_40D ≥ 2 → Short cap -4%", `${D.n_vol15}종목 해당`, ""],
  ["Stress (가정)", "-", "ADV 50% haircut → 30%×ADV", `6% OK ${D.n_stress500}종목`, ""],
], [1700, 2000, 2500, 1400, 1400]));
kids.push(note("Tier 정의: A1 = 시총≥7천억 & 1,000억 Book 6% 3일 청산 가능 / A2 = 500억 Book만 6% 가능 / A3 = 시총≥7천억이나 2-6%만 가능 / B = 3천-7천억 & ≥2% 가능 / C = Event Play 전용 / X = 제외"));

// ---------------- 3. 결과 ----------------
kids.push(h1("3. 유니버스 결과"));
kids.push(table(["Tier", "#", "중위 시총(억)", "중위 ADV20(억)", "일 회전율", "60D Vol", "YTD 중위", "6% OK @500억", "6% OK @1,000억", "특수상황"], tierRows, [2000, 500, 1000, 1000, 800, 800, 800, 900, 900, 800], { size: 14 }));
sp();
kids.push(p(""));
kids.push(bb("집중도: ", `A1이 유니버스 시총의 ${(D.mcap_share_A1 * 100).toFixed(0)}%, 상위 10종목이 ${(D.top10_share * 100).toFixed(0)}%. 3일 청산 기준 총 gross capacity(Σ MaxPos%NAV) = 500억 Book ${(D.sum_maxpos500 * 100).toFixed(0)}%p / 1,000억 Book ${(D.sum_maxpos1000 * 100).toFixed(0)}%p → Gross 100% 포트는 유동성만으로는 충분히 구성 가능.`));
kids.push(bb("시총 구간별: ", `≥7천억 ${D.bucket["A ≥7000억"][0]}종목 중 ${D.bucket["A ≥7000억"][1]} 편입 / 3천-7천억 ${D.bucket["B 3000-7000억"][0]} 중 ${D.bucket["B 3000-7000억"][1]} / 3천억 미만 ${D.bucket["C <3000억"][0].toLocaleString()} 전부 제외(BBAS ⑥).`));
kids.push(bb("Event-Play 후보(엑셀 Excluded 시트): ", `(A) 시총<3천억이나 ADV20≥30억 ${D.cand.A}종목 — 유동성은 충분하나 룰상 일반 편입 불가. (B) 시총≥7천억이나 ADV 부족 ${D.cand.B}종목 (동서, 하이트진로, HDC, 태광산업, 영풍, SK디스커버리 등 지배구조 이벤트 밀집). (C) 3천-7천억 ADV 부족 ${D.cand.C}종목.`));
kids.push(bb("가이드 예시 검증: ", "500억/40종목/Gross 100% 동일비중(12.5억) → 필요 ADV 20.8억. A1-A2-B 상위 420종목이 충족. 문제는 종목 수가 아니라 Special-Sit 종목이 대부분 B/C tier에 몰려 있다는 점."));

// ---------------- 4. 특수상황 ----------------
kids.push(h1("4. 특수상황(Special Situation) 하이라이트"));
kids.push(note(`이벤트 태그 ${D.n_event}종목 (모델 지식 기반, 검증 필요) + 정량 시그널 ${D.n_special - D.n_event}종목 (거래정지 이력·주식수 급변·신규상장·거래대금 급증·1M 급등락·우선주). 전체 목록은 엑셀 Special_Situations 시트.`));
kids.push(h2("4-1. 이벤트 태그 종목 (시총순)"));
kids.push(table(["종목", "Tier", "유형", "내용 (검증 필요)", "시총(억)", "ADV20(억)", "YTD", "MaxPos@500억"],
  D.special_event.map(r => [r[0], r[2], r[3], r[4], r[5], r[6], r[7], r[8]]), [1250, 450, 1000, 3600, 800, 700, 600, 700], { size: 13 }));
kids.push(h2("4-2. 정량 시그널만 있는 종목 (상위 25, 시총순)"));
kids.push(table(["종목", "Tier", "시그널", "시총(억)", "ADV20(억)", "YTD", "1M"],
  D.special_quant.map(r => [r[0], r[2], r[3], r[4], r[5], r[6], r[7]]), [1300, 500, 4000, 900, 800, 700, 700], { size: 13 }));
kids.push(h2("4-3. 우선주-보통주 괴리율 (우선주 ADV20 ≥ 5억, 괴리 큰 순)"));
kids.push(table(["우선주", "보통주", "괴리율", "우선주 ADV20(억)", "우선주 Tier", "보통주 Tier"], D.prefs, [2000, 1800, 1000, 1400, 1300, 1300], { size: 14 }));
kids.push(note(`${D.n_pref_pairs}쌍 중위 괴리율 ${(D.pref_med_disc * 100).toFixed(0)}%. Pair 전략은 BBAS상 편입비 제한 없음(양 leg 차이 4% 이내), 단 우선주 leg 유동성이 binding.`));
kids.push(h2("4-4. 지주사 상장자회사 커버리지 (지분율 = 근사 입력값, 순차입금·비상장 제외)"));
kids.push(table(["지주", "Tier", "시총(억)", "상장지분가치(억)", "커버리지", "내재 디스카운트", "ADV20(억)"], D.holdco, [1800, 600, 1200, 1400, 1000, 1400, 1000], { size: 14 }));

// ---------------- 5. 밸류에이션 ----------------
kids.push(h1("5. 밸류에이션 · ROE · ROIC · 성장률"));
kids.push(bb("현재 산출 불가: ", "Capital IQ·DART 모두 본 환경에서 차단. 추정치로 채우지 않음."));
kids.push(bb("엑셀 구현: ", "Universe 시트에 종목별 =IFERROR(CIQ(ticker,\"IQ_PE_EXCL\"),\"\") 등 10개 필드(P/E LTM·NTM, P/BV, TEV/EBITDA, ROE, ROIC(Return on Capital), 매출·EPS 1Y 성장률, 배당수익률, 순차입금). Summary 시트에 Tier별 AVERAGEIFS 평균. CIQ 플러그인 Excel에서 열고 Refresh → 즉시 채워짐. Ticker 형식 KOSE:A005930 / KOSDAQ:A247540. mnemonic은 CIQ_Fields 시트에서 Formula Builder로 재확인 권장."));
kids.push(bb("대체 경로: ", "Bloomberg BDP 동등 필드(PE_RATIO, PX_TO_BOOK_RATIO, RETURN_COM_EQY, RETURN_ON_CAP 등) 매핑 제공. CIQ Screening 재현 조건: Korea, KOSE/KOSDAQ, Mkt cap ≥ KRW 300bn, 3M ADV ≥ KRW 1.67bn."));
kids.push(bb("데이터로 산출된 평균(참고): ", `A1 60D 변동성 중위 ${tierRows[0][5]}, B ${tierRows[3][5]} — 개별주 vol 80-95%는 1D 99% VaR -1% 룰 하에서 6% 포지션 자체가 VaR 예산(대략 1D 1σ 5-6% × 6% ≈ 0.3-0.4%p)의 1/3을 소비. 룰상 사이징보다 VaR 사이징이 먼저 binding.`));

// ---------------- 6. 투자 아이디어 ----------------
kids.push(h1("6. 투자 아이디어 (룰 내 실행 가능성 기준)"));
kids.push(note("업사이드/다운사이드는 괴리율·커버리지 등 관측치 기반 시나리오 가정이며 모델링 결과가 아님. 모든 건은 CIQ 밸류·DART 공시 확인 후 사이징."));
const ideas = [
  ["1", "삼성전기우 / 삼성전기", "Long pref / Short common", `괴리율 ${D.disc_009155}. 양 leg A1(우 ADV ${n("009155").adv}억). 보통주 YTD ${n("009150").ytd}로 과열 → 보통주 short leg가 hedge+alpha. 자사주 소각 의무화·배당 확대가 촉매.`, "-63%→-50% 수렴 시 +35% / -70% 확대 시 -19%", "괴리율 수년간 -50~-65% 박스. 촉매 부재 시 carry만. 대차 비용."],
  ["2", "현대차2우B / 현대차", "Long pref / Short common", `괴리율 ${D.disc_005387}, 2우B ADV ${n("005387").adv}억으로 1,000억 Book 6%도 3일 청산. TSR 35% 밸류업·자사주 소각은 우선주에 동일 적용.`, "-52%→-40% +25% / -58% -13%", "2021년 이후 이미 좁혀짐. 추가 수렴 촉매 제한."],
  ["3", "SK스퀘어 / SK하이닉스", "Long holdco / Short sub", `하이닉스 20.1% 지분가치가 스퀘어 시총의 ${D.sq_cov} (내재 디스카운트 45%). 자사주 소각·비핵심 매각 촉매. 스퀘어 ±15%일 ${n("402340").vol15}회 → Short cap -4% 유의.`, "디스카운트 45→35%: +18% / 55%: -18%", "지주 디스카운트 구조적. 하이닉스 랠리 시 스퀘어 lag(저베타)."],
  ["4", "삼성물산 / 삼성 basket", "Long holdco / Short subs", "상장지분 커버리지 2.0x(추정). 지배구조 개편·보험업법·자사주 소각 모두 촉매. YTD +55%로 일부 반영.", "디스카운트 10%p 축소 +15~20% / 개편 지연 -10~15%", "2015년 이후 구조적 디스카운트. '논의'만 반복."],
  ["5", "삼성에피스홀딩스", "Long (or vs 삼성바이오)", `2025-11 분할 신설. YTD ${n("0126Z0").ytd}, 52wH 대비 ${n("0126Z0").h52}. A1(ADV ${n("0126Z0").adv}억). post-spin 수급 정상화 6-12개월 패턴.`, "peer 멀티플 시 +20~30% / 가격경쟁 -20%", "대형 spin에서 post-spin 아노말리 약함. 이미 10개월 경과."],
  ["6", "한화 분할 재상장 / 한화머시너리앤서비스홀딩스", "Monitor → Event Play", `재상장 8영업일. 신설법인 시총 ${n("0220W0").mcap}억, ADV ${n("0220W0").adv}억(B tier). 지수 강제매도 구간. Event Play(10%/40거래일) 대상.`, "강제매도 해소 +15~25% / 승계용 저평가 유지 -15%", "분할 목적이 승계 최적화 → 소액주주 가치와 이해상충."],
  ["7", "롯데렌탈 잔여지분 이벤트", "Event arb (조건부)", `PE 인수 후 YTD ${n("089860").ytd}, 거래대금 ${n("089860").spike}. A3(ADV ${n("089860").adv}억, 6% DTL ${n("089860").dtl6}일). 공개매수 공고 전까지 monitor.`, "프리미엄 10~20% / 무산 시 -20~30%", "이미 +60% 반영. 잔여 upside는 협상 의존."],
  ["8", "HD건설기계 post-merger", "Long", `합병 2026-01 완료. A1(ADV ${n("267270").adv}억), YTD ${n("267270").ytd}. 시너지가 실적으로 확인되는 2-3분기 구간.`, "+20~30% / downcycle -20%", "사이클 산업. 시너지보다 신흥국 수요가 결정."],
  ["9", "저PBR 지주·금융 basket vs K200 선물", "Long basket / Short futures", "2차 상법개정·자사주 소각 의무화·분리과세 수혜. 전 종목 A1. 선물 hedge로 Net 15%·3일 Gross-cut 대응.", "PBR 0.5→0.65x +25~30% / 입법 지연 -10%(hedged)", "3년째 테마. 삼성물산 +55%·SK +113% 이미 반영. 팩터 crowding."],
  ["10", "과열 테마 Short screen (건설·전선)", "Short candidates", `금호건설 YTD ${n("002990").ytd}(±15%일 ${n("002990").vol15}회), 대우건설 ${n("047040").ytd}, 대원전선·가온전선 ±15%일 5회. Short cap -4%. 변동성 감소 후 진입.`, "-30~50% 되돌림 / 테마 연장 -30%", "타이밍 실패 시 Book-cut(-6% DD) 주범. 섹터 ETF/선물 hedge가 룰 친화적."],
];
kids.push(table(["#", "아이디어", "방향", "근거 (데이터)", "Upside / Downside (가정)", "Devil's advocate"], ideas, [300, 1500, 1200, 3300, 1500, 1700], { size: 13 }));
kids.push(h2("6-1. 종합 스탠스"));
kids.push(bb("Long bias: ", "우선주 pair(1,2), 지주 NAV pair(3,4) — 시장 중립 구조라 Net 15% 한도·VaR 예산 소모가 적고 3일 청산 가능. 우선순위 1순위."));
kids.push(bb("Neutral/Monitor: ", "spin/merger(5,6,8), PE 이벤트(7) — 밸류·공시 확인 전까지 사이징 보류. Event Play 승인 프로세스 확정이 선행."));
kids.push(bb("Short: ", "10번은 단독 short보다 pair의 short leg 또는 섹터 hedge로만. 급등주 단독 short은 BBAS VaR 2회 이탈(Gross 30% cut) 리스크가 기대수익 대비 큼."));

// ---------------- 7. Devil's advocate ----------------
kids.push(h1("7. 반대 관점 · 리스크"));
kids.push(bb("유니버스가 넓어 보이는 착시: ", `${D.n_univ}종목 중 실제 Special-Sit alpha가 나오는 B/A3 tier(${Number(tierRows[2][1]) + Number(tierRows[3][1])}종목)는 합산 7% bucket과 2-6% 사이징 제약으로 포트 기여도가 낮음. A1은 사실상 KOSPI 대형주 = 팩터/베타 노출.`));
kids.push(bb("ADV 룰 해석 리스크: ", "20% 참여율·3일이 '주문' 기준인지 '보유' 기준인지, 매수·매도 모두인지 미확정. 보유 기준으로 해석되면 (총 보유 ≤ ADV 20%) A2·A3·B의 대부분이 탈락 → 유니버스가 A1 중심 220종목으로 축소."));
kids.push(bb("데이터 regime: ", `시총가중 YTD ${(D.capw_ytd * 100).toFixed(0)}%에 다수 대형주가 52주 고점 대비 -40~50%. 최근 60일 ADV는 급등락 국면의 과대추정 가능성 → 정상화 시 ADV 30-50% 감소가 base case. Stress 열(ADV -50%)을 실질 기준으로 볼 것.`));
kids.push(bb("이벤트 태그 신뢰도: ", "모델 지식 기반이므로 2026년 중반 이후 완료·무산된 이벤트가 포함될 수 있음. 정량 시그널(거래정지 이력, 주식수 급변, 거래대금 급증)이 데이터로 확인되는 이벤트를 우선 검증."));
kids.push(bb("우선주 pair 반론: ", "괴리율은 2020-26년 대부분 -50~-65%에서 정체. 상법개정에도 우선주 의결권 부재는 불변 → 수렴 촉매는 '자사주 소각 대상에 우선주 포함' 같은 개별 공시에 의존."));
kids.push(bb("지주 NAV 반론: ", "커버리지 1.5-2.0x는 한국 지주에서 정상 범위. 디스카운트 축소보다 자회사 하락이 pair P&L을 지배할 수 있음(hedge ratio 오차)."));

// ---------------- 8. Next steps ----------------
kids.push(h1("8. 다음 단계 · BBAS 미팅 확인사항"));
kids.push(bullet("CIQ 연결 Excel에서 첨부 파일 Refresh → Tier별 평균 P/E·P/BV·ROE·ROIC·성장률 확정, 아이디어 1-9 밸류 검증."));
kids.push(bullet("ADV 20% 룰 lookback(20D/60D), 주문 vs 보유 기준, 매수/매도 적용 범위 확정 → Params 시트 반영."));
kids.push(bullet("Event Play bucket 합산 한도(5-10% 제안)와 승인 SLA 확정 → C tier 후보 " + (D.cand.A + D.cand.B + D.cand.C) + "종목 중 우선 검토 리스트 작성."));
kids.push(bullet("이벤트 태그 " + D.n_event + "종목 DART 공시 대조(공개매수·합병·분할·자사주 소각 진행 여부)."));
kids.push(bullet("대차 가능 종목·비용 확인(pair short leg, 아이디어 1-4, 10)."));
kids.push(bullet("데이터 갱신: build_universe.py → build_xlsx.py 재실행(일별 marcap 갱신 반영). 스크립트는 repo output/ 에 포함."));

const doc = new Document({
  creator: "Billionfold Analyst", title: "Korea Universe under BBAS Liquidity Limits",
  styles: { default: { document: { run: { font: FONT, size: 19 } } } },
  numbering: { config: [{ reference: "bul", levels: [
    { level: 0, format: LevelFormat.BULLET, text: "-", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 360, hanging: 240 } } } },
    { level: 1, format: LevelFormat.BULLET, text: "·", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 720, hanging: 240 } } } },
  ] }] },
  sections: [{
    properties: { page: { size: { width: 11906, height: 16838 }, margin: { top: 1000, bottom: 1000, left: 1100, right: 1100 } } },
    headers: { default: new Header({ children: [p("Billionfold — Korea L/S Universe (BBAS) — " + D.asof, { size: 14, color: "808080", align: AlignmentType.RIGHT })] }) },
    footers: { default: new Footer({ children: [new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ children: [PageNumber.CURRENT], font: FONT, size: 14, color: "808080" })] })] }) },
    children: kids,
  }],
});
Packer.toBuffer(doc).then(buf => { fs.writeFileSync(OUT, buf); console.log("wrote", OUT, buf.length); });
