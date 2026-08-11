"""Backtest configuration."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence


@dataclass
class UniverseConfig:
    #: 'ALL' (KOSPI+KOSDAQ), 'TOP500' (mktcap), or 'KOSPI200'
    definition: str = "ALL"
    #: minimum months since listing (상장 후 12개월 미만 제외)
    min_listing_months: int = 12
    #: drop bottom X% by 60-day average traded value (유동성 필터). 0 disables.
    illiquid_drop_pct: float = 0.20
    #: liquidity lookback (trading days)
    liquidity_lookback: int = 60
    #: optional hard market-cap floor in KRW (e.g. 100e8 = 1,000억). None disables.
    mktcap_floor: float | None = None
    #: for TOP500
    top_n_by_mktcap: int | None = None


@dataclass
class PortfolioConfig:
    #: fraction in each tail (0.2 -> top/bottom quintile)
    quantile: float = 0.20
    #: 'equal' or 'mktcap'
    weighting: str = "equal"
    #: trading-day lag between signal date and execution (>=1 kills look-ahead)
    exec_lag_days: int = 1
    #: execute at next-day 'close' or 'vwap'
    exec_price: str = "close"
    #: rebalance frequency (only 'M' month-end supported end-to-end)
    rebalance: str = "M"


@dataclass
class CostConfig:
    #: one-way long transaction cost in bps; round-trip = 2x. Sensitivity list.
    long_cost_bps: Sequence[float] = (15.0, 20.0, 25.0)  # -> 30/40/50bp round trip
    #: extra one-way cost applied to the short leg (거래세 등), bps
    short_extra_bps: float = 0.0
    #: annual borrow (대차) fee scenarios for the short book
    borrow_annual: Sequence[float] = (0.02, 0.05, 0.10)


@dataclass
class FactorConfig:
    #: winsorize revision ratios at these cross-sectional quantiles
    winsor: tuple[float, float] = (0.01, 0.99)
    #: also build standardized (cross-sectional z) version of each factor
    standardize: bool = True
    #: blended-forward weight on FY1 (rest on FY2) for the blended estimate
    fy1_blend_weight: float = 0.65
    #: months a fiscal roll is masked out to avoid spurious revision
    roll_mask_months: int = 1


@dataclass
class BacktestConfig:
    start: str = "2010-01-01"
    end: str | None = None                       # None -> latest available
    benchmark: str = "KOSPI"                      # 'KOSPI' | 'KOSPI200'
    rf_annual: float = 0.02                       # fallback risk-free if none supplied
    season_months: tuple[int, ...] = (2, 5, 8, 11)
    subperiods: tuple[tuple[str, str], ...] = (
        ("2010-01-01", "2014-12-31"),
        ("2015-01-01", "2019-12-31"),
        ("2020-01-01", "2022-12-31"),
        ("2023-01-01", "2100-01-01"),
    )
    n_bootstrap: int = 5000
    newey_west_lags: int = 6
    seed: int = 20260811                          # deterministic bootstrap
    outdir: str = "outputs"

    universe: UniverseConfig = field(default_factory=UniverseConfig)
    portfolio: PortfolioConfig = field(default_factory=PortfolioConfig)
    cost: CostConfig = field(default_factory=CostConfig)
    factor: FactorConfig = field(default_factory=FactorConfig)
