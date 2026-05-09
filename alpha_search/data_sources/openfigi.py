"""Free mapping API for financial instrument identifiers (FIGI, ISIN, CUSIP, ticker symbols) from Bloomberg's OpenFIGI service. (stub).

OpenFIGI -- free financial instrument identifier mapping.

To activate this source:
    1. No API key required
    2. pip install openfigi-client
    3. Implement identifier mapping

References:
    - https://www.openfigi.com/api/
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

import pandas as pd

from alpha_search.data_sources.base import DataSource, SourceMeta

logger = logging.getLogger(__name__)


class OpenFIGISource(DataSource):
    """OpenFIGI -- open identifier mapping for financial instruments.

    Status: **stub** -- implement the methods below to activate.
    """

    meta = SourceMeta(
        name="openfigi",
        category="fundamentals",
        description="OpenFIGI -- free financial instrument identifier mapping.",
        requires_api_key=False,
        free_tier=True,
        rate_limit="25 requests/6sec (bulk: 100/sec)",
        data_types=["identifiers", "mapping"],
        coverage="global",
        homepage="https://www.openfigi.com",
        docs_url="https://www.openfigi.com/api/",
        install_cmd="pip install openfigi-client",
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
            "OpenFIGISource is a stub. To activate it:\n"
            "1. No API key required for basic usage\n"
            "2. pip install openfigi-client\n"
            "3. Implement identifier mapping using openfigi API"
        )
