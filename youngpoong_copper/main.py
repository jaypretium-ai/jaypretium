"""엔트리포인트.

예) python main.py --start 2023-01-01
    python main.py --source offline           # 네트워크 없이 스냅샷으로 실행

온라인(pykrx/FDR/yfinance) 실패 시 ./data/ 오프라인 스냅샷으로 자동 대체.
결과: ./output/*.png, ./output/summary.txt, ./output/monthly.csv
"""

from __future__ import annotations

import argparse
import os
import sys

import pandas as pd

import analysis as an
import data as data_mod
import plots as plots_mod

HERE = os.path.dirname(os.path.abspath(__file__))
OUTDIR = os.path.join(HERE, "output")


def parse_args(argv=None):
    p = argparse.ArgumentParser(description="영풍(000670) 주가 vs 구리 가격: 수준 + YoY 차트")
    p.add_argument("--start", default="2023-01-01")
    p.add_argument("--end", default=None)
    p.add_argument("--source", choices=["auto", "online", "offline"], default="auto")
    p.add_argument("--outdir", default=OUTDIR)
    p.add_argument("--no-plots", action="store_true")
    return p.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    os.makedirs(args.outdir, exist_ok=True)

    # YoY 계산을 위해 시작일 1년 전부터 로드한 뒤, 출력은 --start 이후로 자른다
    warm_start = (pd.Timestamp(args.start) - pd.Timedelta(days=370)).strftime("%Y-%m-%d")
    full, meta = data_mod.load_prices(warm_start, args.end, source=args.source)
    start = pd.Timestamp(args.start)
    daily = full.loc[start:].copy()
    meta["start"] = str(daily.index.min().date())
    meta["yp_gaps"] = [g for g in meta["yp_gaps"] if pd.Timestamp(g[1]) >= start]
    indexed = an.rebase(daily.ffill(limit=5)).where(daily.notna())  # gap 구간은 NaN 유지
    m_full = an.monthly(full)
    yo_m = pd.DataFrame({c: an.yoy(m_full[c], 12) for c in m_full.columns}).loc[start:]
    m = m_full.loc[start:]
    yo_d = an.daily_yoy(full).loc[start:]
    stats = an.summary_stats(daily, m)

    lines = []
    lines.append(f"기간: {meta['start']} ~ {meta['end']}")
    lines.append(f"영풍 소스: {meta['yp_source']}")
    lines.append(f"구리 소스: {meta['cu_source']}")
    if meta.get("yp_gaps"):
        lines.append("영풍 결측 구간: " + ", ".join(f"{a}~{b}" for a, b in meta["yp_gaps"]))
    lines.append("")
    lines.append(f"영풍 최근 종가: {stats['yp_last']:,.0f} KRW ({stats['yp_last_date']})  "
                 f"YoY {stats['yp_yoy_pct']:+.1f}%  YTD {stats['yp_ytd_pct']:+.1f}%  "
                 f"고점 {stats['yp_max']:,.0f} ({stats['yp_max_date']})  저점 {stats['yp_min']:,.0f} ({stats['yp_min_date']})")
    lines.append(f"구리 최근: {stats['cu_last']:,.0f} USD/t ({stats['cu_last_date']})  "
                 f"YoY {stats['cu_yoy_pct']:+.1f}%  YTD {stats['cu_ytd_pct']:+.1f}%  "
                 f"고점 {stats['cu_max']:,.0f} ({stats['cu_max_date']})  저점 {stats['cu_min']:,.0f} ({stats['cu_min_date']})")
    lines.append("")
    lines.append(f"상관계수 (일별 로그수익률): {stats['corr_daily_logret']:.2f}  (n={stats['n_daily']})")
    lines.append(f"상관계수 (월별 로그수익률): {stats['corr_monthly_logret']:.2f}")
    lines.append(f"상관계수 (월별 YoY):       {stats['corr_yoy']:.2f}")
    lines.append(f"베타 (월별, 영풍 on 구리):  {stats['beta_monthly']:.2f}")
    lines.append("")
    lines.append("월말 YoY (%):")
    tbl = yo_m.dropna(how="all").round(1)
    tbl.index = tbl.index.strftime("%Y-%m")
    lines.append(tbl.rename(columns={"yp": "영풍", "cu": "구리"}).to_string())
    text = "\n".join(lines)
    print(text)
    with open(os.path.join(args.outdir, "summary.txt"), "w", encoding="utf-8") as f:
        f.write(text + "\n")
    out_m = m.join(yo_m.add_suffix("_yoy_pct")).round(2)
    out_m.to_csv(os.path.join(args.outdir, "monthly.csv"))

    if not args.no_plots:
        paths = plots_mod.make_all(daily, indexed, yo_d, yo_m, meta.get("yp_gaps", []), args.outdir)
        for p in paths:
            print(f"[plot] {p}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
