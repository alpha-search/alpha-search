"""Data layer for Alpha Search - providers, cache, and normalization."""

from alpha_search.data.cache import CacheManager
from alpha_search.data.normalizer import normalize_ohlcv
from alpha_search.data.providers import ProviderRegistry
from alpha_search.data.yfinance_provider import YFinanceProvider

try:
    from alpha_search.data.binance_provider import BinanceProvider
except ImportError:
    BinanceProvider = None  # type: ignore

__all__ = [
    "CacheManager",
    "ProviderRegistry",
    "YFinanceProvider",
    "BinanceProvider",
    "normalize_ohlcv",
]
