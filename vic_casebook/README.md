# VIC Casebook — 성공 패턴 케이스 스터디

Value Investors Club(VIC) 고평가 피치 × 실제 실현 수익률을 결합해 **"왜 쌌고, 무엇이 정상화시켰나"** 기준의
패턴 라이브러리를 만든다. 최종 산출물 후보: 책(패턴별 챕터) / 앱(필터·검색 DB).

## 구조

```
vic_casebook/
├── taxonomy.yaml        # 패턴 12종 정의 (mispricing 원인 / catalyst / kill criteria)
├── cases/               # 케이스 1건 = YAML 1개 (_TEMPLATE.yaml 참고)
├── prices/              # 선택: {ticker}.csv (date,close) 오프라인 가격
├── casebook.py          # 수익률 계산 + 패턴별 집계
├── tests/fixtures/      # 합성 데이터 (엔진 동작 검증용, 실존 종목 아님)
└── output/              # 생성물 (비커밋)
```

## 실행

```bash
pip install -r requirements.txt
python casebook.py
```

가격 소스: `prices/*.csv` → yfinance → 케이스 파일 수동 입력(`price_points`, `dividends_per_share`, `terminal`).
상장폐지·인수 종목(VIC 승자 다수가 해당)은 yfinance에 없으므로 **수동 모드가 필수**다.

## 방법론 원칙 (책의 신뢰도를 결정)

1. **승자만 모으지 말 것** — 패턴별 base rate(전체 피치 중 몇 %가 벤치마크를 이겼나)가 없으면 "패턴"이 아니라 "일화"다.
   상위 평점 피치는 수익과 무관하게 전수 수집 → 그 후 승자 선별.
2. **평점과 수익의 상관을 검증** — 평점이 높을수록 수익이 높은지 자체가 연구 질문. 상관이 약하면 그것도 결론.
3. **수익의 원인 분리** — `outcome.driver_of_return`: thesis / 시장 멀티플 / 운. 이유가 틀린 승리는 패턴 근거에서 제외.
4. **벤치마크 대비** — 절대수익이 아닌 excess CAGR. 2000-07 같은 소형가치 강세장 효과를 걷어내야 한다.
5. **경로 리스크** — MDD/최대 역행폭 기록. 같은 CAGR이라도 -60%를 거친 케이스는 실전에서 보유 불가.
6. **표본<5 패턴은 일반화 금지** (엔진이 경고 출력).

## 저작권 / ToS

- VIC 피치 원문은 작성자·VIC 저작물. **원문 복제·재배포 금지** → 케이스에는 본인 언어 요약 + URL + 짧은 인용만.
- VIC 자동 수집(스크래핑)은 ToS 위반 소지 — 수집은 수동 또는 VIC 측 허락 하에. 상업 출판 전 법률 검토 필요.
- 대안적 차별화: 원문이 아니라 **사후 검증 데이터(수익률·원인 분석·kill criteria)** 가 본 프로젝트의 IP.

## 로드맵

| 단계 | 내용 | 목표 |
|---|---|---|
| 1 | 케이스 30-50건 (패턴당 3-5건), 수동 입력 | 택소노미 검증·수정 |
| 2 | 상위 평점 전수 200-300건 + base rate | 패턴별 hit rate / median excess CAGR |
| 3 | 앱 MVP (Streamlit: 패턴·지역·시총 필터, 케이스 카드) | 내부 툴 |
| 4 | 책: 패턴별 챕터 = 대표 승리 2 + 실패 1 + 체크리스트 | 출판 |
