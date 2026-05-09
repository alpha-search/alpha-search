"""Access to official US SEC EDGAR filings and company financial data.

SEC EDGAR (Electronic Data Gathering, Analysis, and Retrieval system) provides
free access to company filings including 10-K, 10-Q, 8-K, and financial statements.

Setup:
    No API key required.  The SEC requires a descriptive User-Agent header.
    Set SEC_USER_AGENT environment variable, e.g.:
        export SEC_USER_AGENT="MyCompany ResearchBot contact@example.com"

    If not set, a default User-Agent is used (sufficient for low-volume use).

Endpoints used:
    - ``api.sec.gov/submissions/CIK{cik}.json`` — company submissions
    - ``api.sec.gov/api/xbrl/companyfacts/CIK{cik}.json`` — XBRL financial facts

References:
    - https://www.sec.gov/edgar
    - https://www.sec.gov/edgar/sec-api-documentation
"""

from __future__ import annotations

import logging
import os
import time
from datetime import datetime
from typing import Any, Dict, List

import pandas as pd
import requests

from alpha_search.data_sources.base import DataSource, SourceMeta

logger = logging.getLogger(__name__)

# CIK lookup for commonly requested tickers (zero-padded to 10 digits)
_CIK_MAP: Dict[str, str] = {
    "AAPL": "0000320193",
    "MSFT": "0000789019",
    "GOOGL": "0001652044",
    "AMZN": "0001018724",
    "TSLA": "0001318605",
    "META": "0001326801",
    "NVDA": "0001014128",
    "JPM": "0000019617",
    "JNJ": "0000200406",
    "V": "0001403161",
    "PG": "0000080424",
    "UNH": "0000731766",
    "HD": "0000354950",
    "MA": "0001141391",
    "BAC": "0000070858",
    "ABBV": "0001551152",
    "PFE": "0000078003",
    "KO": "0000021344",
    "WMT": "0000104169",
    "MRK": "0000310158",
    "PEP": "0000077476",
    "TMO": "0000097745",
    "COST": "0000909832",
    "DIS": "0001744489",
    "AVGO": "0001730168",
    "ADBE": "0000796343",
    "CSCO": "0000858877",
    "VZ": "0000732712",
    "NKE": "0000320187",
    "ABT": "0000001800",
    "CMCSA": "0001166691",
    "XOM": "0000034088",
    "CVX": "0000093410",
    "LLY": "0000059478",
    "CRM": "0001108524",
    "TXN": "0000097476",
    "ACN": "0001467373",
    "NEE": "0000753308",
    "QCOM": "0000804328",
    "IBM": "0000051143",
    "INTC": "0000050863",
    "LIN": "0001707925",
    "AMD": "0000002488",
    "HON": "0000773840",
    "PM": "0001413329",
    "AMGN": "0000318154",
    "SBUX": "0000829224",
    "UPS": "0001090727",
    "LOW": "0000060667",
    "MS": "0000895421",
    "GS": "0000886982",
    "BLK": "0001084424",
    "INTU": "0000896878",
    "SPGI": "0000064040",
    "CAT": "0000018230",
    "RTX": "0000101829",
    "PLD": "0001045609",
    "T": "0000732717",
    "ISRG": "0001035267",
    "GE": "0000040545",
    "BA": "0000012927",
    "DE": "0000315189",
}


