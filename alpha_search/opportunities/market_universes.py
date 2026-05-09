"""Global multi-asset market universe definitions and utilities.

Defines ticker lists, sector mappings, and benchmark references for:
* Indian equities (NIFTY 50) via ``.NS`` suffix
* US equities (S&P 500, NASDAQ 100, DOW 30) via plain ticker
* Cryptocurrency (BTC, ETH, BNB, SOL, XRP, ADA) via ``-USD`` suffix
* Benchmark indices for beta and correlation calculations

All tickers are compatible with Yahoo Finance (``yfinance``).
"""

from __future__ import annotations

from typing import Dict, List, Optional

import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# NIFTY 50 — Indian equities (Yahoo Finance format with .NS suffix)
# ---------------------------------------------------------------------------
NIFTY50_TICKERS: Dict[str, str] = {
    "RELIANCE.NS": "Reliance Industries",
    "TCS.NS": "Tata Consultancy Services",
    "HDFCBANK.NS": "HDFC Bank",
    "ICICIBANK.NS": "ICICI Bank",
    "INFY.NS": "Infosys",
    "HINDUNILVR.NS": "Hindustan Unilever",
    "ITC.NS": "ITC Limited",
    "SBIN.NS": "State Bank of India",
    "BHARTIARTL.NS": "Bharti Airtel",
    "KOTAKBANK.NS": "Kotak Mahindra Bank",
    "LT.NS": "Larsen & Toubro",
    "AXISBANK.NS": "Axis Bank",
    "ASIANPAINT.NS": "Asian Paints",
    "MARUTI.NS": "Maruti Suzuki",
    "TITAN.NS": "Titan Company",
    "SUNPHARMA.NS": "Sun Pharmaceutical",
    "BAJFINANCE.NS": "Bajaj Finance",
    "WIPRO.NS": "Wipro",
    "NESTLEIND.NS": "Nestle India",
    "ULTRACEMCO.NS": "UltraTech Cement",
    "HCLTECH.NS": "HCL Technologies",
    "BAJAJFINSV.NS": "Bajaj Finserv",
    "ADANIENT.NS": "Adani Enterprises",
    "NTPC.NS": "NTPC Limited",
    "TATAMOTORS.NS": "Tata Motors",
    "POWERGRID.NS": "Power Grid Corporation",
    "ONGC.NS": "Oil & Natural Gas Corporation",
    "COALINDIA.NS": "Coal India",
    "TATASTEEL.NS": "Tata Steel",
    "ADANIPORTS.NS": "Adani Ports & SEZ",
    "BAJAJ-AUTO.NS": "Bajaj Auto",
    "M&M.NS": "Mahindra & Mahindra",
    "GRASIM.NS": "Grasim Industries",
    "JSWSTEEL.NS": "JSW Steel",
    "APOLLOHOSP.NS": "Apollo Hospitals",
    "BRITANNIA.NS": "Britannia Industries",
    "CIPLA.NS": "Cipla Limited",
    "EICHERMOT.NS": "Eicher Motors",
    "DRREDDY.NS": "Dr. Reddy's Laboratories",
    "HEROMOTOCO.NS": "Hero MotoCorp",
    "HINDALCO.NS": "Hindalco Industries",
    "INDUSINDBK.NS": "IndusInd Bank",
    "SBILIFE.NS": "SBI Life Insurance",
    "TECHM.NS": "Tech Mahindra",
    "UPL.NS": "UPL Limited",
    "HDFCLIFE.NS": "HDFC Life Insurance",
    "TATACONSUM.NS": "Tata Consumer Products",
    "DIVISLAB.NS": "Divi's Laboratories",
    "SHRIRAMFIN.NS": "Shriram Finance",
    "BPCL.NS": "Bharat Petroleum",
}

# Deduplicate while preserving order
_seen = set()
NIFTY50_TICKERS_ORDERED: Dict[str, str] = {}
for k, v in NIFTY50_TICKERS.items():
    if k not in _seen:
        _seen.add(k)
        NIFTY50_TICKERS_ORDERED[k] = v
NIFTY50_TICKERS = NIFTY50_TICKERS_ORDERED


