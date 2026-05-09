"""Free weather data API providing historical weather, climate forecasts, and meteorological data for location-based analysis. (stub).

Open-Meteo -- free weather data API for climate analytics.

To activate this source:
    1. No API key required
    2. pip install openmeteo-requests
    3. Implement weather data fetching

References:
    - https://open-meteo.com/en/docs
"""

from __future__ import annotations

import logging

import pandas as pd

from alpha_search.data_sources.base import DataSource, SourceMeta

logger = logging.getLogger(__name__)


class OpenMeteoSource(DataSource):
    """Open-Meteo -- free weather and climate data.

    Status: **stub** -- implement the methods below to activate.
    """

    meta = SourceMeta(
        name="openmeteo",
        category="alternative",
        description="Open-Meteo -- free weather data API for climate analytics.",
        requires_api_key=False,
        free_tier=True,
        rate_limit="unspecified",
        data_types=["weather", "climate", "forecasts"],
        coverage="global",
        homepage="https://open-meteo.com",
        docs_url="https://open-meteo.com/en/docs",
        install_cmd="pip install openmeteo-requests",
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
            "OpenMeteoSource is a stub. To activate it:\n"
            "1. No API key required\n"
            "2. pip install openmeteo-requests\n"
            "3. Implement weather data fetching using openmeteo_requests.Client"
        )
