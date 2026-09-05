# Korea L/S Universe under BBAS Liquidity Limits (as of 2026-09-03) — v4

v4: (1) DART_Verify 시트 — 이벤트 태그 69종목 검증 우선순위 P1/P2/P3. (2) Alpha_Risk 시트 — 아이디어별 expected alpha(가정 입력) vs Solo/Component VaR, Research ROI. (3) Cov 시트(유니버스 60D 공분산) + PreTrade_Check의 공분산 기반 marginal/component VaR.

v3: ADV 하한 폐지. 유니버스 = 시총 ≥ 3,000억 & Event sleeve(10일) 기준 1%+ 사이징 가능 (659종목). MaxPos = min(룰 한도, 20% × sleeve DTL × ADV / Book), sleeve = Core 3일 / Alpha 5일 / Event 10일. 포트 레벨: 유동 sleeve ≥ 40% Gross, Trim 트리거 DTL > 2× 목표.

Deliverables
- `Korea_Universe_BBAS_2026-09-03.xlsx` — 유니버스(492종목), Tier, 특수상황 하이라이트, PreTrade_Check(모델 포트 BBAS 컴플라이언스·3일 청산·VaR 점검), 우선주 pair, 지주 NAV, 아이디어, 제외/Event-Play 후보, 12M ADV 저점 stress, CIQ 수식 열
- `Korea_Universe_BBAS_Memo_2026-09-03.docx` / `.pdf` — 스크리닝 메모 (결론, 방법론, 룰 매핑, 결과, 특수상황, 밸류 처리, 아이디어, 반대관점, 다음 단계)

Data
- KRX 전종목 시세/거래대금/시총: FinanceData/marcap (github, 일별 갱신), 2025-01-02 ~ 2026-09-03
- 섹터: FinanceData/stock_master (2018 snapshot)
- 재무/밸류에이션: Capital IQ Excel plug-in 수식으로 삽입 (본 환경에서 CIQ/DART 접근 불가)

Rebuild
```
git clone --depth 1 --filter=blob:none --no-checkout https://github.com/FinanceData/marcap /home/user/financedata/marcap
cd /home/user/financedata/marcap && git checkout HEAD -- data/marcap-2025.parquet data/marcap-2026.parquet
git clone --depth 1 https://github.com/FinanceData/stock_master /home/user/financedata/stock_master
pip install pandas pyarrow openpyxl && npm install docx@8
python3 scripts/build_universe.py && python3 scripts/build_risk.py && python3 scripts/build_xlsx.py && python3 scripts/export_memo_data.py && node scripts/build_docx.js Korea_Universe_BBAS_Memo.docx
```
Paths inside the scripts point to the session scratchpad; adjust `OUTDIR`/`MARCAP_DIR` as needed.