# ---------------------------------------------------------------------------
# S&P 500 — US large-cap equities (plain ticker, no suffix)
# ---------------------------------------------------------------------------
SP500_TICKERS: Dict[str, str] = {
    "AAPL": "Apple Inc.",
    "MSFT": "Microsoft Corp.",
    "GOOGL": "Alphabet Inc.",
    "AMZN": "Amazon.com Inc.",
    "NVDA": "NVIDIA Corp.",
    "META": "Meta Platforms Inc.",
    "TSLA": "Tesla Inc.",
    "BRK-B": "Berkshire Hathaway",
    "UNH": "UnitedHealth Group",
    "JPM": "JPMorgan Chase",
    "V": "Visa Inc.",
    "JNJ": "Johnson & Johnson",
    "WMT": "Walmart Inc.",
    "MA": "Mastercard Inc.",
    "PG": "Procter & Gamble",
    "ORCL": "Oracle Corp.",
    "HD": "Home Depot",
    "BAC": "Bank of America",
    "KO": "Coca-Cola Co.",
    "MRK": "Merck & Co.",
    "PEP": "PepsiCo Inc.",
    "COST": "Costco Wholesale",
    "TMO": "Thermo Fisher Scientific",
    "DIS": "Walt Disney Co.",
    "ADBE": "Adobe Inc.",
    "PFE": "Pfizer Inc.",
    "NFLX": "Netflix Inc.",
    "ABT": "Abbott Laboratories",
    "CRM": "Salesforce Inc.",
    "AMD": "Advanced Micro Devices",
}

SP500_SECTORS: Dict[str, str] = {
    "AAPL": "Technology",
    "MSFT": "Technology",
    "GOOGL": "Communication Services",
    "AMZN": "Consumer Discretionary",
    "NVDA": "Technology",
    "META": "Communication Services",
    "TSLA": "Consumer Discretionary",
    "BRK-B": "Financials",
    "UNH": "Health Care",
    "JPM": "Financials",
    "V": "Financials",
    "JNJ": "Health Care",
    "WMT": "Consumer Staples",
    "MA": "Financials",
    "PG": "Consumer Staples",
    "ORCL": "Technology",
    "HD": "Consumer Discretionary",
    "BAC": "Financials",
    "KO": "Consumer Staples",
    "MRK": "Health Care",
    "PEP": "Consumer Staples",
    "COST": "Consumer Staples",
    "TMO": "Health Care",
    "DIS": "Communication Services",
    "ADBE": "Technology",
    "PFE": "Health Care",
    "NFLX": "Communication Services",
    "ABT": "Health Care",
    "CRM": "Technology",
    "AMD": "Technology",
}


# ---------------------------------------------------------------------------
# NASDAQ 100 — US tech-heavy equities
# ---------------------------------------------------------------------------
NASDAQ100_TICKERS: Dict[str, str] = {
    "AAPL": "Apple Inc.",
    "MSFT": "Microsoft Corp.",
    "GOOGL": "Alphabet Inc.",
    "AMZN": "Amazon.com Inc.",
    "NVDA": "NVIDIA Corp.",
    "META": "Meta Platforms Inc.",
    "TSLA": "Tesla Inc.",
    "AVGO": "Broadcom Inc.",
    "PEP": "PepsiCo Inc.",
    "COST": "Costco Wholesale",
    "NFLX": "Netflix Inc.",
    "ADBE": "Adobe Inc.",
    "AMD": "Advanced Micro Devices",
    "CMCSA": "Comcast Corp.",
    "TMUS": "T-Mobile US",
    "INTC": "Intel Corp.",
    "INTU": "Intuit Inc.",
    "QCOM": "Qualcomm Inc.",
    "AMGN": "Amgen Inc.",
    "HON": "Honeywell International",
}

NASDAQ100_SECTORS: Dict[str, str] = {
    "AAPL": "Technology",
    "MSFT": "Technology",
    "GOOGL": "Communication Services",
    "AMZN": "Consumer Discretionary",
    "NVDA": "Technology",
    "META": "Communication Services",
    "TSLA": "Consumer Discretionary",
    "AVGO": "Technology",
    "PEP": "Consumer Staples",
    "COST": "Consumer Staples",
    "NFLX": "Communication Services",
    "ADBE": "Technology",
    "AMD": "Technology",
    "CMCSA": "Communication Services",
    "TMUS": "Communication Services",
    "INTC": "Technology",
    "INTU": "Technology",
    "QCOM": "Technology",
    "AMGN": "Health Care",
    "HON": "Industrials",
}


