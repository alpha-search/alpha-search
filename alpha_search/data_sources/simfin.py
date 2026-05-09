"""Fundamental financial data including income statements, balance sheets, and cash flow statements for quantitative analysis and backtesting. (stub).

SimFin -- simplified financial data for quantitative analysis.

To activate this source:
    1. Get API key at https://simfin.com
    2. Set SIMFIN_API_KEY env var
    3. pip install simfin
    4. Implement fetch_fundamentals()

References:
    - https://simfin.com/api/v2/documentation/
"""

from __future__ import annotations

import logging

import pandas as pd

from alpha_search.data_sources.base import DataSource, SourceMeta

logger = logging.getLogger(__name__)


class SimFinSource(DataSource):
    """SimFin -- free fundamental data for backtesting and research.

    Status: **stub** -- implement the methods below to activate.
    """

    meta = SourceMeta(
        name="simfin",
        category="fundamentals",
        description="SimFin -- simplified financial data for quantitative analysis.",
        requires_api_key=False,
        free_tier=True,
        rate_limit="2000 calls/day (free)",
        data_types=["fundamentals", "financial_statements", "ratios"],
        coverage="global",
        homepage="https://simfin.com",
        docs_url="https://simfin.com/api/v2/documentation/",
        install_cmd="pip install simfin",
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
            "SimFinSource is a stub. To activate it:\n"
            "1. Get API key at https://simfin.com\n"
            "2. Set SIMFIN_API_KEY environment variable\n"
            "3. pip install simfin\n"
            "4. Implement fetch_fundamentals() using simfin.load()"
        )
