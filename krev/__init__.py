"""
krev — Korea Earnings-Revision Factor backtest engine.

A point-in-time, look-ahead-free backtest framework for testing whether the
Earnings-Revision anomaly (buy stocks whose forward consensus is being revised
up) works in the Korean market (KOSPI + KOSDAQ).

The engine is data-source agnostic. You supply three point-in-time panels
(consensus estimates, prices, security metadata) that conform to
``krev.data_schema``; everything else — factors, portfolios, costs, metrics,
seasonality, event-time, neutralization, regressions, reporting — is built here.

See docs/DATA_GUIDE.md for how to obtain the consensus panel for Korea.
"""

__version__ = "0.1.0"

from . import (  # noqa: F401
    config,
    data_schema,
    factors,
    portfolio,
    metrics,
    seasonality,
    eventtime,
    neutral,
    report,
    adapters,
)
