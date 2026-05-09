"""Foreign exchange rates, currency conversion, and historical forex data via the forex-python library. (stub).

Forex Python -- currency exchange rates and conversion.

To activate this source:
    1. pip install forex-python
    2. Implement fetch_ohlcv() using forex_python.CurrencyRates

References:
    - https://forex-python.readthedocs.io/
"""

from __future__ import annotations

import logging

import pandas as pd

from alpha_search.data_sources.base import DataSource, SourceMeta

logger = logging.getLogger(__name__)


class ForexPythonSource(DataSource):
    """Forex Python -- real-time and historical forex rates.

    Status: **stub** -- implement the methods below to activate.
    """

    meta = SourceMeta(
        name="forex_python",
        category="forex_commodities",
        description="Forex Python -- currency exchange rates and conversion.",
        requires_api_key=False,
        free_tier=True,
        rate_limit="unspecified",
        data_types=["forex", "rates"],
        coverage="global",
        homepage="https://github.com/MicroPyramid/forex-python",
        docs_url="https://forex-python.readthedocs.io/",
        install_cmd="pip install forex-python",
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
            "ForexPythonSource is a stub. To activate it:\n"
            "1. pip install forex-python\n"
            "2. Implement fetch_ohlcv() using forex_python.CurrencyRates.get_rates()"
        )
