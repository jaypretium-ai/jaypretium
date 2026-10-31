"""VIC 케이스북: 케이스 YAML 로드 → 실현 수익률 계산 → 패턴별 집계 리포트.

가격 소스 우선순위:
  1) prices/{ticker}.csv  (컬럼: date,close  — 배당 반영 수정종가 권장)
  2) yfinance 수정종가     (설치·네트워크 가능 시)
  3) 케이스 파일의 price_points + dividends_per_share + terminal (상장폐지 종목용 수동 모드)

사용:
  python casebook.py                 # cases/*.yaml 전체
  python casebook.py --cases tests/fixtures/cases --prices tests/fixtures/prices
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

HERE = Path(__file__).parent
HORIZONS_Y = (1, 3, 5)
MIN_N = 5  # 패턴별 표본 경고 임계


@dataclass
class Result:
    id: str
    ticker: str
    pattern: str
    direction: str
    rating: float | None
    entry_date: date
    entry_price: float
    exit_date: date
    exit_value: float          # 청산 가치 + 누적 배당 (재투자 없음)
    years: float
    multiple: float
    cagr: float
    bench_cagr: float | None
    max_drawdown: float | None  # 일별 시계열 있을 때만
    source: str
    horizon: dict


def load_cases(case_dir: Path) -> list[dict]:
    cases = []
    for p in sorted(case_dir.glob("*.yaml")):
        if p.name.startswith("_"):
            continue
        with open(p, encoding="utf-8") as f:
            c = yaml.safe_load(f)
        for need in ("id", "ticker", "direction", "vic", "pattern"):
            if need not in c:
                raise ValueError(f"{p.name}: '{need}' 필드 누락")
        cases.append(c)
    return cases


def _to_date(x) -> date:
    return pd.Timestamp(x).date()


def _load_series(ticker: str, price_dir: Path, start: date) -> tuple[pd.Series | None, str]:
    csv = price_dir / f"{ticker}.csv"
    if csv.exists():
        df = pd.read_csv(csv, parse_dates=["date"]).set_index("date").sort_index()
        return df["close"].astype(float), "csv"
    try:
        import yfinance as yf
        df = yf.download(ticker, start=str(start), auto_adjust=True, progress=False)
        if df is not None and not df.empty:
            s = df["Close"].squeeze().astype(float)
            s.index = pd.to_datetime(s.index).tz_localize(None)
            return s, "yfinance"
    except Exception as e:  # noqa: BLE001
        print(f"[price] {ticker}: yfinance 실패 ({type(e).__name__})", file=sys.stderr)
    return None, "none"


def _cagr(multiple: float, years: float) -> float:
    if years <= 0 or multiple <= 0:
        return float("nan") if multiple > 0 else -1.0
    return multiple ** (1 / years) - 1


def _manual_value(c: dict, entry: date, exit_: date, exit_px: float) -> float:
    """수동 모드: 청산가 + (진입~청산 연도) 배당 합. 재투자 없음 → 보수적."""
    divs = c.get("dividends_per_share") or {}
    return exit_px + sum(v for y, v in divs.items() if entry.year <= int(y) <= exit_.year)


def evaluate(c: dict, price_dir: Path) -> Result:
    vic = c["vic"]
    entry_cfg = c.get("entry") or {}
    entry = _to_date(entry_cfg.get("date") or vic["post_date"])
    term = c.get("terminal") or {}
    sign = 1 if c["direction"] == "long" else -1

    series, source = _load_series(c["ticker"], price_dir, entry)
    mdd = None
    horizon: dict[str, float | None] = {}

    if series is not None and len(series) > 1:
        s = series[series.index >= pd.Timestamp(entry)]
        entry_px = float(entry_cfg.get("price") or s.iloc[0])
        exit_date, exit_px = s.index[-1].date(), float(s.iloc[-1])
        if term.get("event") and term.get("value_per_share") is not None:
            exit_date, exit_px = _to_date(term["date"]), float(term["value_per_share"])
        exit_value = exit_px  # 수정종가 → 배당 이미 반영
        path = s / entry_px
        mdd = float((path / path.cummax() - 1).min()) if sign == 1 else None
        for h in HORIZONS_Y:
            t = pd.Timestamp(entry) + pd.DateOffset(years=h)
            horizon[f"{h}y"] = float(s[s.index <= t].iloc[-1] / entry_px - 1) if s.index[-1] >= t else None
    else:
        if "price" not in entry_cfg or not term.get("event"):
            raise ValueError(f"{c['id']}: 시계열 없음 → entry.price 와 terminal 필수")
        source = "manual"
        entry_px = float(entry_cfg["price"])
        exit_date, exit_px = _to_date(term["date"]), float(term["value_per_share"])
        exit_value = _manual_value(c, entry, exit_date, exit_px)
        pts = {_to_date(p["date"]): float(p["price"]) for p in c.get("price_points") or []}
        for h in HORIZONS_Y:
            t = date(entry.year + h, entry.month, min(entry.day, 28))
            near = [d for d in pts if abs((d - t).days) <= 60]
            horizon[f"{h}y"] = (pts[near[0]] + _manual_value(c, entry, near[0], 0)) / entry_px - 1 if near else None

    years = (exit_date - entry).days / 365.25
    multiple = exit_value / entry_px
    if sign == -1:  # 숏: 단순 손익 배수 (차입비용 미반영)
        multiple = 2 - multiple

    bench_cagr = None
    b_series, _ = _load_series(c.get("benchmark", "SPY"), price_dir, entry)
    if b_series is not None:
        b = b_series[(b_series.index >= pd.Timestamp(entry)) & (b_series.index <= pd.Timestamp(exit_date))]
        if len(b) > 1:
            bench_cagr = _cagr(float(b.iloc[-1] / b.iloc[0]), years)

    return Result(
        id=c["id"], ticker=c["ticker"], pattern=c["pattern"]["primary"], direction=c["direction"],
        rating=vic.get("rating"), entry_date=entry, entry_price=entry_px, exit_date=exit_date,
        exit_value=exit_value, years=years, multiple=multiple, cagr=_cagr(multiple, years),
        bench_cagr=bench_cagr, max_drawdown=mdd, source=source, horizon=horizon,
    )


def summarize(results: list[Result]) -> pd.DataFrame:
    df = pd.DataFrame([r.__dict__ for r in results])
    df["excess_cagr"] = df["cagr"] - df["bench_cagr"].astype(float)
    g = df.groupby("pattern")
    out = pd.DataFrame({
        "n": g.size(),
        "cagr_median": g["cagr"].median(),
        "cagr_p25": g["cagr"].quantile(0.25),
        "cagr_p75": g["cagr"].quantile(0.75),
        "hit_rate_excess": g["excess_cagr"].apply(lambda x: (x > 0).mean() if x.notna().any() else np.nan),
        "worst_multiple": g["multiple"].min(),
    })
    out["warning"] = np.where(out["n"] < MIN_N, f"표본<{MIN_N}: 일반화 금지", "")
    return out.sort_values("n", ascending=False)


def _pct(x) -> str:
    return "n/a" if x is None or (isinstance(x, float) and np.isnan(x)) else f"{x * 100:.1f}%"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cases", default=HERE / "cases", type=Path)
    ap.add_argument("--prices", default=HERE / "prices", type=Path)
    ap.add_argument("--out", default=HERE / "output", type=Path)
    a = ap.parse_args()

    results = [evaluate(c, a.prices) for c in load_cases(a.cases)]
    if not results:
        sys.exit("케이스 없음")

    print(f"{'id':<22}{'src':<9}{'entry':>8}{'exit':>9}{'yrs':>6}{'mult':>7}{'CAGR':>8}{'bench':>8}{'1y':>8}{'3y':>8}{'5y':>8}")
    for r in results:
        print(f"{r.id:<22}{r.source:<9}{r.entry_price:>8.2f}{r.exit_value:>9.2f}{r.years:>6.1f}"
              f"{r.multiple:>6.2f}x{_pct(r.cagr):>8}{_pct(r.bench_cagr):>8}"
              + "".join(f"{_pct(r.horizon.get(f'{h}y')):>8}" for h in HORIZONS_Y))

    summ = summarize(results)
    print("\n[패턴별 집계]")
    print(summ.to_string(float_format=lambda v: f"{v:.3f}"))
    a.out.mkdir(exist_ok=True)
    pd.DataFrame([r.__dict__ for r in results]).to_csv(a.out / "case_results.csv", index=False)
    summ.to_csv(a.out / "pattern_summary.csv")


if __name__ == "__main__":
    main()