# ---------------------------------------------------------------------------
# DOW 30 — US blue-chip equities
# ---------------------------------------------------------------------------
DOW30_TICKERS: Dict[str, str] = {
    "AAPL": "Apple Inc.",
    "MSFT": "Microsoft Corp.",
    "V": "Visa Inc.",
    "JPM": "JPMorgan Chase",
    "WMT": "Walmart Inc.",
    "JNJ": "Johnson & Johnson",
    "PG": "Procter & Gamble",
    "HD": "Home Depot",
    "UNH": "UnitedHealth Group",
    "MRK": "Merck & Co.",
    "KO": "Coca-Cola Co.",
    "CSCO": "Cisco Systems",
    "MCD": "McDonald's Corp.",
    "DIS": "Walt Disney Co.",
    "TRV": "Travelers Companies",
    "VZ": "Verizon Communications",
    "AMGN": "Amgen Inc.",
    "HON": "Honeywell International",
    "IBM": "IBM Corp.",
    "GS": "Goldman Sachs",
    "BA": "Boeing Co.",
    "CVX": "Chevron Corp.",
    "CAT": "Caterpillar Inc.",
    "MMM": "3M Company",
    "NKE": "Nike Inc.",
    "AXP": "American Express",
    "INTC": "Intel Corp.",
    "DOW": "Dow Inc.",
    "WBA": "Walgreens Boots Alliance",
}

DOW30_SECTORS: Dict[str, str] = {
    "AAPL": "Technology",
    "MSFT": "Technology",
    "V": "Financials",
    "JPM": "Financials",
    "WMT": "Consumer Staples",
    "JNJ": "Health Care",
    "PG": "Consumer Staples",
    "HD": "Consumer Discretionary",
    "UNH": "Health Care",
    "MRK": "Health Care",
    "KO": "Consumer Staples",
    "CSCO": "Technology",
    "MCD": "Consumer Discretionary",
    "DIS": "Communication Services",
    "TRV": "Financials",
    "VZ": "Communication Services",
    "AMGN": "Health Care",
    "HON": "Industrials",
    "IBM": "Technology",
    "GS": "Financials",
    "BA": "Industrials",
    "CVX": "Energy",
    "CAT": "Industrials",
    "MMM": "Industrials",
    "NKE": "Consumer Discretionary",
    "AXP": "Financials",
    "INTC": "Technology",
    "DOW": "Materials",
    "WBA": "Consumer Staples",
}


# ---------------------------------------------------------------------------
# FTSE 100 — UK large-cap equities
# ---------------------------------------------------------------------------
FTSE100_TICKERS: Dict[str, str] = {
    "SHEL.L": "Shell plc",
    "AZN.L": "AstraZeneca plc",
    "HSBA.L": "HSBC Holdings",
    "ULVR.L": "Unilever plc",
    "BP.L": "BP plc",
    "RIO.L": "Rio Tinto",
    "GSK.L": "GSK plc",
    "DGE.L": "Diageo plc",
    "BARC.L": "Barclays",
    "LSEG.L": "London Stock Exchange Group",
    "REL.L": "Relx plc",
    "NG.L": "National Grid",
    "AAL.L": "Anglo American",
    "NWG.L": "NatWest Group",
    "JD.L": "JD Sports Fashion",
    "TSCO.L": "Tesco plc",
    "LLOY.L": "Lloyds Banking Group",
}

FTSE100_SECTORS: Dict[str, str] = {
    "SHEL.L": "Energy",
    "AZN.L": "Health Care",
    "HSBA.L": "Financials",
    "ULVR.L": "Consumer Staples",
    "BP.L": "Energy",
    "RIO.L": "Materials",
    "GSK.L": "Health Care",
    "DGE.L": "Consumer Staples",
    "BARC.L": "Financials",
    "LSEG.L": "Financials",
    "REL.L": "Industrials",
    "NG.L": "Utilities",
    "AAL.L": "Materials",
    "NWG.L": "Financials",
    "JD.L": "Consumer Discretionary",
    "TSCO.L": "Consumer Staples",
    "LLOY.L": "Financials",
}


