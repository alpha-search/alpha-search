"""Stock price data and corporate information from Bursa Malaysia, the stock exchange of Malaysia. (stub).

Bursa Malaysia -- Malaysian stock market data.

To activate this source:
    1. pip install requests beautifulsoup4
    2. Implement fetch_ohlcv() using web scraping or API

References:
    - https://www.bursamalaysia.com/trade/our_services_services/az_bursa_api
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

import pandas as pd

from alpha_search.data_sources.base import DataSource, SourceMeta

logger = logging.getLogger(__name__)


class BursaMalaysiaSource(DataSource):
    """Bursa Malaysia -- KLSE stock data.

    Status: **stub** -- implement the methods below to activate.
    """

    meta = SourceMeta(
        name="bursa_malaysia",
        category="stocks",
        description="Bursa Malaysia -- Malaysian stock market data.",
        requires_api_key=False,
        free_tier=True,
        rate_limit="unspecified",
        data_types=["ohlcv", "fundamentals"],
        coverage="malaysia",
        homepage="https://www.bursamalaysia.com",
        docs_url="https://www.bursamalaysia.com/trade/our_services_services/az_bursa_api",
        install_cmd=None,
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
            "BursaMalaysiaSource is a stub. To activate it:\n"
            "1. pip install requests beautifulsoup4\n"
            "2. Implement fetch_ohlcv() using requests to scrape Bursa Malaysia data"
        )
