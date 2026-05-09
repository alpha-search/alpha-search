"""Unified API for cryptocurrency trading and market data across 100+ exchanges via the CCXT library. (stub).

CCXT -- unified cryptocurrency exchange trading API.

To activate this source:
    1. pip install ccxt
    2. Implement fetch_ohlcv() using ccxt.Exchange.fetch_ohlcv()

References:
    - https://docs.ccxt.com/
"""

from __future__ import annotations

import logging

import pandas as pd

from alpha_search.data_sources.base import DataSource, SourceMeta

logger = logging.getLogger(__name__)


class CCXTSource(DataSource):
    """CCXT -- trade and fetch data from 100+ crypto exchanges.

    Status: **stub** -- implement the methods below to activate.
    """

    meta = SourceMeta(
        name="ccxt",
        category="crypto",
        description="CCXT -- unified cryptocurrency exchange trading API.",
        requires_api_key=False,
        free_tier=True,
        rate_limit="exchange-dependent",
        data_types=["ohlcv", "orderbook", "trades", "balances"],
        coverage="crypto",
        homepage="https://ccxt.trade",
        docs_url="https://docs.ccxt.com/",
        install_cmd="pip install ccxt",
        status="stub",
    )

    def is_available(self) -> bool:
        """Return ``False`` -- this source is a stub and not yet implemented."""
        return False

    def fetch_ohlcv(
        self, symbol: str, start: str, end: str, interval: str = "1d",
    ) -> pd.DataFrame:
        """Not implemented -- activate by overriding this method."""
        raise NotImplementedError(
            "CCXTSource is a stub. To activate it:\n"
            "1. pip install ccxt\n"
            "2. Create exchange instance: ccxt.binance() or ccxt.coinbase()\n"
            "3. Implement fetch_ohlcv() using exchange.fetch_ohlcv()"
        )
