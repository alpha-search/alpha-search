"""Core module for Alpha Search - models, base classes, config, and exceptions."""

from alpha_search.core.base import (
    BrokerAdapter,
    CompositeSignal,
    DataProvider,
    SentimentAnalyzer,
    Signal,
)
from alpha_search.core.config import QuantOsConfig, get_config
from alpha_search.core.errors import (
    BacktestError,
    DataProviderError,
    ExecutionError,
    QuantOSError,
    ValidationError,
)
from alpha_search.core.models import OHLCV, BacktestResult, Order, Position, SignalData

__all__ = [
    "DataProvider",
    "BrokerAdapter",
    "SentimentAnalyzer",
    "Signal",
    "CompositeSignal",
    "QuantOsConfig",
    "get_config",
    "QuantOSError",
    "DataProviderError",
    "ValidationError",
    "BacktestError",
    "ExecutionError",
    "OHLCV",
    "SignalData",
    "BacktestResult",
    "Order",
    "Position",
]
