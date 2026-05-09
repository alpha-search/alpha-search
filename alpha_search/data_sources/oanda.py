"""Foreign exchange rates, CFD prices, and precious metals data from OANDA, a leading forex broker. (stub).

OANDA -- forex and CFD trading data.

To activate this source:
    1. Get API key at https://developer.oanda.com
    2. Set OANDA_API_KEY env var
    3. pip install oandapyV20
    4. Implement fetch_ohlcv()

References:
    - https://developer.oanda.com/docs/
"""

from __future__ import annotations

import logging

import pandas as pd

from alpha_search.data_sources.base import DataSource, SourceMeta

logger = logging.getLogger(__name__)


class OANDASource(DataSource):
    """OANDA -- professional forex, CFD, and metals data.

    Status: **stub** -- implement the methods below to activate.
    """

    meta = SourceMeta(
        name="oanda",
        category="forex_commodities",
        description="OANDA -- forex and CFD trading data.",
        requires_api_key=False,
        free_tier=True,
        rate_limit="100-500/sec",
        data_types=["forex", "cfds", "metals"],
        coverage="global",
        homepage="https://www.oanda.com",
        docs_url="https://developer.oanda.com/docs/",
        install_cmd="pip install oandapyV20",
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
            "OANDASource is a stub. To activate it:\n"
            "1. Get API key at https://developer.oanda.com\n"
            "2. Set OANDA_API_KEY environment variable\n"
            "3. pip install oandapyV20\n"
            "4. Implement fetch_ohlcv() using oandapyV20.API"
        )
