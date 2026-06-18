"""Forward-return 백테스트 (overlapping 처리 포함).

전략 가정: 할인율이 임계값 이상인 '진입일'에 우선주를 매수한다.
각 진입일에 대해 forward window(거래일) 뒤의 수익률을 진입일 '이후' 가격만으로 계산
(미래 데이터 누수 금지). 일별 중복 진입(overlapping)의 편향을 명시하기 위해
관측 수(n_days)와 독립 에피소드 수(distinct upward-breakout cluster)를 함께 보고한다.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

PCTS = [5, 25, 50, 75, 95]


def _episodes(entry_pos: np.ndarray) -> int:
    """진입 포지션(정수 인덱스) 배열에서 독립 에피소드(연속 클러스터) 개수.

    연속한 거래일(인덱스 차이 1)은 같은 에피소드로 묶는다. 한 번 임계값 아래로
    내려갔다가 다시 상향 돌파하면 새로운 에피소드. = upward-breakout cluster 수.
    """
    if entry_pos.size == 0:
        return 0
    diffs = np.diff(entry_pos)
    return int(1 + np.count_nonzero(diffs > 1))


def run(
    df: pd.DataFrame,
    thresholds: list[int],
    windows: list[int],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """백테스트 실행.

    반환:
      - summary_df: (threshold, window) 별 통계 요약
      - trades_df : 개별 진입×윈도우 raw 결과 (분포·플롯·산점도용)
    """
    common = df["common"].to_numpy()
    pref = df["pref"].to_numpy()
    disc = df["discount_pct"].to_numpy()
    dates = df.index
    n = len(df)

    trade_rows = []
    summ_rows = []

    for thr in thresholds:
        entry_mask = disc >= thr
        entry_pos_all = np.nonzero(entry_mask)[0]

        for w in windows:
            # 진입일 이후 w 거래일 가격이 존재하는 진입만 사용(truncation, look-ahead 방지)
            valid = entry_pos_all[entry_pos_all + w < n]
            n_days = valid.size
            n_epi = _episodes(valid)

            if n_days == 0:
                summ_rows.append(_empty_summary(thr, w))
                continue

            exit_pos = valid + w
            pref_ret = pref[exit_pos] / pref[valid] - 1.0
            common_ret = common[exit_pos] / common[valid] - 1.0
            rel_ret = pref_ret - common_ret  # 괴리율 전략의 진짜 알파
            entry_disc = disc[valid]
            exit_disc = disc[exit_pos]
            disc_narrow = entry_disc - exit_disc  # 양수 = 할인율 축소

            for i in range(n_days):
                trade_rows.append(
                    {
                        "threshold": thr,
                        "window": w,
                        "entry_date": dates[valid[i]].date().isoformat(),
                        "exit_date": dates[exit_pos[i]].date().isoformat(),
                        "entry_discount": entry_disc[i],
                        "exit_discount": exit_disc[i],
                        "discount_narrowed": disc_narrow[i],
                        "pref_ret": pref_ret[i],
                        "common_ret": common_ret[i],
                        "rel_ret": rel_ret[i],
                    }
                )

            summ_rows.append(
                _summarize(thr, w, n_days, n_epi, rel_ret, pref_ret, common_ret, disc_narrow)
            )

    summary_df = pd.DataFrame(summ_rows)
    trades_df = pd.DataFrame(trade_rows)
    return summary_df, trades_df


def _empty_summary(thr: int, w: int) -> dict:
    base = {"threshold": thr, "window": w, "n_days": 0, "n_episodes": 0}
    for k in ("rel_mean", "rel_median", "rel_std", "rel_worst", "rel_best",
              "rel_win_rate", "pref_mean", "common_mean", "narrow_mean",
              "narrow_rate"):
        base[k] = float("nan")
    for p in PCTS:
        base[f"rel_p{p}"] = float("nan")
    base["low_significance"] = True
    return base


def _summarize(thr, w, n_days, n_epi, rel, pref_ret, common_ret, narrow) -> dict:
    row = {
        "threshold": thr,
        "window": w,
        "n_days": int(n_days),
        "n_episodes": int(n_epi),
        "rel_mean": float(np.mean(rel)),
        "rel_median": float(np.median(rel)),
        "rel_std": float(np.std(rel, ddof=1)) if n_days > 1 else float("nan"),
        "rel_worst": float(np.min(rel)),       # 최대 손실
        "rel_best": float(np.max(rel)),        # 최대 수익
        "rel_win_rate": float(np.mean(rel > 0)),
        "pref_mean": float(np.mean(pref_ret)),
        "common_mean": float(np.mean(common_ret)),
        "narrow_mean": float(np.mean(narrow)),
        "narrow_rate": float(np.mean(narrow > 0)),  # 할인 축소된 비율
        "low_significance": bool(n_epi < 5),
    }
    for p in PCTS:
        row[f"rel_p{p}"] = float(np.percentile(rel, p))
    return row


def _label(w: int) -> str:
    return {21: "1M", 63: "3M", 126: "6M", 252: "12M"}.get(w, f"{w}d")


def print_report(summary_df: pd.DataFrame) -> None:
    """콘솔 리포트. 승률만 쓰지 않고 분포·양방향·표본한계를 모두 표시."""
    print("\n=== 백테스트: 상대수익률(우선주 - 보통주) 분포 ===")
    print("  (일별 진입 = overlapping 중복표본. 결론은 '독립 에피소드' 기준으로 해석할 것)\n")
    hdr = (
        f"{'thr':>4} {'win':>4} {'n_days':>7} {'n_epi':>6} "
        f"{'mean':>7} {'med':>7} {'std':>6} {'p5':>7} {'p95':>7} "
        f"{'worst':>7} {'best':>7} {'win%':>6} {'narrow%':>8}"
    )
    print(hdr)
    print("-" * len(hdr))
    for _, r in summary_df.iterrows():
        if r["n_days"] == 0:
            print(f"{int(r['threshold']):>3}% {_label(int(r['window'])):>4} "
                  f"{'0':>7}  표본 없음 (윈도우가 데이터보다 김)")
            continue
        warn = "  ⚠표본<5" if r["low_significance"] else ""
        print(
            f"{int(r['threshold']):>3}% {_label(int(r['window'])):>4} "
            f"{int(r['n_days']):>7} {int(r['n_episodes']):>6} "
            f"{r['rel_mean']*100:>6.1f}% {r['rel_median']*100:>6.1f}% "
            f"{r['rel_std']*100:>5.1f} {r['rel_p5']*100:>6.1f}% {r['rel_p95']*100:>6.1f}% "
            f"{r['rel_worst']*100:>6.1f}% {r['rel_best']*100:>6.1f}% "
            f"{r['rel_win_rate']*100:>5.0f}% {r['narrow_rate']*100:>7.0f}%{warn}"
        )

    low = summary_df[(summary_df["n_days"] > 0) & (summary_df["low_significance"])]
    if not low.empty:
        print(
            "\n[경고] 독립 에피소드 < 5 인 버킷이 있습니다 → 통계적 유의성 낮음, 일반화 금지.\n"
            "       해당 결과는 '몇 번의 특정 국면'을 본 것일 뿐 전략의 기대값이 아닙니다."
        )


def save_csvs(summary_df: pd.DataFrame, trades_df: pd.DataFrame,
              summary_path: str, trades_path: str) -> None:
    summary_df.round(6).to_csv(summary_path, index=False)
    trades_df.round(6).to_csv(trades_path, index=False)
    print(f"[backtest] 요약 저장: {summary_path}")
    print(f"[backtest] 개별 트레이드 저장: {trades_path} ({len(trades_df)} rows)")
