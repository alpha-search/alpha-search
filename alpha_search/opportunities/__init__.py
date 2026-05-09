"""Alpha Search Global Multi-Asset Opportunity Discovery — trading opportunity scanner.

This module provides a comprehensive framework for discovering trading
opportunities across global multi-asset markets. It includes three core
strategy engines:

1. **Momentum Scan** — Identifies trending instruments using RSI, MACD, ADX and volume confirmation
2. **Mean Reversion Scan** — Finds overbought/oversold instruments via z-score, Bollinger Bands, RSI extremes
3. **Statistical Arbitrage Scan** — Discovers cointegrated pairs for pair trading

All scores are normalized to the [0, 1] range. Supports US equities,
Indian equities, cryptocurrencies, forex pairs, and commodities.
"""

from alpha_search.opportunities.models import PairOpportunity, StockOpportunity
from alpha_search.opportunities.scoring import FinalScore
from alpha_search.opportunities.scanner import StockOpportunityScanner
from alpha_search.opportunities.strategies import momentum_scan, mean_reversion_scan, arbitrage_scan

__all__ = [
    "StockOpportunity", "PairOpportunity", "FinalScore",
    "StockOpportunityScanner",
    "momentum_scan", "mean_reversion_scan", "arbitrage_scan",
]
