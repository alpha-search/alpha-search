"""Financial statements, key metrics, stock prices, and analyst estimates from Financial Modeling Prep. (stub).

Financial Modeling Prep -- financial statements, ratios, market data.

To activate this source:
    1. Get API key at https://financialmodelingprep.com
    2. Set FMP_API_KEY env var
    3. pip install financialmodelingprep
    4. Implement fetch_ohlcv()

References:
    - https://site.financialmodelingprep.com/developer/docs/
"""

from __future__ import annotations

import logging

import pandas as pd

from alpha_search.data_sources.base import DataSource, SourceMeta

logger = logging.getLogger(__name__)


class FMPSource(DataSource):
    """Financial Modeling Prep -- comprehensive financial data API.

    Status: **stub** -- implement the methods below to activate.
    """

    meta = SourceMeta(
        name="fmp",
        category="stocks",
        description="Financial Modeling Prep -- financial statements, ratios, market data.",
        requires_api_key=False,
        free_tier=True,
        rate_limit="250/day (free)",
        data_types=["ohlcv", "fundamentals", "ratios", "estimates"],
        coverage="us",
        homepage="https://financialmodelingprep.com",
        docs_url="https://site.financialmodelingprep.com/developer/docs/",
        install_cmd="pip install financialmodelingprep",
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
            "FMPSource is a stub. To activate it:\n"
            "1. Get API key at https://financialmodelingprep.com\n"
            "2. Set FMP_API_KEY environment variable\n"
            "3. pip install financialmodelingprep\n"
            "4. Implement fetch_ohlcv() using the FMP API"
        )
