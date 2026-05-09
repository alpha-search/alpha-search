"""Access to over 800,000 economic time series from the Federal Reserve Bank of St. Louis, including interest rates, GDP, unemployment, and inflation. (stub).

FRED -- Federal Reserve Economic Data, 800k+ time series.

To activate this source:
    1. Get API key at https://fred.stlouisfed.org/docs/api/api_key.html
    2. Set FRED_API_KEY env var
    3. pip install fredapi
    4. Implement fetch_ohlcv() and fetch_macro()

References:
    - https://fred.stlouisfed.org/docs/api/fred/
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

import pandas as pd

from alpha_search.data_sources.base import DataSource, SourceMeta

logger = logging.getLogger(__name__)


class FREDSource(DataSource):
    """FRED -- Federal Reserve Economic Data from the St. Louis Fed.

    Status: **stub** -- implement the methods below to activate.
    """

    meta = SourceMeta(
        name="fred",
        category="macro_economic",
        description="FRED -- Federal Reserve Economic Data, 800k+ time series.",
        requires_api_key=False,
        free_tier=True,
        rate_limit="120 requests/min",
        data_types=["macro", "interest_rates", "gdp", "inflation", "employment"],
        coverage="us",
        homepage="https://fred.stlouisfed.org",
        docs_url="https://fred.stlouisfed.org/docs/api/fred/",
        install_cmd="pip install fredapi",
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
            "FREDSource is a stub. To activate it:\n"
            "1. Get API key at https://fred.stlouisfed.org/docs/api/api_key.html\n"
            "2. Set FRED_API_KEY environment variable\n"
            "3. pip install fredapi\n"
            "4. Implement fetch_ohlcv() and fetch_macro() using fredapi.Fred"
        )
