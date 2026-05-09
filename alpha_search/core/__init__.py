"""Core module for Alpha Search - models, base classes, config, and exceptions."""

from alpha_search.core.base import DataProvider, BrokerAdapter, SentimentAnalyzer, Signal, CompositeSignal
from alpha_search.core.config import QuantOsConfig, get_config
from alpha_search.core.errors import (
    QuantOSError,
    DataProviderError,
    ValidationError,
    BacktestError,
    ExecutionError,
)
from alpha_search.core.models import OHLCV, SignalData, BacktestResult, Order, Position

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
