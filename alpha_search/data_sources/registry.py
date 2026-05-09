"""Registry of all built-in data sources for Alpha Search.

This module imports every source module and populates the global
``BUILTIN_SOURCES`` registry.  Sources are registered lazily — a source
is added to the registry even when its third-party dependencies are not
installed, but its :meth:`is_available` method will return ``False``.

Usage::

    from alpha_search.data_sources.registry import BUILTIN_SOURCES

    # Total sources registered
    print(BUILTIN_SOURCES.count())          # 35+

    # Sources with live implementations
    print(BUILTIN_SOURCES.count_live())     # 3

    # Available right now (deps installed, keys set)
    print(BUILTIN_SOURCES.count_available())

    # Query by category
    crypto = BUILTIN_SOURCES.list_by_category("crypto")
"""

from __future__ import annotations

import logging
from typing import Dict

from alpha_search.data_sources.base import DataSourceRegistry

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Helper — safe module import
# ---------------------------------------------------------------------------

def _try_import(class_path: str):
    """Try to import a class, returning ``None`` on any failure.

    Parameters:
        class_path: Dotted path, e.g. ``module.submodule.ClassName``.

    Returns:
        The class object, or ``None``.
    """
    try:
        module_path, class_name = class_path.rsplit(".", 1)
        module = __import__(module_path, fromlist=[class_name])
        return getattr(module, class_name)
    except Exception as exc:
        logger.debug("Failed to import %s: %s", class_path, exc)
        return None


# ---------------------------------------------------------------------------
# Source class map
# ---------------------------------------------------------------------------

_SOURCE_CLASSES: Dict[str, str] = {
    # -- stocks (8) ---------------------------------------------------------
    "yfinance": "alpha_search.data_sources.yfinance_source.YFinanceSource",
    "alpha_vantage": "alpha_search.data_sources.providers.alpha_vantage.AlphaVantageSource",
    "eodhd": "alpha_search.data_sources.eodhd.EODHDSource",
    "fmp": "alpha_search.data_sources.fmp.FMPSource",
    "tiingo": "alpha_search.data_sources.tiingo.TiingoSource",
    "nasdaq_data_link": "alpha_search.data_sources.nasdaq_data_link.NasdaqDataLinkSource",
    "nseindia": "alpha_search.data_sources.nseindia.NSEIndiaSource",
    "bursa_malaysia": "alpha_search.data_sources.bursa_malaysia.BursaMalaysiaSource",

    # -- crypto (7) ---------------------------------------------------------
    "binance": "alpha_search.data_sources.binance_source.BinanceSource",
    "coingecko": "alpha_search.data_sources.coingecko.CoinGeckoSource",
    "coinmarketcap": "alpha_search.data_sources.coinmarketcap.CoinMarketCapSource",
    "cryptocompare": "alpha_search.data_sources.cryptocompare.CryptoCompareSource",
    "ccxt": "alpha_search.data_sources.ccxt_source.CCXTSource",
    "messari": "alpha_search.data_sources.messari.MessariSource",
    "glassnode": "alpha_search.data_sources.glassnode.GlassnodeSource",

    # -- forex / commodities (4) --------------------------------------------
    "forex_python": "alpha_search.data_sources.forex_python.ForexPythonSource",
    "oanda": "alpha_search.data_sources.oanda.OANDASource",
    "twelvedata": "alpha_search.data_sources.twelvedata.TwelveDataSource",
    "commodities": "alpha_search.data_sources.commodities.CommoditiesSource",

    # -- macro / economic (5) -----------------------------------------------
    "fred": "alpha_search.data_sources.fred.FREDSource",
    "world_bank": "alpha_search.data_sources.world_bank.WorldBankSource",
    "oecd": "alpha_search.data_sources.oecd.OECDSource",
    "imf": "alpha_search.data_sources.imf.IMFSource",
    "tradingeconomics": "alpha_search.data_sources.tradingeconomics.TradingEconomicsSource",

    # -- news / sentiment (5) -----------------------------------------------
    "newsapi": "alpha_search.data_sources.newsapi_source.NewsAPISource",
    "reddit": "alpha_search.data_sources.reddit_api.RedditAPISource",
    "twitter": "alpha_search.data_sources.twitter_api.TwitterAPISource",
    "gdelt": "alpha_search.data_sources.gdelt.GDELTSource",
    "finnhub": "alpha_search.data_sources.finnhub_news.FinnhubNewsSource",

    # -- fundamentals (4) ---------------------------------------------------
    "sec_edgar": "alpha_search.data_sources.sec_edgar.SECEdgarSource",
    "simfin": "alpha_search.data_sources.simfin.SimFinSource",
    "yahoo_query": "alpha_search.data_sources.yahoo_query.YahooQuerySource",
    "openfigi": "alpha_search.data_sources.openfigi.OpenFIGISource",

    # -- alternative (4) ----------------------------------------------------
    "github_activity": "alpha_search.data_sources.github_activity.GitHubActivitySource",
    "openmeteo": "alpha_search.data_sources.openmeteo.OpenMeteoSource",
    "altstack": "alpha_search.data_sources.altstack.AltStackSource",
    "polygon": "alpha_search.data_sources.polygon.PolygonSource",
}


# ---------------------------------------------------------------------------
# Build the global registry
# ---------------------------------------------------------------------------

def _build_registry() -> DataSourceRegistry:
    """Construct and populate the built-in source registry.

    Each source class is imported dynamically.  If the import fails (e.g.
    because the module has a hard dependency that is not installed), the
    source is skipped — this keeps the registry resilient.

    Returns:
        A fully populated :class:`DataSourceRegistry`.
    """
    registry = DataSourceRegistry()

    for name, class_path in _SOURCE_CLASSES.items():
        cls = _try_import(class_path)
        if cls is None:
            logger.debug("Skipping source '%s' — import failed.", name)
            continue

        try:
            instance = cls()
            registry.register(instance)
            logger.debug("Registered source: %s", name)
        except Exception as exc:
            logger.warning(
                "Failed to instantiate source '%s': %s", name, exc,
            )

    return registry


# Global singleton — populated at import time.
BUILTIN_SOURCES: DataSourceRegistry = _build_registry()

logger.info(
    "Alpha Search Data Source Registry loaded: %d sources total, %d live, %d available.",
    BUILTIN_SOURCES.count(),
    BUILTIN_SOURCES.count_live(),
    BUILTIN_SOURCES.count_available(),
)
