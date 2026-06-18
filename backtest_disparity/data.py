"""데이터 로드·정제.

우선순위: pykrx(1순위) -> FinanceDataReader(대체) -> --csv(오프라인).
수정주가(adjusted close)를 사용하며, 2018-05 액면분할(50:1) 반영 여부를 검증한다.
두 종목의 거래일 교집합으로 정렬하고, 결측치는 forward fill 없이 drop 한다.
"""

from __future__ import annotations

import sys
from datetime import datetime

import numpy as np
import pandas as pd

COMMON = "005930"  # 삼성전자 보통주
PREF = "005935"    # 삼성전자 우선주

# 액면분할: 2018-05-04 거래정지 후 2018-05-04 재상장, 50:1.
SPLIT_DATE = pd.Timestamp("2018-05-04")


def _fetch_pykrx(start: str, end: str) -> pd.DataFrame | None:
    """pykrx로 수정종가를 받아 (common, pref) 일별 종가 DataFrame 반환. 실패 시 None."""
    try:
        from pykrx import stock
    except Exception as e:  # noqa: BLE001
        print(f"[data] pykrx 임포트 실패: {e}", file=sys.stderr)
        return None

    s = start.replace("-", "")
    e = end.replace("-", "")
    try:
        # adjusted=True -> 액면분할/배당락 등을 반영한 수정주가
        c = stock.get_market_ohlcv(s, e, COMMON, adjusted=True)
        p = stock.get_market_ohlcv(s, e, PREF, adjusted=True)
    except Exception as ex:  # noqa: BLE001
        print(f"[data] pykrx 조회 실패: {ex}", file=sys.stderr)
        return None
    if c is None or p is None or c.empty or p.empty:
        return None
    df = pd.DataFrame(
        {"common": c["종가"].astype(float), "pref": p["종가"].astype(float)}
    )
    df.index = pd.to_datetime(df.index)
    df.index.name = "date"
    return df


def _fetch_fdr(start: str, end: str) -> pd.DataFrame | None:
    """FinanceDataReader 대체 경로. 실패 시 None."""
    try:
        import FinanceDataReader as fdr
    except Exception as e:  # noqa: BLE001
        print(f"[data] FinanceDataReader 임포트 실패: {e}", file=sys.stderr)
        return None
    try:
        c = fdr.DataReader(COMMON, start, end)
        p = fdr.DataReader(PREF, start, end)
    except Exception as ex:  # noqa: BLE001
        print(f"[data] FDR 조회 실패: {ex}", file=sys.stderr)
        return None
    if c is None or p is None or c.empty or p.empty:
        return None
    df = pd.DataFrame(
        {"common": c["Close"].astype(float), "pref": p["Close"].astype(float)}
    )
    df.index = pd.to_datetime(df.index)
    df.index.name = "date"
    return df


def _load_csv(path: str) -> pd.DataFrame:
    """오프라인 CSV 로더. 필수 컬럼: date, common, pref (discount_pct는 무시·재계산)."""
    df = pd.read_csv(path)
    cols = {c.lower(): c for c in df.columns}
    for need in ("date", "common", "pref"):
        if need not in cols:
            raise ValueError(f"CSV에 '{need}' 컬럼이 필요합니다. 보유 컬럼: {list(df.columns)}")
    out = pd.DataFrame(
        {
            "common": df[cols["common"]].astype(float).values,
            "pref": df[cols["pref"]].astype(float).values,
        },
        index=pd.to_datetime(df[cols["date"]]),
    )
    out.index.name = "date"
    return out


def _verify_split_adjustment(df: pd.DataFrame) -> None:
    """2018 액면분할 구간에서 raw 가격 점프(미수정 데이터)가 있는지 검증·경고.

    수정주가라면 분할 전후로 ~50배 점프가 없어야 한다. 하루 만에 종가가
    절반 이하(또는 2배 이상)로 튀면 데이터 소스가 미조정일 가능성을 경고한다.
    """
    if df.empty:
        return
    win = df.loc[(df.index >= SPLIT_DATE - pd.Timedelta(days=10))
                 & (df.index <= SPLIT_DATE + pd.Timedelta(days=10))]
    if win.empty or len(win) < 2:
        return
    ratio = win["common"].pct_change().abs()
    big = ratio[ratio > 0.6]  # 하루 60% 이상 변동 = 미수정 분할 점프 의심
    if not big.empty:
        print(
            "[data][경고] 2018 액면분할 구간에서 큰 가격 점프 감지 → "
            "데이터가 액면분할 미조정(raw)일 수 있습니다. 수정주가 소스 사용을 확인하세요. "
            f"의심 일자: {[d.date().isoformat() for d in big.index]}",
            file=sys.stderr,
        )
    else:
        print("[data] 액면분할(2018-05) 구간 점프 미검출 → 수정주가로 판단.", file=sys.stderr)


def load_prices(
    start: str,
    end: str | None = None,
    source: str = "auto",
    csv_path: str | None = None,
) -> pd.DataFrame:
    """일별 (common, pref, discount_pct) DataFrame 반환.

    - source: 'auto'(pykrx→fdr), 'pykrx', 'fdr', 'csv'
    - 거래일 교집합(inner join) + dropna(ffill 금지)
    - discount_pct = (common - pref) / common * 100
    """
    if end is None:
        end = datetime.today().strftime("%Y-%m-%d")

    raw: pd.DataFrame | None = None
    if source == "csv" or csv_path:
        if not csv_path:
            raise ValueError("source=csv 인데 --csv 경로가 없습니다.")
        raw = _load_csv(csv_path)
        print(f"[data] CSV 로드: {csv_path} ({len(raw)} rows)", file=sys.stderr)
    elif source == "pykrx":
        raw = _fetch_pykrx(start, end)
    elif source == "fdr":
        raw = _fetch_fdr(start, end)
    else:  # auto
        raw = _fetch_pykrx(start, end)
        if raw is None:
            print("[data] pykrx 실패 → FinanceDataReader로 대체 시도", file=sys.stderr)
            raw = _fetch_fdr(start, end)

    if raw is None or raw.empty:
        raise RuntimeError(
            "데이터를 가져오지 못했습니다. 네트워크에서 KRX/Naver 접근이 차단된 환경일 수 있습니다.\n"
            "  - 로컬(인터넷 가능) 환경에서 실행하거나\n"
            "  - --csv 로 date,common,pref 컬럼의 가격 파일을 직접 제공하세요."
        )

    # 거래일 교집합 정렬 + 결측 drop (forward fill 금지)
    df = raw.sort_index()
    df = df[(df.index >= pd.Timestamp(start)) & (df.index <= pd.Timestamp(end))]
    before = len(df)
    df = df.dropna(subset=["common", "pref"])
    df = df[(df["common"] > 0) & (df["pref"] > 0)]
    dropped = before - len(df)
    if dropped:
        print(f"[data] 결측/비정상 {dropped}행 drop (ffill 미사용)", file=sys.stderr)

    _verify_split_adjustment(df)

    df["discount_pct"] = (df["common"] - df["pref"]) / df["common"] * 100.0
    return df


def save_daily_csv(df: pd.DataFrame, path: str) -> None:
    out = df.reset_index()[["date", "common", "pref", "discount_pct"]].copy()
    out["discount_pct"] = out["discount_pct"].round(4)
    out.to_csv(path, index=False)
    print(f"[data] 일별 시계열 저장: {path} ({len(out)} rows)")
