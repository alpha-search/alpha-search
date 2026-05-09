"""Economic statistics, forecasts, and policy analysis from the OECD covering 38 member countries and key partners. (stub).

OECD Data -- economic statistics from Organisation for Economic Co-operation and Development.

To activate this source:
    1. pip install pandasdmx
    2. Implement fetch_ohlcv() and fetch_macro() using pandasdmx

References:
    - https://pandasdmx.readthedocs.io/
"""

from __future__ import annotations

import logging

import pandas as pd

from alpha_search.data_sources.base import DataSource, SourceMeta

logger = logging.getLogger(__name__)


class OECDSource(DataSource):
    """OECD -- economic statistics and forecasts from 38 member countries.

    Status: **stub** -- implement the methods below to activate.
    """

    meta = SourceMeta(
        name="oecd",
        category="macro_economic",
        description="OECD Data -- economic statistics from Organisation for Economic Co-operation and Development.",
        requires_api_key=False,
        free_tier=True,
        rate_limit="unspecified",
        data_types=["macro", "gdp", "trade", "employment", "inflation"],
        coverage="global",
        homepage="https://data.oecd.org",
        docs_url="https://pandasdmx.readthedocs.io/",
        install_cmd="pip install pandasdmx",
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
            "OECDSource is a stub. To activate it:\n"
            "1. pip install pandasdmx\n"
            "2. Implement fetch_macro() using pandasdmx.Request('OECD').data()"
        )
