"""Real-time and historical stock data from the National Stock Exchange of India (NSE), including equities, derivatives, and indices. (stub).

NSE India Official -- Indian stock market data from NSE.

To activate this source:
    1. pip install nsepython
    2. Implement fetch_ohlcv() using nsepython functions

References:
    - https://github.com/aeron7/nsepython
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

import pandas as pd

from alpha_search.data_sources.base import DataSource, SourceMeta

logger = logging.getLogger(__name__)


class NSEIndiaSource(DataSource):
    """NSE India -- official National Stock Exchange of India data.

    Status: **stub** -- implement the methods below to activate.
    """

    meta = SourceMeta(
        name="nseindia",
        category="stocks",
        description="NSE India Official -- Indian stock market data from NSE.",
        requires_api_key=False,
        free_tier=True,
        rate_limit="unspecified",
        data_types=["ohlcv", "fundamentals", "derivatives"],
        coverage="india",
        homepage="https://www.nseindia.com",
        docs_url="https://github.com/aeron7/nsepython",
        install_cmd="pip install nsepython",
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
            "NSEIndiaSource is a stub. To activate it:\n"
            "1. pip install nsepython\n"
            "2. Implement fetch_ohlcv() using nsepython.nse_eq() or nsepython.index_history()"
        )
