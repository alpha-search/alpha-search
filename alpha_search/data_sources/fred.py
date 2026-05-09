"""Access to 800,000+ economic time series from the Federal Reserve Bank of St. Louis.

FRED (Federal Reserve Economic Data) provides freely accessible economic data
including GDP, CPI, unemployment rates, interest rates, and 800,000+ other series.

Setup:
    No API key required for basic usage, but recommended for higher rate limits.
    Optionally set FRED_API_KEY environment variable for higher limits.

Common series IDs:
    - ``GDP``       — Gross Domestic Product (quarterly)
    - ``CPIAUCSL``  — Consumer Price Index for All Urban Consumers (monthly)
    - ``UNRATE``    — Civilian Unemployment Rate (monthly)
    - ``DFF``       — Federal Funds Effective Rate (daily)
    - ``T10Y2Y``    — 10-Year minus 2-Year Treasury Yield Spread (daily)
    - ``T10Y3M``    — 10-Year minus 3-Month Treasury Yield Spread (daily)
    - ``PAYEMS``    — Total Nonfarm Payrolls (monthly)
    - ``PCEC1``     — Personal Consumption Expenditures (monthly)
    - ``M2SL``      — M2 Money Stock (weekly)
    - ``INDPRO``    — Industrial Production Index (monthly)
    - ``RSXFS``     — Advance Retail Sales (monthly)
    - "HOUST"       - New Housing Units Started (monthly)

References:
    - https://fred.stlouisfed.org
    - https://fred.stlouisfed.org/docs/api/fred/
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any, Dict, List, Optional

import pandas as pd
import requests

from alpha_search.data_sources.base import DataSource, SourceMeta

logger = logging.getLogger(__name__)

# Well-known FRED series IDs for convenience
_COMMON_SERIES: Dict[str, str] = {
    "GDP": "Gross Domestic Product",
    "CPIAUCSL": "Consumer Price Index: All Urban Consumers",
    "UNRATE": "Unemployment Rate",
    "DFF": "Federal Funds Effective Rate",
    "T10Y2Y": "10-Year Treasury Constant Maturity Minus 2-Year",
    "T10Y3M": "10-Year Treasury Constant Maturity Minus 3-Month",
    "PAYEMS": "Total Nonfarm Payrolls",
    "PCEC1": "Personal Consumption Expenditures",
    "M2SL": "M2 Money Stock",
    "INDPRO": "Industrial Production Index",
    "RSXFS": "Advance Retail Sales",
    "HOUST": "New Privately Owned Housing Units Started",
    "BAMLH0A0HYM2": "ICE BofA US High Yield Option-Adjusted Spread",
    "VIXCLS": "CBOE Volatility Index",
    "DTWEXBGS": "Trade Weighted U.S. Dollar Index",
    "SP500": "S&P 500",
    "DJIA": "Dow Jones Industrial Average",
    "NASDAQCOM": "NASDAQ Composite Index",
    "TB3MS": "3-Month Treasury Bill Secondary Market Rate",
    "GS10": "10-Year Treasury Constant Maturity Rate",
    "MORTGAGE30US": "30-Year Fixed Rate Mortgage Average",
}


class FREDSource(DataSource):
    """FRED — Federal Reserve Economic Data from the St. Louis Fed.

    Provides:
        - 800,000+ economic time series
        - Macro indicators: GDP, CPI, unemployment, interest rates
        - No API key required for basic usage

    This source does not support ``fetch_ohlcv`` — use
    :meth:`fetch_macro` to retrieve economic indicator data.

    Example::

        >>> src = FREDSource()
        >>> src.is_available()
        True
        >>> df = src.fetch_macro("GDP", start="2020-01-01")
        >>> df.head()
                        value
        date
        2020-01-01  21561.139
        2020-04-01  19477.444
    """

    meta = SourceMeta(
        name="fred",
        category="macro_economic",
        description=(
            "FRED — Federal Reserve Economic Data, 800k+ time series. "
            "GDP, CPI, unemployment, interest rates, and more. "
            "No API key required."
        ),
        requires_api_key=False,
        free_tier=True,
        rate_limit="120 requests/min",
        data_types=["macro", "interest_rates", "gdp", "inflation", "employment"],
        coverage="us",
        homepage="https://fred.stlouisfed.org",
        docs_url="https://fred.stlouisfed.org/docs/api/fred/",
        install_cmd="pip install requests pandas",
        status="live",
    )

    BASE_URL = "https://api.stlouisfed.org/fred"
    _last_call: float = 0.0
    MIN_INTERVAL: float = 0.5  # 120 requests/min = 2/sec max

    # ------------------------------------------------------------------
    # Availability
    # ------------------------------------------------------------------

    def is_available(self) -> bool:
        """Check whether FRED API is reachable.

        Returns:
            ``True`` always — no API key or dependencies required for
            basic usage.
        """
        return True

    # ------------------------------------------------------------------
    # Rate limiting
    # ------------------------------------------------------------------

    def _rate_limited_get(
        self, endpoint: str, params: Optional[Dict[str, Any]] = None,
    ) -> requests.Response:
        """Execute a rate-limited GET request to the FRED API.

        Parameters:
            endpoint: API endpoint path (e.g. ``series/observations``).
            params: Optional query parameters.

        Returns:
            The :class:`requests.Response` object.

        Raises:
            RuntimeError: If the request fails.
        """
        elapsed = time.time() - self._last_call
        if elapsed < self.MIN_INTERVAL:
            sleep_for = self.MIN_INTERVAL - elapsed
            logger.debug("FRED rate limit: sleeping %.2fs", sleep_for)
            time.sleep(sleep_for)

        url = f"{self.BASE_URL}/{endpoint}"
        params = params or {}
        api_key = os.environ.get("FRED_API_KEY")
        if api_key:
            params["api_key"] = api_key
        params["file_type"] = "json"

        logger.debug("FRED API call: %s", endpoint)

        try:
            resp = requests.get(url, params=params, timeout=30)
            resp.raise_for_status()
        except requests.RequestException as exc:
            logger.error("FRED request failed: %s", exc)
            raise RuntimeError(f"FRED API request failed: {exc}") from exc
        finally:
            self._last_call = time.time()

        return resp

    # ------------------------------------------------------------------
    # OHLCV — not applicable
    # ------------------------------------------------------------------

    def fetch_ohlcv(
        self,
        symbol: str,
        start: str,
        end: str,
        interval: str = "1d",
    ) -> pd.DataFrame:
        """Not supported — FRED provides macro-economic data, not OHLCV prices.

        Raises:
            NotImplementedError: Always — use :meth:`fetch_macro` instead.
        """
        raise NotImplementedError(
            "FRED does not support OHLCV price data. "
            "Use fetch_macro(indicator) to retrieve economic time series. "
            f"Common indicators: {', '.join(list(_COMMON_SERIES.keys())[:8])}"
        )

    # ------------------------------------------------------------------
    # Macro data
    # ------------------------------------------------------------------

    def fetch_macro(
        self,
        indicator: str,
        start: Optional[str] = None,
        end: Optional[str] = None,
        frequency: Optional[str] = None,
        **kwargs: Any,
    ) -> pd.DataFrame:
        """Fetch a macro-economic indicator time series from FRED.

        Parameters:
            indicator: FRED series ID, e.g. ``"GDP"``, ``"CPIAUCSL"``,
                ``"UNRATE"``.  See ``_COMMON_SERIES`` for a list of
                well-known series IDs.
            start: Start date ``YYYY-MM-DD`` (optional).
            end: End date ``YYYY-MM-DD`` (optional).
            frequency: Data frequency for resampling — ``"d"``, ``"w"``,
                ``"m"``, ``"q"``, ``"sa"`` (semi-annual), ``"a"``.
            **kwargs: Additional parameters passed to the FRED API.

        Returns:
            DataFrame with columns ``[value]`` and a DatetimeIndex named
            ``date``.  Missing values are represented as ``NaN``.

        Raises:
            ValueError: If the series ID is not found or no data is returned.
            RuntimeError: If the API request fails.

        Example::

            >>> df = src.fetch_macro("GDP", start="2020-01-01", end="2023-12-31")
            >>> df.tail()
                           value
            date
            2023-07-01  27610.134
            2023-10-01  27939.098
        """
        logger.info(
            "Fetching FRED macro series: %s (%s to %s)",
            indicator, start or "beginning", end or "now",
        )

        params: Dict[str, Any] = {"series_id": indicator}
        if start:
            params["observation_start"] = start
        if end:
            params["observation_end"] = end
        if frequency:
            params["frequency"] = frequency
        params.update(kwargs)

        resp = self._rate_limited_get("series/observations", params)
        data = resp.json()

        if "error_code" in data and data["error_code"] != 0:
            raise ValueError(
                f"FRED API error for series '{indicator}': "
                f"{data.get('error_message', 'Unknown error')}"
            )

        observations = data.get("observations", [])
        if not observations:
            raise ValueError(
                f"No observations returned for series '{indicator}'. "
                f"Check that the series ID is valid."
            )

        # Parse observations into DataFrame
        records = []
        for obs in observations:
            date_str = obs.get("date")
            value_str = obs.get("value")
            # FRED uses "." for missing values
            if value_str is None or value_str == ".":
                value = float("nan")
            else:
                try:
                    value = float(value_str)
                except (ValueError, TypeError):
                    value = float("nan")
            records.append({"date": date_str, "value": value})

        df = pd.DataFrame(records)
        df["date"] = pd.to_datetime(df["date"])
        df = df.set_index("date")
        df = df.sort_index()

        # Drop rows where all values are NaN
        df = df.dropna(how="all")

        if df.empty:
            raise ValueError(
                f"No valid data for series '{indicator}' in the given range."
            )

        logger.info(
            "FRED returned %d observations for %s", len(df), indicator,
        )
        return df

    # ------------------------------------------------------------------
    # Series discovery
    # ------------------------------------------------------------------

    def search_series(
        self,
        query: str,
        limit: int = 10,
    ) -> List[Dict[str, str]]:
        """Search for FRED series by keyword.

        Parameters:
            query: Search keyword, e.g. ``"inflation"``, ``"interest rate"``.
            limit: Maximum number of results to return.

        Returns:
            List of dictionaries with series metadata (id, title, frequency, etc.).

        Raises:
            RuntimeError: If the API request fails.
        """
        logger.info("Searching FRED series: '%s'", query)

        params = {
            "search_text": query,
            "limit": limit,
        }

        resp = self._rate_limited_get("series/search", params)
        data = resp.json()

        series_list = data.get("seriess", [])
        results: List[Dict[str, str]] = []
        for s in series_list[:limit]:
            results.append({
                "id": s.get("id", ""),
                "title": s.get("title", ""),
                "frequency": s.get("frequency", ""),
                "units": s.get("units", ""),
                "seasonal_adjustment": s.get("seasonal_adjustment", ""),
                "last_updated": s.get("last_updated", ""),
                "popularity": str(s.get("popularity", "")),
            })

        return results

    def list_common_series(self) -> Dict[str, str]:
        """Return a dictionary of commonly used FRED series IDs and their descriptions.

        Returns:
            Dictionary mapping series ID → description.
        """
        return _COMMON_SERIES.copy()

    # ------------------------------------------------------------------
    # Multi-series helper
    # ------------------------------------------------------------------

    def fetch_multiple_macro(
        self,
        indicators: List[str],
        start: Optional[str] = None,
        end: Optional[str] = None,
    ) -> Dict[str, pd.DataFrame]:
        """Fetch multiple macro-economic indicators in one call.

        Parameters:
            indicators: List of FRED series IDs, e.g. ``["GDP", "UNRATE"]``.
            start: Start date ``YYYY-MM-DD`` (optional).
            end: End date ``YYYY-MM-DD`` (optional).

        Returns:
            Dictionary mapping series ID -> DataFrame.

        Example::

            >>> data = src.fetch_multiple_macro(
            ...     ["GDP", "CPIAUCSL", "UNRATE"], start="2020-01-01"
            ... )
            >>> data["UNRATE"].tail()
                          value
            date
            2024-01-01    3.7
        """
        result: Dict[str, pd.DataFrame] = {}
        for indicator in indicators:
            try:
                df = self.fetch_macro(indicator, start=start, end=end)
                result[indicator] = df
            except Exception as exc:
                logger.warning("Failed to fetch %s: %s", indicator, exc)
        return result


# ---------------------------------------------------------------------------
# Demo
# ---------------------------------------------------------------------------

if __name__ == "__main__":

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    src = FREDSource()
    print(f"Source info: {src.info()}")

    # List common series
    print("\n--- Common FRED Series ---")
    for series_id, desc in list(src.list_common_series().items())[:10]:
        print(f"  {series_id:20s} — {desc}")

    # Demo GDP
    try:
        df = src.fetch_macro("GDP", start="2020-01-01", end="2023-12-31")
        print("\n--- GDP ---")
        print(df.tail())
    except Exception as exc:
        print(f"GDP fetch failed: {exc}")

    # Demo Unemployment Rate
    try:
        df = src.fetch_macro("UNRATE", start="2023-01-01")
        print("\n--- Unemployment Rate ---")
        print(df.tail())
    except Exception as exc:
        print(f"UNRATE fetch failed: {exc}")

    # Demo search
    try:
        results = src.search_series("inflation", limit=5)
        print("\n--- Search: 'inflation' ---")
        for r in results:
            print(f"  {r['id']:15s} — {r['title']}")
    except Exception as exc:
        print(f"Search failed: {exc}")
