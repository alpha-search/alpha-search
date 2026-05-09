"""Base classes for the Alpha Search Data Source Platform.

This module defines the abstract interfaces and metadata structures used by
all 35+ data source providers in the Alpha Search platform.

Example:
    >>> from alpha_search.data_sources.base import DataSourceRegistry, DataSource
    >>> registry = DataSourceRegistry()
    >>> for meta in registry.list_available():
    ...     print(f"{meta.name}: {meta.description}")
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class SourceMeta:
    """Metadata describing a data source provider.

    Attributes:
        name: Unique machine-readable identifier (snake_case).
        category: Broad category — one of "stocks", "crypto", "forex",
            "macro", "news", "fundamentals", "alternative".
        description: Human-readable one-line summary.
        requires_api_key: Whether an API key is needed to access the source.
        free_tier: Whether the source offers a free usage tier.
        rate_limit: Rate limit description, e.g. "5/min", "100/day".
        data_types: List of supported data types, e.g. ["ohlcv", "fundamentals"].
        coverage: Geographic or asset coverage, e.g. "global", "us", "crypto".
        homepage: URL to the provider's homepage.
        docs_url: URL to API documentation.
        install_cmd: Optional ``pip install`` command if a package is required.
        status: Current implementation status — "live", "planned", or "stub".
    """

    name: str
    category: str  # "stocks", "crypto", "forex", "macro", "news", "fundamentals", "alternative"
    description: str
    requires_api_key: bool
    free_tier: bool
    rate_limit: str  # e.g. "5/min", "100/day"
    data_types: List[str]  # ["ohlcv", "fundamentals", "news", "sentiment"]
    coverage: str  # "global", "us", "india", "crypto", etc.
    homepage: str
    docs_url: str
    install_cmd: Optional[str] = None  # pip install command if needed
    status: str = "planned"  # "live", "planned", "stub"

    def to_dict(self) -> Dict[str, Any]:
        """Return metadata as a dictionary."""
        return {
            "name": self.name,
            "category": self.category,
            "description": self.description,
            "requires_api_key": self.requires_api_key,
            "free_tier": self.free_tier,
            "rate_limit": self.rate_limit,
            "data_types": self.data_types,
            "coverage": self.coverage,
            "homepage": self.homepage,
            "docs_url": self.docs_url,
            "install_cmd": self.install_cmd,
            "status": self.status,
        }


class DataSource(ABC):
    """Abstract base class for all Alpha Search data sources.

    Every provider in the platform must inherit from ``DataSource`` and
    implement the required abstract methods. Optional capabilities (fundamentals,
    news, sentiment) raise ``NotImplementedError`` by default.

    Attributes:
        meta: A :class:`SourceMeta` instance describing this source.

    Example:
        >>> class MySource(DataSource):
        ...     meta = SourceMeta(name="my_source", ...)
        ...     def is_available(self) -> bool:
        ...         return True
        ...     def fetch_ohlcv(self, symbol, start, end, interval="1d") -> pd.DataFrame:
        ...         return pd.DataFrame()
    """

    meta: SourceMeta

    @abstractmethod
    def is_available(self) -> bool:
        """Check whether this source can be used right now.

        Returns ``True`` when all runtime dependencies are installed and any
        required API keys / credentials are configured.
        """

    @abstractmethod
    def fetch_ohlcv(
        self,
        symbol: str,
        start: str,
        end: str,
        interval: str = "1d",
    ) -> pd.DataFrame:
        """Fetch OHLCV (Open/High/Low/Close/Volume) price data.

        Parameters:
            symbol: Ticker or trading-pair symbol, e.g. ``AAPL`` or ``BTCUSDT``.
            start: Start date as ``YYYY-MM-DD``.
            end: End date as ``YYYY-MM-DD``.
            interval: Bar interval — ``1d`` (default), ``1h``, ``15m``, etc.

        Returns:
            A :class:`pandas.DataFrame` with columns ``[open, high, low, close, volume]``
            and a DatetimeIndex.
        """

    def fetch_fundamentals(self, symbol: str) -> Dict[str, Any]:
        """Fetch fundamental financial data for *symbol*.

        Parameters:
            symbol: Ticker symbol.

        Returns:
            Dictionary of fundamental metrics (P/E, market cap, etc.).

        Raises:
            NotImplementedError: If the source does not support fundamentals.
        """
        raise NotImplementedError(
            f"{self.meta.name} does not support fundamentals. "
            "Override fetch_fundamentals() to add this capability."
        )

    def fetch_news(
        self, symbol: str, limit: int = 10
    ) -> List[Dict[str, str]]:
        """Fetch recent news articles related to *symbol*.

        Parameters:
            symbol: Ticker or keyword to search news for.
            limit: Maximum number of articles to return.

        Returns:
            List of article dictionaries with keys ``title``, ``url``, ``published``.

        Raises:
            NotImplementedError: If the source does not support news.
        """
        raise NotImplementedError(
            f"{self.meta.name} does not support news. "
            "Override fetch_news() to add this capability."
        )

    def fetch_sentiment(self, symbol: str) -> Dict[str, float]:
        """Fetch sentiment scores for *symbol*.

        Parameters:
            symbol: Ticker or keyword.

        Returns:
            Dictionary of sentiment scores, e.g. ``{"bullish": 0.72, "bearish": 0.28}``.

        Raises:
            NotImplementedError: If the source does not support sentiment.
        """
        raise NotImplementedError(
            f"{self.meta.name} does not support sentiment. "
            "Override fetch_sentiment() to add this capability."
        )

    def fetch_macro(self, indicator: str, **kwargs: Any) -> pd.DataFrame:
        """Fetch macro-economic indicator data.

        Parameters:
            indicator: Macro indicator code, e.g. ``GDP``, ``CPIAUCSL``.
            **kwargs: Additional provider-specific parameters.

        Returns:
            A :class:`pandas.DataFrame` with the indicator time series.

        Raises:
            NotImplementedError: If the source does not support macro data.
        """
        raise NotImplementedError(
            f"{self.meta.name} does not support macro-economic data. "
            "Override fetch_macro() to add this capability."
        )

    def info(self) -> Dict[str, Any]:
        """Return metadata and availability info for this source.

        Returns:
            Dictionary combining :attr:`meta` with runtime availability.
        """
        result = self.meta.to_dict()
        result["available"] = self.is_available()
        return result


class DataSourceRegistry:
    """Central registry for all :class:`DataSource` implementations.

    The registry acts as a catalog — providers are registered once at import
    time and can be queried by name, category, or availability.

    Example:
        >>> registry = DataSourceRegistry()
        >>> registry.register(YFinanceSource())
        >>> yf = registry.get("yfinance")
        >>> live = registry.list_live()
    """

    def __init__(self) -> None:
        self._sources: Dict[str, DataSource] = {}

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register(self, source: DataSource) -> None:
        """Register a :class:`DataSource` instance.

        Parameters:
            source: The data source to register.

        Raises:
            ValueError: If a source with the same name is already registered.
        """
        name = source.meta.name
        if name in self._sources:
            raise ValueError(f"Data source '{name}' is already registered.")
        self._sources[name] = source
        logger.debug("Registered data source: %s", name)

    def unregister(self, name: str) -> None:
        """Remove a source from the registry.

        Parameters:
            name: The unique source name to remove.
        """
        self._sources.pop(name, None)
        logger.debug("Unregistered data source: %s", name)

    # ------------------------------------------------------------------
    # Retrieval
    # ------------------------------------------------------------------

    def get(self, name: str) -> Optional[DataSource]:
        """Retrieve a registered source by name.

        Parameters:
            name: Machine-readable source name (snake_case).

        Returns:
            The :class:`DataSource` instance, or ``None`` if not found.
        """
        return self._sources.get(name)

    def get_or_raise(self, name: str) -> DataSource:
        """Retrieve a source by name, raising if not found.

        Parameters:
            name: Machine-readable source name.

        Returns:
            The :class:`DataSource` instance.

        Raises:
            KeyError: If no source with *name* is registered.
        """
        source = self._sources.get(name)
        if source is None:
            available = list(self._sources.keys())
            raise KeyError(
                f"Data source '{name}' not found. "
                f"Available sources: {available}"
            )
        return source

    # ------------------------------------------------------------------
    # Listing / filtering
    # ------------------------------------------------------------------

    def list_all(self) -> List[SourceMeta]:
        """Return metadata for every registered source."""
        return [s.meta for s in self._sources.values()]

    def list_available(self) -> List[SourceMeta]:
        """Return metadata for sources where :meth:`is_available` is ``True``."""
        return [s.meta for s in self._sources.values() if s.is_available()]

    def list_by_category(self, category: str) -> List[SourceMeta]:
        """Return sources filtered by category string.

        Parameters:
            category: One of ``stocks``, ``crypto``, ``forex``, ``macro``,
                ``news``, ``fundamentals``, ``alternative``.
        """
        return [s.meta for s in self._sources.values() if s.meta.category == category]

    def list_live(self) -> List[SourceMeta]:
        """Return sources whose ``status`` is ``"live"``."""
        return [s.meta for s in self._sources.values() if s.meta.status == "live"]

    def list_stubs(self) -> List[SourceMeta]:
        """Return sources whose ``status`` is ``"stub"``."""
        return [s.meta for s in self._sources.values() if s.meta.status == "stub"]

    def list_planned(self) -> List[SourceMeta]:
        """Return sources whose ``status`` is ``"planned"``."""
        return [s.meta for s in self._sources.values() if s.meta.status == "planned"]

    def list_needing_key(self) -> List[SourceMeta]:
        """Return sources that require an API key."""
        return [s.meta for s in self._sources.values() if s.meta.requires_api_key]

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def count(self) -> int:
        """Total number of registered sources."""
        return len(self._sources)

    def count_live(self) -> int:
        """Number of sources with ``status == "live"``."""
        return len(self.list_live())

    def count_available(self) -> int:
        """Number of sources that are currently available for use."""
        return len(self.list_available())

    def summary(self) -> Dict[str, Any]:
        """Return a high-level summary of the registry state.

        Returns:
            Dictionary with counts and breakdowns by category / status.
        """
        categories: Dict[str, int] = {}
        statuses: Dict[str, int] = {}
        for meta in self.list_all():
            categories[meta.category] = categories.get(meta.category, 0) + 1
            statuses[meta.status] = statuses.get(meta.status, 0) + 1

        return {
            "total": self.count(),
            "live": self.count_live(),
            "available_now": self.count_available(),
            "by_category": categories,
            "by_status": statuses,
        }

    def __repr__(self) -> str:
        return (
            f"DataSourceRegistry(sources={self.count()}, "
            f"live={self.count_live()}, available={self.count_available()})"
        )