# ---------------------------------------------------------------------------
# Cryptocurrency — major tokens (Yahoo Finance format with -USD suffix)
# ---------------------------------------------------------------------------
CRYPTO_TICKERS: Dict[str, str] = {
    "BTC-USD": "Bitcoin",
    "ETH-USD": "Ethereum",
    "BNB-USD": "Binance Coin",
    "SOL-USD": "Solana",
    "XRP-USD": "XRP",
    "ADA-USD": "Cardano",
}

CRYPTO_SECTORS: Dict[str, str] = {
    "BTC-USD": "Layer 1",
    "ETH-USD": "Layer 1",
    "BNB-USD": "Exchange",
    "SOL-USD": "Layer 1",
    "XRP-USD": "Payments",
    "ADA-USD": "Layer 1",
}


# ---------------------------------------------------------------------------
# FX (Forex) — major currency pairs
# ---------------------------------------------------------------------------
FX_PAIRS: Dict[str, str] = {
    "EURUSD=X": "EUR/USD",
    "GBPUSD=X": "GBP/USD",
    "USDJPY=X": "USD/JPY",
    "USDCHF=X": "USD/CHF",
    "AUDUSD=X": "AUD/USD",
    "USDCAD=X": "USD/CAD",
    "NZDUSD=X": "NZD/USD",
    "EURGBP=X": "EUR/GBP",
    "EURJPY=X": "EUR/JPY",
    "GBPJPY=X": "GBP/JPY",
}

FX_SECTORS: Dict[str, str] = {
    "EURUSD=X": "Major",
    "GBPUSD=X": "Major",
    "USDJPY=X": "Major",
    "USDCHF=X": "Major",
    "AUDUSD=X": "Major",
    "USDCAD=X": "Major",
    "NZDUSD=X": "Major",
    "EURGBP=X": "Cross",
    "EURJPY=X": "Cross",
    "GBPJPY=X": "Cross",
}


# ---------------------------------------------------------------------------
# Commodities — major commodity futures (Yahoo Finance format)
# ---------------------------------------------------------------------------
COMMODITY_TICKERS: Dict[str, str] = {
    "GC=F": "Gold",
    "SI=F": "Silver",
    "CL=F": "Crude Oil (WTI)",
    "BZ=F": "Brent Crude Oil",
    "NG=F": "Natural Gas",
    "HG=F": "Copper",
    "PL=F": "Platinum",
    "PA=F": "Palladium",
    "ZC=F": "Corn",
    "ZS=F": "Soybeans",
    "ZW=F": "Wheat",
    "CT=F": "Cotton",
}

COMMODITY_SECTORS: Dict[str, str] = {
    "GC=F": "Precious Metals",
    "SI=F": "Precious Metals",
    "CL=F": "Energy",
    "BZ=F": "Energy",
    "NG=F": "Energy",
    "HG=F": "Industrial Metals",
    "PL=F": "Precious Metals",
    "PA=F": "Precious Metals",
    "ZC=F": "Agriculture",
    "ZS=F": "Agriculture",
    "ZW=F": "Agriculture",
    "CT=F": "Agriculture",
}


# ---------------------------------------------------------------------------
# Sector mapping for NIFTY 50 constituents
# ---------------------------------------------------------------------------
SECTOR_MAP: Dict[str, str] = {
    "RELIANCE.NS": "Energy",
    "TCS.NS": "IT",
    "HDFCBANK.NS": "Financial Services",
    "ICICIBANK.NS": "Financial Services",
    "INFY.NS": "IT",
    "HINDUNILVR.NS": "Consumer Goods",
    "ITC.NS": "Consumer Goods",
    "SBIN.NS": "Financial Services",
    "BHARTIARTL.NS": "Telecom",
    "KOTAKBANK.NS": "Financial Services",
    "LT.NS": "Construction",
    "AXISBANK.NS": "Financial Services",
    "ASIANPAINT.NS": "Consumer Goods",
    "MARUTI.NS": "Automobile",
    "TITAN.NS": "Consumer Goods",
    "SUNPHARMA.NS": "Pharma",
    "BAJFINANCE.NS": "Financial Services",
    "WIPRO.NS": "IT",
    "NESTLEIND.NS": "Consumer Goods",
    "ULTRACEMCO.NS": "Cement",
    "HCLTECH.NS": "IT",
    "BAJAJFINSV.NS": "Financial Services",
    "ADANIENT.NS": "Conglomerate",
    "NTPC.NS": "Energy",
    "TATAMOTORS.NS": "Automobile",
    "POWERGRID.NS": "Energy",
    "ONGC.NS": "Energy",
    "COALINDIA.NS": "Energy",
    "TATASTEEL.NS": "Metals",
    "ADANIPORTS.NS": "Infrastructure",
    "BAJAJ-AUTO.NS": "Automobile",
    "M&M.NS": "Automobile",
    "GRASIM.NS": "Diversified",
    "JSWSTEEL.NS": "Metals",
    "APOLLOHOSP.NS": "Healthcare",
    "BRITANNIA.NS": "Consumer Goods",
    "CIPLA.NS": "Pharma",
    "EICHERMOT.NS": "Automobile",
    "DRREDDY.NS": "Pharma",
    "HEROMOTOCO.NS": "Automobile",
    "HINDALCO.NS": "Metals",
    "INDUSINDBK.NS": "Financial Services",
    "SBILIFE.NS": "Financial Services",
    "TECHM.NS": "IT",
    "UPL.NS": "Chemicals",
    "HDFCLIFE.NS": "Financial Services",
    "TATACONSUM.NS": "Consumer Goods",
    "DIVISLAB.NS": "Pharma",
    "SHRIRAMFIN.NS": "Financial Services",
    "BPCL.NS": "Energy",
}


