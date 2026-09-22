"""데이터 로드.

영풍(000670) 종가와 구리 가격을 일별 DataFrame(date index, 컬럼: yp, cu)으로 반환한다.

온라인 우선순위
  영풍: pykrx -> FinanceDataReader -> yfinance(000670.KS)
  구리: yfinance(HG=F, COMEX $/lb -> $/t) -> FRED(PCOPPUSDM, 월별)
온라인 조회가 모두 실패하면 ./data/ 의 오프라인 CSV(스냅샷)로 자동 대체한다.

오프라인 CSV 출처(2026-09-22 스냅샷)
  data/youngpoong_000670_close.csv : KRX 일별 시세 공개 미러 3종을 이어 붙임.
      2023-01-02~2025-04-07 구간은 2025년 10:1 액면분할 전 가격이므로 /10 으로 조정.
      2025-04-08~2025-08-06 구간은 공개 소스가 없어 결측(gap).
  data/copper_usd_daily.csv : copper_usd_t = COMEX HG=F 종가 x 2204.62 (USD/t), 2021-02-04~2026-02-04.
      이후 구간은 중국 현물(CNY/t, VAT 13% 제외, USDCNY 환산)에 60일 중첩구간 중앙값 비율을 곱해 이어 붙임(splice).
      copper_source 컬럼으로 구분 가능.
"""

from __future__ import annotations

import os
import sys

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(HERE, "data")
YP_CODE = "000670"
LB_PER_T = 2204.62
SPLIT_DATE = pd.Timestamp("2025-04-08")  # 이 날짜 이전 원시 가격은 10:1 분할 조정 대상


def _log(msg: str) -> None:
    print(f"[data] {msg}", file=sys.stderr)


# --------------------------------------------------------------------------- 영풍
def _yp_pykrx(start: str, end: str) -> pd.Series | None:
    try:
        from pykrx import stock
        df = stock.get_market_ohlcv(start.replace("-", ""), end.replace("-", ""),
                                    YP_CODE, adjusted=True)
        if df is None or df.empty:
            return None
        s = df["종가"].astype(float)
        s.index = pd.to_datetime(s.index)
        return s
    except Exception as e:  # noqa: BLE001
        _log(f"pykrx 실패: {e}")
        return None


def _yp_fdr(start: str, end: str) -> pd.Series | None:
    try:
        import FinanceDataReader as fdr
        df = fdr.DataReader(YP_CODE, start, end)
        if df is None or df.empty:
            return None
        s = df["Close"].astype(float)
        s.index = pd.to_datetime(s.index)
        return s
    except Exception as e:  # noqa: BLE001
        _log(f"FinanceDataReader 실패: {e}")
        return None


def _yf(ticker: str, start: str, end: str) -> pd.Series | None:
    try:
        import yfinance as yf
        df = yf.download(ticker, start=start, end=end, progress=False, auto_adjust=True)
        if df is None or df.empty:
            return None
        close = df["Close"]
        if isinstance(close, pd.DataFrame):
            close = close.iloc[:, 0]
        s = close.astype(float).dropna()
        s.index = pd.to_datetime(s.index).tz_localize(None)
        return s
    except Exception as e:  # noqa: BLE001
        _log(f"yfinance({ticker}) 실패: {e}")
        return None


def load_youngpoong_online(start: str, end: str) -> pd.Series | None:
    for fn in (_yp_pykrx, _yp_fdr, lambda a, b: _yf(f"{YP_CODE}.KS", a, b)):
        s = fn(start, end)
        if s is not None and len(s) > 50:
            return s.rename("yp")
    return None


def load_youngpoong_offline() -> pd.Series:
    path = os.path.join(DATA_DIR, "youngpoong_000670_close.csv")
    df = pd.read_csv(path, parse_dates=["date"]).set_index("date").sort_index()
    return df["close"].astype(float).rename("yp")


# --------------------------------------------------------------------------- 구리
def _cu_fred(start: str, end: str) -> pd.Series | None:
    """FRED PCOPPUSDM(IMF 글로벌 구리, USD/t, 월별). 일별로 ffill 하지 않고 월말 기준 반환."""
    try:
        url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id=PCOPPUSDM&cosd={start}&coed={end}"
        df = pd.read_csv(url)
        df.columns = ["date", "cu"]
        df["date"] = pd.to_datetime(df["date"])
        s = pd.to_numeric(df.set_index("date")["cu"], errors="coerce").dropna()
        return s if len(s) else None
    except Exception as e:  # noqa: BLE001
        _log(f"FRED 실패: {e}")
        return None


def load_copper_online(start: str, end: str) -> tuple[pd.Series, str] | None:
    s = _yf("HG=F", start, end)
    if s is not None and len(s) > 50:
        return (s * LB_PER_T).rename("cu"), "COMEX HG=F (USD/t)"
    s = _cu_fred(start, end)
    if s is not None:
        return s.rename("cu"), "FRED PCOPPUSDM (USD/t, monthly)"
    return None


def load_copper_offline() -> pd.Series:
    path = os.path.join(DATA_DIR, "copper_usd_daily.csv")
    df = pd.read_csv(path, parse_dates=["date"]).set_index("date").sort_index()
    return df["copper_usd_t"].astype(float).dropna().rename("cu")


# --------------------------------------------------------------------------- 통합
def load_prices(start: str, end: str | None = None, source: str = "auto") -> tuple[pd.DataFrame, dict]:
    """(df[yp, cu], meta) 반환. df 는 두 시계열의 outer join(일별)."""
    end = end or pd.Timestamp.today().strftime("%Y-%m-%d")
    meta: dict = {}

    yp = cu = None
    if source in ("auto", "online"):
        yp = load_youngpoong_online(start, end)
        cu_r = load_copper_online(start, end)
        if cu_r is not None:
            cu, meta["cu_source"] = cu_r
    if yp is None:
        if source == "online":
            raise RuntimeError("영풍 온라인 조회 실패 (source=online)")
        yp = load_youngpoong_offline()
        meta["yp_source"] = "offline snapshot (data/youngpoong_000670_close.csv)"
    else:
        meta["yp_source"] = "online"
    if cu is None:
        if source == "online":
            raise RuntimeError("구리 온라인 조회 실패 (source=online)")
        cu = load_copper_offline()
        meta["cu_source"] = ("offline snapshot: COMEX HG=F USD/t, spliced with China spot ex-VAT after "
                             "2026-02-04 (data/copper_usd_daily.csv)")

    df = pd.concat([yp, cu], axis=1).sort_index()
    df = df.loc[pd.Timestamp(start):pd.Timestamp(end)]
    meta["start"] = str(df.index.min().date())
    meta["end"] = str(df.index.max().date())
    meta["yp_gaps"] = _gaps(df["yp"].dropna())
    return df, meta


def _gaps(s: pd.Series, min_days: int = 10) -> list[tuple[str, str]]:
    idx = s.index.to_series()
    d = idx.diff().dt.days
    out = []
    for t, days in d[d > min_days].items():
        prev = idx.shift(1)[t]
        out.append((str(prev.date()), str(t.date())))
    return out
