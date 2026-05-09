"""Alternative data aggregation from multiple niche providers including satellite imagery, web traffic, and consumer spending data. (stub).

AltStack -- alternative data aggregation platform.

To activate this source:
    1. Get API key at provider
    2. Set ALTSTACK_API_KEY env var
    3. pip install requests
    4. Implement data fetching

References:
    - https://example.com/docs
"""

from __future__ import annotations

import logging

import pandas as pd

from alpha_search.data_sources.base import DataSource, SourceMeta

logger = logging.getLogger(__name__)


class AltStackSource(DataSource):
    """AltStack -- alternative data provider aggregator.

    Status: **stub** -- implement the methods below to activate.
    """

    meta = SourceMeta(
        name="altstack",
        category="alternative",
        description="AltStack -- alternative data aggregation platform.",
        requires_api_key=False,
        free_tier=True,
        rate_limit="provider-dependent",
        data_types=["alternative", "satellite", "web_traffic", "spending"],
        coverage="global",
        homepage="https://example.com",
        docs_url="https://example.com/docs",
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
            "AltStackSource is a stub. To activate it:\n"
            "1. Sign up for AltStack API access\n"
            "2. Set ALTSTACK_API_KEY environment variable\n"
            "3. pip install requests\n"
            "4. Implement data fetching using requests"
        )
