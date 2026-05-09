"""On-chain analytics, market indicators, and blockchain data for Bitcoin, Ethereum, and other cryptocurrencies from Glassnode. (stub).

Glassnode -- on-chain analytics and market indicators.

To activate this source:
    1. Get API key at https://glassnode.com
    2. Set GLASSNODE_API_KEY env var
    3. pip install glassnode
    4. Implement fetch_ohlcv()

References:
    - https://docs.glassnode.com/
"""

from __future__ import annotations

import logging

import pandas as pd

from alpha_search.data_sources.base import DataSource, SourceMeta

logger = logging.getLogger(__name__)


class GlassnodeSource(DataSource):
    """Glassnode -- on-chain metrics and market intelligence for crypto.

    Status: **stub** -- implement the methods below to activate.
    """

    meta = SourceMeta(
        name="glassnode",
        category="crypto",
        description="Glassnode -- on-chain analytics and market indicators.",
        requires_api_key=False,
        free_tier=True,
        rate_limit="30 calls/min (free)",
        data_types=["onchain", "metrics", "indicators"],
        coverage="crypto",
        homepage="https://glassnode.com",
        docs_url="https://docs.glassnode.com/",
        install_cmd="pip install glassnode",
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
            "GlassnodeSource is a stub. To activate it:\n"
            "1. Get API key at https://glassnode.com\n"
            "2. Set GLASSNODE_API_KEY environment variable\n"
            "3. pip install glassnode\n"
            "4. Implement fetch_ohlcv() using glassnode API endpoints"
        )