# ---------------------------------------------------------------------------
# Sector groups for NIFTY 50
# ---------------------------------------------------------------------------
SECTOR_GROUPS: Dict[str, List[str]] = {
    "Financial Services": [
        "HDFCBANK.NS", "ICICIBANK.NS", "SBIN.NS", "KOTAKBANK.NS",
        "AXISBANK.NS", "BAJFINANCE.NS", "BAJAJFINSV.NS", "INDUSINDBK.NS",
        "SBILIFE.NS", "HDFCLIFE.NS", "SHRIRAMFIN.NS",
    ],
    "IT": [
        "TCS.NS", "INFY.NS", "WIPRO.NS", "HCLTECH.NS", "TECHM.NS",
    ],
    "Energy": [
        "RELIANCE.NS", "ONGC.NS", "NTPC.NS", "POWERGRID.NS",
        "COALINDIA.NS", "BPCL.NS",
    ],
    "Consumer Goods": [
        "HINDUNILVR.NS", "ITC.NS", "ASIANPAINT.NS", "TITAN.NS",
        "NESTLEIND.NS", "BRITANNIA.NS", "TATACONSUM.NS",
    ],
    "Automobile": [
        "MARUTI.NS", "TATAMOTORS.NS", "BAJAJ-AUTO.NS", "M&M.NS",
        "EICHERMOT.NS", "HEROMOTOCO.NS",
    ],
    "Pharma": [
        "SUNPHARMA.NS", "CIPLA.NS", "DRREDDY.NS", "DIVISLAB.NS",
    ],
    "Metals": [
        "TATASTEEL.NS", "HINDALCO.NS", "JSWSTEEL.NS",
    ],
}


