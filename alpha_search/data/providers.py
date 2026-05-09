"""Provider registry for managing multiple data sources."""

from __future__ import annotations

import logging
from typing import Dict, List, Optional, Type

import pandas as pd

from alpha_search.core.base import DataProvider
from alpha_search.core.errors import DataProviderError
from alpha_search.data.cache import CacheManager

logger = logging.getLogger(__name__)


class ProviderRegistry:
    """Registry of :class:`DataProvider` instances.

    Automatically registers built-in providers on first use.
    Providers are tried in registration order when no source is specified.

    Example::

        registry = ProviderRegistry()
        df = registry.get_prices("AAPL", "2020-01-01", "2020-12-31")
    """

    def __init__(self) -> None:
        self._providers: Dict[str, DataProvider] = {}
        self._cache = CacheManager()
        self._auto_registered = False

    def _ensure_builtin(self) -> None:
        """Lazy auto-registration of built-in providers."""
        if self._auto_registered:
            return
        self._auto_registered = True
        # Try to register YFinanceProvider
        try:
            from alpha_search.data.yfinance_provider import YFinanceProvider

            self.register(YFinanceProvider(cache=self._cache))
            logger.debug("Auto-registered YFinanceProvider")
        except ImportError as exc:
            logger.debug("YFinanceProvider not available: %s", exc)

        # Try to register BinanceProvider
        try:
            from alpha_search.data.binance_provider import BinanceProvider

            self.register(BinanceProvider(cache=self._cache))
            logger.debug("Auto-registered BinanceProvider")
        except ImportError as exc:
            logger.debug("BinanceProvider not available: %s", exc)

    def register(self, provider: DataProvider) -> None:
        """Add a provider to the registry.

        Args:
            provider: Concrete DataProvider instance.

        Raises:
            DataProviderError: If a provider with the same name already exists.
        """
        name = provider.name
        if name in self._providers:
            raise DataProviderError(
                f"Provider '{name}' is already registered.",
                provider=name,
            )
        self._providers[name] = provider
        logger.info("Registered data provider: %s", name)

    def get(self, name: str) -> DataProvider:
        """Retrieve a provider by name.

        Args:
            name: Provider name (e.g. ``'yfinance'``, ``'binance'``).

        Returns:
            The registered DataProvider instance.

        Raises:
            DataProviderError: If the provider is not found.
        """
        self._ensure_builtin()
        if name not in self._providers:
            available = list(self._providers.keys())
            raise DataProviderError(
                f"Provider '{name}' not found. Available: {available}",
                provider=name,
            )
        return self._providers[name]

    def get_prices(
        self,
        ticker: str,
        start: str,
        end: str,
        source: Optional[str] = None,
    ) -> pd.DataFrame:
        """Fetch prices for *ticker*, trying providers until one succeeds.

        Args:
            ticker: Ticker symbol.
            start: Start date ``YYYY-MM-DD``.
            end: End date ``YYYY-MM-DD``.
            source: Specific provider name to use. If ``None``, tries all
                registered providers in order.

        Returns:
            Normalized OHLCV DataFrame.

        Raises:
            DataProviderError: If all providers fail.
        """
        self._ensure_builtin()

        if source is not None:
            providers = [self.get(source)]
        else:
            providers = list(self._providers.values())

        if not providers:
            raise DataProviderError("No data providers are registered.")

        errors: List[str] = []
        for prov in providers:
            try:
                logger.info(
                    "Fetching %s via %s (%s to %s)",
                    ticker,
                    prov.name,
                    start,
                    end,
                )
                df = prov.get_prices(ticker, start, end)
                if df is not None and not df.empty:
                    return df
            except Exception as exc:
                msg = f"{prov.name}: {exc}"
                logger.warning(msg)
                errors.append(msg)

        raise DataProviderError(
            f"All providers failed for {ticker} ({start} to {end}). "
            f"Errors: {'; '.join(errors)}"
        )

    def list_providers(self) -> List[str]:
        """Return a list of registered provider names."""
        self._ensure_builtin()
        return list(self._providers.keys())

    def __contains__(self, name: str) -> bool:
        self._ensure_builtin()
        return name in self._providers

    def __repr__(self) -> str:
        names = self.list_providers()
        return f"<ProviderRegistry providers={names}>"
