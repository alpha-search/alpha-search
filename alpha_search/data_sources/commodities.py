"""Commodity price data including precious metals, energy, and agricultural products from various commodity data providers. (stub).

Commodities API -- precious metals, energy, and agricultural prices.

To activate this source:
    1. Get API key from a commodities provider
    2. Set COMMODITIES_API_KEY env var
    3. pip install requests
    4. Implement fetch_ohlcv()

References:
    - https://metals-api.com/documentation
"""

from __future__ import annotations

import logging

import pandas as pd

from alpha_search.data_sources.base import DataSource, SourceMeta

logger = logging.getLogger(__name__)


class CommoditiesSource(DataSource):
    """Commodities API -- commodity price data and historical series.

    Status: **stub** -- implement the methods below to activate.
    """

    meta = SourceMeta(
        name="commodities",
        category="forex_commodities",
        description="Commodities API -- precious metals, energy, and agricultural prices.",
        requires_api_key=False,
        free_tier=True,
        rate_limit="provider-dependent",
        data_types=["commodities", "metals", "energy", "agriculture"],
        coverage="global",
        homepage="https://metals-api.com",
        docs_url="https://metals-api.com/documentation",
        install_cmd="pip install requests",
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
            "CommoditiesSource is a stub. To activate it:\n"
            "1. Get API key from a commodity data provider (e.g., metals-api.com)\n"
            "2. Set COMMODITIES_API_KEY environment variable\n"
            "3. pip install requests\n"
            "4. Implement fetch_ohlcv() using the provider's API"
        )