# ---------------------------------------------------------------------------
# Benchmark indices
# ---------------------------------------------------------------------------
BENCHMARKS: Dict[str, str] = {
    "^NSEI": "NIFTY 50",
    "^GSPC": "S&P 500",
    "^IXIC": "NASDAQ",
    "^DJI": "Dow Jones",
    "^FTSE": "FTSE 100",
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_nifty50_tickers() -> List[str]:
    """Return the ordered list of NIFTY 50 ticker symbols (``.NS`` suffix).

    Returns
    -------
    list[str]
        E.g. ``["RELIANCE.NS", "TCS.NS", ...]``.
    """
    return list(NIFTY50_TICKERS.keys())


def get_sp500_tickers() -> List[str]:
    """Return the S&P 500 representative ticker list.

    Returns
    -------
    list[str]
        E.g. ``["AAPL", "MSFT", ...]``.
    """
    return list(SP500_TICKERS.keys())


def get_nasdaq100_tickers() -> List[str]:
    """Return the NASDAQ 100 representative ticker list.

    Returns
    -------
    list[str]
        E.g. ``["AAPL", "MSFT", ...]``.
    """
    return list(NASDAQ100_TICKERS.keys())


def get_dow30_tickers() -> List[str]:
    """Return the DOW 30 representative ticker list.

    Returns
    -------
    list[str]
        E.g. ``["AAPL", "MSFT", ...]``.
    """
    return list(DOW30_TICKERS.keys())


def get_ftse100_tickers() -> List[str]:
    """Return the FTSE 100 representative ticker list.

    Returns
    -------
    list[str]
        E.g. ``["SHEL.L", "AZN.L", ...]``.
    """
    return list(FTSE100_TICKERS.keys())


def get_crypto_tickers() -> List[str]:
    """Return the cryptocurrency ticker list (``-USD`` suffix).

    Returns
    -------
    list[str]
        E.g. ``["BTC-USD", "ETH-USD", ...]``.
    """
    return list(CRYPTO_TICKERS.keys())


def get_fx_pairs() -> List[str]:
    """Return the FX (forex) currency pair list.

    Returns
    -------
    list[str]
        E.g. ``["EURUSD=X", "GBPUSD=X", ...]``.
    """
    return list(FX_PAIRS.keys())


def get_commodity_tickers() -> List[str]:
    """Return the commodity futures ticker list.

    Returns
    -------
    list[str]
        E.g. ``["GC=F", "SI=F", ...]``.
    """
    return list(COMMODITY_TICKERS.keys())


# ---------------------------------------------------------------------------
# Unified universe lookup
# ---------------------------------------------------------------------------

_ALL_UNIVERSE_MAP: Dict[str, List[str]] = {
    "NIFTY50": get_nifty50_tickers(),
    "NIFTY 50": get_nifty50_tickers(),
    "SP500": get_sp500_tickers(),
    "S&P500": get_sp500_tickers(),
    "S&P 500": get_sp500_tickers(),
    "NASDAQ100": get_nasdaq100_tickers(),
    "NASDAQ 100": get_nasdaq100_tickers(),
    "DOW30": get_dow30_tickers(),
    "DOW 30": get_dow30_tickers(),
    "FTSE100": get_ftse100_tickers(),
    "FTSE 100": get_ftse100_tickers(),
    "CRYPTO": get_crypto_tickers(),
    "FX": get_fx_pairs(),
    "FOREX": get_fx_pairs(),
    "COMMODITIES": get_commodity_tickers(),
    "COMMODITY": get_commodity_tickers(),
}

_ALL_NAME_MAPS: Dict[str, Dict[str, str]] = {
    "NIFTY50": NIFTY50_TICKERS,
    "SP500": SP500_TICKERS,
    "NASDAQ100": NASDAQ100_TICKERS,
    "DOW30": DOW30_TICKERS,
    "FTSE100": FTSE100_TICKERS,
    "CRYPTO": CRYPTO_TICKERS,
    "FX": FX_PAIRS,
    "COMMODITIES": COMMODITY_TICKERS,
}

_ALL_SECTOR_MAPS: Dict[str, Dict[str, str]] = {
    "NIFTY50": SECTOR_MAP,
    "SP500": SP500_SECTORS,
    "NASDAQ100": NASDAQ100_SECTORS,
    "DOW30": DOW30_SECTORS,
    "FTSE100": FTSE100_SECTORS,
    "CRYPTO": CRYPTO_SECTORS,
    "FX": FX_SECTORS,
    "COMMODITIES": COMMODITY_SECTORS,
}


def get_universe_tickers(universe: str) -> List[str]:
    """Return tickers for a named market universe.

    Supported universe identifiers:
    * ``"NIFTY50"`` / ``"NIFTY 50"`` — NIFTY 50 Indian equities (``.NS``)
    * ``"SP500"`` / ``"S&P500"`` / ``"S&P 500"`` — S&P 500 US equities
    * ``"NASDAQ100"`` / ``"NASDAQ 100"`` — NASDAQ 100 US equities
    * ``"DOW30"`` / ``"DOW 30"`` — Dow Jones 30 US equities
    * ``"FTSE100"`` / ``"FTSE 100"`` — FTSE 100 UK equities
    * ``"CRYPTO"`` — Major cryptocurrencies (``-USD``)
    * ``"FX"`` / ``"FOREX"`` — Major forex pairs
    * ``"COMMODITIES"`` — Major commodity futures
    * Comma-separated tickers — returned as-is

    Parameters
    ----------
    universe : str
        Universe identifier or comma-separated ticker list.

    Returns
    -------
    list[str]
        List of ticker strings.

    Raises
    ------
    ValueError
        If *universe* is not a recognised identifier.
    """
    key = universe.strip().upper()
    if key in _ALL_UNIVERSE_MAP:
        return _ALL_UNIVERSE_MAP[key].copy()

    # Try comma-separated tickers
    if "," in universe:
        return [t.strip() for t in universe.split(",") if t.strip()]

    raise ValueError(
        f"Unknown universe: {universe!r}. "
        f"Use one of: {', '.join(sorted(set(k for k in _ALL_UNIVERSE_MAP if ' ' not in k)))} "
        f"or provide a comma-separated ticker list."
    )


def get_company_name(ticker: str) -> str:
    """Return the company / asset name for a given ticker.

    Searches across all supported universes (NIFTY 50, S&P 500,
    NASDAQ 100, DOW 30, FTSE 100, Crypto, FX, Commodities).

    Parameters
    ----------
    ticker : str
        Ticker symbol (e.g. ``"RELIANCE.NS"``, ``"AAPL"``, ``"BTC-USD"``).

    Returns
    -------
    str
        Company or asset name, or the ticker itself if unknown.
    """
    for name_map in _ALL_NAME_MAPS.values():
        if ticker in name_map:
            return name_map[ticker]
    return ticker


def get_sector(ticker: str) -> str:
    """Return the sector / category for a given ticker.

    Searches across all supported universes.

    Parameters
    ----------
    ticker : str
        Ticker symbol.

    Returns
    -------
    str
        Sector name, or ``"Unknown"`` if not mapped.
    """
    for sector_map in _ALL_SECTOR_MAPS.values():
        if ticker in sector_map:
            return sector_map[ticker]
    return "Unknown"


def get_sector_tickers(sector: str) -> List[str]:
    """Return all NIFTY 50 tickers belonging to *sector*.

    Parameters
    ----------
    sector : str
        Sector name (e.g. ``"Financial Services"``).

    Returns
    -------
    list[str]
        Matching tickers, empty list if sector is unknown.
    """
    return [t for t, s in SECTOR_MAP.items() if s == sector]


def get_benchmark_ticker(market: str = "US") -> str:
    """Return the benchmark index ticker for the given market.

    Parameters
    ----------
    market : str
        Market identifier: ``"IN"`` (India), ``"US"`` (United States),
        ``"UK"`` (United Kingdom).  Defaults to ``"US"``.

    Returns
    -------
    str
        Yahoo Finance benchmark ticker (e.g. ``"^GSPC"`` for US).
    """
    market = market.upper()
    if market in ("IN", "INDIA", "NSE"):
        return "^NSEI"  # NIFTY 50
    if market in ("UK", "LSE", "LONDON"):
        return "^FTSE"  # FTSE 100
    return "^GSPC"  # Default: S&P 500


def get_available_universes() -> List[str]:
    """Return a list of all available universe identifiers.

    Returns
    -------
    list[str]
        Sorted list of supported universe names.
    """
    return sorted(set(
        k for k in _ALL_UNIVERSE_MAP.keys() if " " not in k
    ))


def calculate_beta(
    stock_returns: pd.Series,
    market_returns: pd.Series,
) -> float:
    """Calculate the CAPM beta of *stock_returns* against *market_returns*.

    Beta is defined as ``Cov(r_s, r_m) / Var(r_m)``.
    Missing values are dropped pairwise.

    Parameters
    ----------
    stock_returns : pandas.Series
        Daily (or periodic) returns of the stock / asset.
    market_returns : pandas.Series
        Daily (or periodic) returns of the market benchmark.

    Returns
    -------
    float
        Beta value.  Returns ``0.0`` if variance is zero or insufficient data.
    """
    if stock_returns is None or market_returns is None:
        return 0.0

    aligned = pd.concat([stock_returns, market_returns], axis=1).dropna()
    if aligned.shape[0] < 5:
        return 0.0

    s = aligned.iloc[:, 0].values
    m = aligned.iloc[:, 1].values

    m_var = np.var(m, ddof=1)
    if m_var == 0 or not np.isfinite(m_var):
        return 0.0

    covariance = np.cov(s, m, ddof=1)[0, 1]
    beta = covariance / m_var

    if not np.isfinite(beta):
        return 0.0

    # Clamp to a reasonable range
    return float(max(-2.0, min(4.0, beta)))
