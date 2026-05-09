"""Access to official US SEC EDGAR filings including 10-K, 10-Q, 8-K, and other financial reports for publicly traded companies. (stub).

SEC EDGAR -- official US company filings and financial statements.

To activate this source:
    1. pip install sec-edgar-downloader
    2. Implement fetch_fundamentals() using EDGAR API

References:
    - https://www.sec.gov/edgar/sec-api-documentation
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

import pandas as pd

from alpha_search.data_sources.base import DataSource, SourceMeta

logger = logging.getLogger(__name__)


class SECEdgarSource(DataSource):
    """SEC EDGAR -- official US Securities and Exchange Commission filings.

    Status: **stub** -- implement the methods below to activate.
    """

    meta = SourceMeta(
        name="sec_edgar",
        category="fundamentals",
        description="SEC EDGAR -- official US company filings and financial statements.",
        requires_api_key=False,
        free_tier=True,
        rate_limit="10 requests/sec",
        data_types=["fundamentals", "filings", "financial_statements"],
        coverage="us",
        homepage="https://www.sec.gov/edgar",
        docs_url="https://www.sec.gov/edgar/sec-api-documentation",
        install_cmd="pip install sec-edgar-downloader",
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
            "SECEdgarSource is a stub. To activate it:\n"
            "1. pip install sec-edgar-downloader\n"
            "2. Implement fetch_fundamentals() using sec_edgar_downloader.Downloader"
        )
