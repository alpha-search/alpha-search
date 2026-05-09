"""Access to the World Bank's Open Data portal with thousands of indicators covering economics, health, education, environment, and development across all countries. (stub).

World Bank Open Data -- global development indicators.

To activate this source:
    1. pip install wbgapi
    2. Implement fetch_ohlcv() and fetch_macro() using wbgapi

References:
    - https://pypi.org/project/wbgapi/
"""

from __future__ import annotations

import logging

import pandas as pd

from alpha_search.data_sources.base import DataSource, SourceMeta

logger = logging.getLogger(__name__)


class WorldBankSource(DataSource):
    """World Bank -- global economic and development indicators.

    Status: **stub** -- implement the methods below to activate.
    """

    meta = SourceMeta(
        name="world_bank",
        category="macro_economic",
        description="World Bank Open Data -- global development indicators.",
        requires_api_key=False,
        free_tier=True,
        rate_limit="unspecified",
        data_types=["macro", "gdp", "population", "trade", "development"],
        coverage="global",
        homepage="https://data.worldbank.org",
        docs_url="https://pypi.org/project/wbgapi/",
        install_cmd="pip install wbgapi",
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
            "WorldBankSource is a stub. To activate it:\n"
            "1. pip install wbgapi pandas_datareader\n"
            "2. Implement fetch_macro() using wbgapi or pandas_datareader"
        )
