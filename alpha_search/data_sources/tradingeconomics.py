"""Economic indicators, exchange rates, stock market indexes, government bond yields, and commodity prices for 196 countries from Trading Economics. (stub).

Trading Economics -- 20M+ indicators for 196 countries.

To activate this source:
    1. Get API key at https://tradingeconomics.com
    2. Set TE_API_KEY env var
    3. pip install tradingeconomics
    4. Implement fetch_ohlcv()

References:
    - https://docs.tradingeconomics.com/
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

import pandas as pd

from alpha_search.data_sources.base import DataSource, SourceMeta

logger = logging.getLogger(__name__)


class TradingEconomicsSource(DataSource):
    """Trading Economics -- economic indicators and forecasts for 196 countries.

    Status: **stub** -- implement the methods below to activate.
    """

    meta = SourceMeta(
        name="tradingeconomics",
        category="macro_economic",
        description="Trading Economics -- 20M+ indicators for 196 countries.",
        requires_api_key=False,
        free_tier=True,
        rate_limit="provider-dependent",
        data_types=["macro", "indicators", "forex", "bonds", "commodities"],
        coverage="global",
        homepage="https://tradingeconomics.com",
        docs_url="https://docs.tradingeconomics.com/",
        install_cmd="pip install tradingeconomics",
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
            "TradingEconomicsSource is a stub. To activate it:\n"
            "1. Get API key at https://tradingeconomics.com\n"
            "2. Set TE_API_KEY environment variable\n"
            "3. pip install tradingeconomics\n"
            "4. Implement fetch_macro() using tradingeconomics API"
        )
