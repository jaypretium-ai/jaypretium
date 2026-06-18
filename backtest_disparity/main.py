"""엔트리포인트.

예) python main.py --start 2016-01-01 --thresholds 20 25 30 35 --windows 21 63 126 252

데이터 소스는 pykrx(1순위) → FinanceDataReader(대체) 자동 시도.
KRX/Naver 접근이 막힌 환경에서는 --csv 로 date,common,pref 가격 파일을 직접 제공.
"""

from __future__ import annotations

import argparse
import os
import sys

import data as data_mod
import stats as stats_mod
import backtest as bt_mod
import plots as plots_mod

HERE = os.path.dirname(os.path.abspath(__file__))
OUTDIR = os.path.join(HERE, "output")


def parse_args(argv=None):
    p = argparse.ArgumentParser(
        description="삼성전자 보통주(005930) vs 우선주(005935) 괴리율 백테스트")
    p.add_argument("--start", default="2016-01-01", help="시작일 YYYY-MM-DD")
    p.add_argument("--end", default=None, help="종료일 YYYY-MM-DD (기본=오늘)")
    p.add_argument("--thresholds", type=int, nargs="+", default=[20, 25, 30, 35],
                   help="진입 임계 할인율(%%) 버킷")
    p.add_argument("--windows", type=int, nargs="+", default=[21, 63, 126, 252],
                   help="forward window 거래일 수 (21/63/126/252 = 1/3/6/12M)")
    p.add_argument("--source", choices=["auto", "pykrx", "fdr", "csv"], default="auto",
                   help="데이터 소스")
    p.add_argument("--csv", default=None,
                   help="오프라인 가격 CSV 경로 (컬럼: date, common, pref)")
    p.add_argument("--outdir", default=OUTDIR, help="출력 디렉터리")
    p.add_argument("--no-plots", action="store_true", help="플롯 생략")
    return p.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    os.makedirs(args.outdir, exist_ok=True)
    source = "csv" if args.csv else args.source

    # 1) 데이터
    try:
        df = data_mod.load_prices(args.start, args.end, source=source, csv_path=args.csv)
    except Exception as e:  # noqa: BLE001
        print(f"\n[오류] 데이터 로드 실패:\n{e}", file=sys.stderr)
        return 2

    data_mod.save_daily_csv(df, os.path.join(args.outdir, "daily_discount.csv"))

    # 2) 통계
    s = stats_mod.summary(df)
    tbl = stats_mod.yearly_table(df)
    stats_mod.print_summary(s)
    stats_mod.print_yearly(tbl)
    stats_mod.save_csvs(
        s, tbl,
        os.path.join(args.outdir, "stats_summary.csv"),
        os.path.join(args.outdir, "stats_yearly.csv"),
    )

    # 3) 백테스트
    summary_df, trades_df = bt_mod.run(df, args.thresholds, args.windows)
    bt_mod.print_report(summary_df)
    bt_mod.save_csvs(
        summary_df, trades_df,
        os.path.join(args.outdir, "backtest_summary.csv"),
        os.path.join(args.outdir, "backtest_trades.csv"),
    )

    # 4) 시각화
    if not args.no_plots:
        plots_mod.make_all(df, trades_df, s["mean"], args.thresholds, args.windows,
                           args.outdir)

    print("\n[완료] 결과는 output/ 에 저장되었습니다. 해석 시 README의 '통계 함정' 절을 반드시 참고하세요.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
