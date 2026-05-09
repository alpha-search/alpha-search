"""Cryptocurrency asset profiles, on-chain metrics, market data, and institutional research from Messari. (stub).

Messari -- crypto asset profiles, metrics, and research.

To activate this source:
    1. Get API key at https://messari.io
    2. Set MESSARI_API_KEY env var
    3. pip install messari
    4. Implement fetch_ohlcv()

References:
    - https://messari.io/api/docs
"""

from __future__ import annotations

import logging

import pandas as pd

from alpha_search.data_sources.base import DataSource, SourceMeta

logger = logging.getLogger(__name__)


class MessariSource(DataSource):
    """Messari -- institutional-grade crypto data and research.

    Status: **stub** -- implement the methods below to activate.
    """

    meta = SourceMeta(
        name="messari",
        category="crypto",
        description="Messari -- crypto asset profiles, metrics, and research.",
        requires_api_key=False,
        free_tier=True,
        rate_limit="1000/day (free)",
        data_types=["ohlcv", "metrics", "profiles", "research"],
        coverage="crypto",
        homepage="https://messari.io",
        docs_url="https://messari.io/api/docs",
        install_cmd="pip install messari",
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
            "MessariSource is a stub. To activate it:\n"
            "1. Get API key at https://messari.io\n"
            "2. Set MESSARI_API_KEY environment variable\n"
            "3. pip install messari\n"
            "4. Implement fetch_ohlcv() using the Messari API"
        )
