"""Alpha Search Data Source Platform — 30+ financial data providers.

The data source platform provides a unified interface to 35+ financial data
providers across stocks, crypto, forex, macroeconomics, news, sentiment,
fundamentals, and alternative data categories.

Usage::

    from alpha_search.data_sources import BUILTIN_SOURCES

    # List all available data sources
    for meta in BUILTIN_SOURCES.list_all():
        print(f"{meta.name}: {meta.description}")

    # Get a specific source
    yf = BUILTIN_SOURCES.get("yfinance")
    df = yf.fetch_ohlcv("AAPL", "2023-01-01", "2023-12-31")

Categories:
    - **stocks**: 8 sources (yfinance, alpha_vantage, fmp, tiingo, ...)
    - **crypto**: 7 sources (binance, coingecko, coinmarketcap, ...)
    - **forex_commodities**: 4 sources (forex_python, oanda, ...)
    - **macro_economic**: 5 sources (fred, world_bank, oecd, ...)
    - **news_sentiment**: 5 sources (newsapi, reddit, twitter, ...)
    - **fundamentals**: 4 sources (sec_edgar, simfin, ...)
    - **alternative**: 4 sources (github_activity, openmeteo, ...)
"""

from alpha_search.data_sources.base import DataSource, DataSourceRegistry
from alpha_search.data_sources.registry import BUILTIN_SOURCES

__all__ = ["DataSource", "DataSourceRegistry", "BUILTIN_SOURCES"]
