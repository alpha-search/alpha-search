"""International financial statistics, balance of payments, government finance, and macroeconomic data from the International Monetary Fund. (stub).

IMF Data -- international financial statistics and macroeconomic data.

To activate this source:
    1. pip install imfpy
    2. Implement fetch_ohlcv() and fetch_macro()

References:
    - https://datahelp.imf.org/knowledgebase/articles/667681
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

import pandas as pd

from alpha_search.data_sources.base import DataSource, SourceMeta

logger = logging.getLogger(__name__)


class IMFSource(DataSource):
    """IMF -- international monetary and financial statistics.

    Status: **stub** -- implement the methods below to activate.
    """

    meta = SourceMeta(
        name="imf",
        category="macro_economic",
        description="IMF Data -- international financial statistics and macroeconomic data.",
        requires_api_key=False,
        free_tier=True,
        rate_limit="unspecified",
        data_types=["macro", "finance", "trade", "debt"],
        coverage="global",
        homepage="https://data.imf.org",
        docs_url="https://datahelp.imf.org/knowledgebase/articles/667681",
        install_cmd="pip install imfpy",
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
            "IMFSource is a stub. To activate it:\n"
            "1. pip install imfpy\n"
            "2. Implement fetch_macro() using imfpy to access IMF databases"
        )