class SECEdgarSource(DataSource):
    """SEC EDGAR — official US company filings and financial statements.

    Provides:
        - Company fundamental data from XBRL company facts
        - Recent filing history (10-K, 10-Q, 8-K, etc.)
        - No API key required

    This source does not support ``fetch_ohlcv`` — use :meth:`fetch_fundamentals`
    to retrieve financial statement data.

    Example::

        >>> src = SECEdgarSource()
        >>> src.is_available()
        True
        >>> info = src.fetch_fundamentals("AAPL")
        >>> info.get("entityName")
        'Apple Inc.'
    """

    meta = SourceMeta(
        name="sec_edgar",
        category="fundamentals",
        description=(
            "SEC EDGAR — official US company filings and financial statements. "
            "XBRL company facts, 10-K/10-Q data, no API key required."
        ),
        requires_api_key=False,
        free_tier=True,
        rate_limit="10 requests/sec",
        data_types=["fundamentals", "filings", "financial_statements"],
        coverage="us",
        homepage="https://www.sec.gov/edgar",
        docs_url="https://www.sec.gov/edgar/sec-api-documentation",
        install_cmd="pip install requests pandas",
        status="live",
    )

    BASE_URL = "https://www.sec.gov"
    _last_call: float = 0.0
    MIN_INTERVAL: float = 0.11  # ~10 requests/sec max (be conservative)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _get_headers() -> Dict[str, str]:
        """Build request headers with required User-Agent.

        The SEC requires a descriptive User-Agent that identifies the requester.

        Returns:
            Dictionary of HTTP headers.
        """
        user_agent = os.environ.get(
            "SEC_USER_AGENT",
            "AlphaSearch ResearchBot contact@example.com",
        )
        return {
            "User-Agent": user_agent,
            "Accept": "application/json",
        }

    def _rate_limited_get(self, url: str) -> requests.Response:
        """Execute a rate-limited GET request to the SEC API.

        Parameters:
            url: Full URL to request.

        Returns:
            The :class:`requests.Response` object.

        Raises:
            RuntimeError: If the request fails.
        """
        elapsed = time.time() - self._last_call
        if elapsed < self.MIN_INTERVAL:
            sleep_for = self.MIN_INTERVAL - elapsed
            logger.debug("SEC EDGAR rate limit: sleeping %.3fs", sleep_for)
            time.sleep(sleep_for)

        logger.debug("SEC EDGAR API call: %s", url[:80])

        try:
            resp = requests.get(url, headers=self._get_headers(), timeout=30)
            resp.raise_for_status()
        except requests.RequestException as exc:
            logger.error("SEC EDGAR request failed: %s", exc)
            raise RuntimeError(f"SEC EDGAR request failed: {exc}") from exc
        finally:
            self._last_call = time.time()

        return resp

    @classmethod
    def _get_cik(cls, symbol: str) -> str:
        """Get the CIK for a ticker symbol.

        Parameters:
            symbol: Ticker symbol, e.g. ``AAPL``.

        Returns:
            Zero-padded 10-digit CIK string.

        Raises:
            ValueError: If the CIK is not known for the symbol.
        """
        symbol_upper = symbol.upper()
        if symbol_upper in _CIK_MAP:
            return _CIK_MAP[symbol_upper]
        raise ValueError(
            f"CIK not known for symbol '{symbol}'. "
            f"Available symbols: {', '.join(sorted(_CIK_MAP.keys()))}. "
            f"You can look up CIKs at https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany"
        )

    # ------------------------------------------------------------------
    # Availability
    # ------------------------------------------------------------------

    def is_available(self) -> bool:
        """Check whether the SEC EDGAR API is reachable.

        Returns:
            ``True`` always — no API key required.
        """
        return True

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
        """Not supported — SEC EDGAR provides filings, not price data.

        Raises:
            NotImplementedError: Always — use :meth:`fetch_fundamentals` instead.
        """
        raise NotImplementedError(
            "SEC EDGAR does not provide OHLCV price data. "
            "Use fetch_fundamentals(symbol) to retrieve financial statement data."
        )

    # ------------------------------------------------------------------
    # Fundamentals
    # ------------------------------------------------------------------

    def fetch_fundamentals(self, symbol: str) -> Dict[str, Any]:
        """Fetch fundamental data for *symbol* from SEC EDGAR.

        Retrieves company facts from the XBRL API, including financial
        statement line items (revenue, net income, assets, liabilities, etc.)
        and recent filing history.

        Parameters:
            symbol: US stock ticker symbol, e.g. ``AAPL``, ``MSFT``.

        Returns:
            Dictionary containing:
                - ``entityName``: Company legal name
                - ``cik``: CIK identifier
                - ``recent_filings``: List of recent filings
                - ``facts``: Dictionary of XBRL financial facts keyed by topic

        Raises:
            ValueError: If the CIK is not known for the symbol.
            RuntimeError: If the API request fails.

        Example::

            >>> info = src.fetch_fundamentals("AAPL")
            >>> info["entityName"]
            'Apple Inc.'
            >>> len(info["recent_filings"]) > 0
            True
        """
        cik = self._get_cik(symbol)

        logger.info(
            "Fetching SEC EDGAR fundamentals: %s (CIK=%s)", symbol, cik,
        )

        # Fetch company facts
        facts_url = f"{self.BASE_URL}/api/xbrl/companyfacts/CIK{cik}.json"
        facts_resp = self._rate_limited_get(facts_url)
        facts_data = facts_resp.json()

        # Fetch recent submissions
        submissions_url = f"{self.BASE_URL}/submissions/CIK{cik}.json"
        submissions_resp = self._rate_limited_get(submissions_url)
        submissions_data = submissions_resp.json()

        # Extract recent filings
        recent_filings: List[Dict[str, str]] = []
        filings_data = submissions_data.get("filings", {}).get("recent", {})
        if filings_data:
            form_types = filings_data.get("form", [])
            filing_dates = filings_data.get("filingDate", [])
            accession_nums = filings_data.get("accessionNumber", [])
            primary_docs = filings_data.get("primaryDocument", [])

            for i in range(min(len(form_types), 20)):  # Last 20 filings
                recent_filings.append({
                    "form": form_types[i] if i < len(form_types) else "",
                    "filing_date": filing_dates[i] if i < len(filing_dates) else "",
                    "accession_number": accession_nums[i] if i < len(accession_nums) else "",
                    "primary_document": primary_docs[i] if i < len(primary_docs) else "",
                })

        # Build result
        result: Dict[str, Any] = {
            "symbol": symbol,
            "cik": cik,
            "entityName": facts_data.get("entityName", submissions_data.get("name", "")),
            "recent_filings": recent_filings,
            "facts": facts_data.get("facts", {}),
            "source": "sec_edgar",
            "fetched_at": datetime.utcnow().isoformat(),
        }

        logger.info(
            "SEC EDGAR fundamentals fetched for %s (%d recent filings, %d fact topics)",
            symbol,
            len(recent_filings),
            len(result["facts"]),
        )
        return result

    # ------------------------------------------------------------------
    # Financial statement extraction
    # ------------------------------------------------------------------

    def fetch_financial_statement(
        self,
        symbol: str,
        statement: str = "income",
        units: str = "USD",
    ) -> pd.DataFrame:
        """Fetch a specific financial statement as a time series.

        Extracts data from the XBRL company facts for income statement,
        balance sheet, or cash flow items.

        Parameters:
            symbol: US stock ticker symbol.
            statement: Statement type — ``"income"``, ``"balance"``,
                or ``"cash_flow"``.
            units: Currency unit — ``"USD"`` (default) or ``"shares"``.

        Returns:
            DataFrame with financial statement line items as columns and
            dates as index.

        Raises:
            ValueError: If no data is found for the requested statement.
            RuntimeError: If the API request fails.

        Example::

            >>> df = src.fetch_financial_statement("AAPL", "income")
            >>> df.columns  # doctest: +SKIP
            Index(['Revenue', 'NetIncomeLoss', ...], dtype='object')
        """
        cik = self._get_cik(symbol)

        logger.info(
            "Fetching SEC EDGAR %s statement: %s (CIK=%s)",
            statement, symbol, cik,
        )

        facts_url = f"{self.BASE_URL}/api/xbrl/companyfacts/CIK{cik}.json"
        resp = self._rate_limited_get(facts_url)
        data = resp.json()

        facts = data.get("facts", {})
        if not facts:
            raise ValueError(f"No XBRL facts available for {symbol}.")

        # Map statement type to common taxonomy keys
        statement_keys: Dict[str, List[str]] = {
            "income": [
                "RevenueFromContractWithCustomerExcludingAssessedTax",
                "Revenues",
                "SalesRevenueNet",
                "NetIncomeLoss",
                "OperatingIncomeLoss",
                "GrossProfit",
                "ResearchAndDevelopmentExpense",
                "SellingGeneralAndAdministrativeExpense",
                "IncomeTaxExpenseBenefit",
                "EarningsPerShareBasic",
                "EarningsPerShareDiluted",
            ],
            "balance": [
                "Assets",
                "CurrentAssets",
                "Liabilities",
                "CurrentLiabilities",
                "StockholdersEquity",
                "LongTermDebt",
                "CashAndCashEquivalentsAtCarryingValue",
                "PropertyPlantAndEquipmentNet",
                "Goodwill",
                "InventoryNet",
                "AccountsReceivableNetCurrent",
            ],
            "cash_flow": [
                "NetCashProvidedByUsedInOperatingActivities",
                "NetCashProvidedByUsedInInvestingActivities",
                "NetCashProvidedByUsedInFinancingActivities",
                "CapitalExpenditures",
                "DepreciationDepletionAndAmortization",
                "PaymentsOfDividends",
                "RepaymentsOfDebt",
                "ProceedsFromIssuanceOfDebt",
            ],
        }

        keys = statement_keys.get(statement, [])
        if not keys:
            raise ValueError(
                f"Unknown statement type '{statement}'. "
                f"Choose from: {', '.join(statement_keys.keys())}"
            )

        all_records: Dict[str, Dict[str, float]] = {}

        for taxonomy, topics in facts.items():
            for key in keys:
                if key not in topics:
                    continue
                units_data = topics[key].get("units", {})
                if units not in units_data:
                    # Try alternative unit labels
                    for u in units_data:
                        if u.upper() == units.upper():
                            units = u
                            break
                    else:
                        continue

                entries = units_data[units]
                for entry in entries:
                    form = entry.get("form", "")
                    # Focus on 10-K (annual) and 10-Q (quarterly) filings
                    if form not in ("10-K", "10-Q"):
                        continue
                    end_date = entry.get("end")
                    val = entry.get("val")
                    if end_date is None or val is None:
                        continue
                    if end_date not in all_records:
                        all_records[end_date] = {}
                    all_records[end_date][key] = val

        if not all_records:
            raise ValueError(
                f"No financial statement data found for {symbol} "
                f"(statement='{statement}', units='{units}')."
            )

        df = pd.DataFrame.from_dict(all_records, orient="index")
        df.index = pd.to_datetime(df.index)
        df = df.sort_index()
        df.index.name = "date"

        logger.info(
            "SEC EDGAR %s statement for %s: %d rows x %d columns",
            statement, symbol, len(df), len(df.columns),
        )
        return df

    def list_available_cik(self) -> Dict[str, str]:
        """Return the dictionary of ticker symbols to CIK mappings.

        Returns:
            Dictionary mapping uppercase ticker symbol → CIK string.
        """
        return _CIK_MAP.copy()


# ---------------------------------------------------------------------------
# Demo
# ---------------------------------------------------------------------------

if __name__ == "__main__":

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    src = SECEdgarSource()
    print(f"Source info: {src.info()}")

    # List available tickers
    print("\n--- Available Tickers ---")
    print(f"{len(src.list_available_cik())} tickers with known CIKs")

    # Demo fundamentals
    try:
        info = src.fetch_fundamentals("AAPL")
        print("\n--- Fundamentals (AAPL) ---")
        print(f"Entity Name: {info.get('entityName')}")
        print(f"CIK: {info.get('cik')}")
        print(f"Recent filings: {len(info.get('recent_filings', []))}")
        for filing in info.get("recent_filings", [])[:5]:
            print(f"  {filing['form']:6s} — {filing['filing_date']}")
    except Exception as exc:
        print(f"Fundamentals fetch failed: {exc}")

    # Demo financial statement
    try:
        df = src.fetch_financial_statement("AAPL", "income")
        print("\n--- Income Statement (AAPL) ---")
        print(df.tail())
    except Exception as exc:
        print(f"Income statement fetch failed: {exc}")
