# Alpha Search — Jupyter Notebooks

All notebooks use **ONLY real data** from free APIs. No synthetic data anywhere.

## Quick Start (Google Colab)

Click any notebook to open in Colab, then Runtime > Run all.

| # | Notebook | Data Source | Reliability | Cells |
|---|----------|-------------|-------------|-------|
| 01 | [FRED Macro Analysis](01_FRED_Macro_Analysis.ipynb) | FRED API | **High** — always works | 13 |
| 02 | [Crypto Analysis](02_Crypto_Analysis.ipynb) | CoinGecko API | **High** — generous limits | 14 |
| 03 | [SEC Fundamentals](03_SEC_Fundamentals.ipynb) | SEC EDGAR API | Medium — may rate-limit | 13 |
| 04 | [Multi-Asset Pipeline](04_Multi_Asset_Pipeline.ipynb) | All sources | Varies by source | 13 |

## Notebooks

### 01_FRED_Macro_Analysis.ipynb
Fetches and visualizes key US macroeconomic indicators:
- **GDP** — Gross Domestic Product (quarterly)
- **CPIAUCSL** — Consumer Price Index for inflation
- **UNRATE** — Unemployment rate
- **DFF** — Federal Funds effective rate
- **T10Y2Y** — Yield curve spread (10Y minus 2Y Treasury)

**Reliability:** Excellent. FRED API is highly reliable from Google Colab.

**Rate limit:** ~120 requests/minute (very generous).

### 02_Crypto_Analysis.ipynb
Fetches cryptocurrency data and performs technical analysis:
- **BTC/ETH/SOL** prices (365 days)
- Normalized performance comparison
- Daily returns, volatility, correlation matrix
- Momentum signals (20-day Rate of Change)
- Mean reversion strategy (z-score based backtest)

**Reliability:** Excellent. CoinGecko free tier is generous.

**Rate limit:** 10-30 calls/minute. Notebook includes `time.sleep(1.5)` between calls.

### 03_SEC_Fundamentals.ipynb
Fetches company financials from SEC EDGAR filings:
- Company facts lookup via CIK
- Revenue, net income, EPS extraction from XBRL
- Profit margin calculation
- Side-by-side comparison (AAPL, MSFT, TSLA)

**Reliability:** Medium. SEC EDGAR may rate-limit shared Colab IPs.

**Rate limit:** ~10 requests/second. Proper User-Agent header required.

### 04_Multi_Asset_Pipeline.ipynb
Combines ALL data sources into a unified pipeline:
- Fetches from FRED, CoinGecko, and yfinance
- Robust error handling per source
- Falls back gracefully when APIs fail
- Cross-asset summary dashboard
- Results aggregation and export

**Data source reliability:**
| Source | Expected Success | Fallback |
|--------|-----------------|----------|
| FRED | 100% | None needed |
| CoinGecko | ~95% | Wait + retry |
| yfinance | ~50% from Colab | Shows clear message |

## Installation

Each notebook installs Alpha Search automatically on first run:

```python
!pip install git+https://github.com/alpha-search/alpha-search.git -q
```

Or install locally:

```bash
cd /mnt/agents/output/quant-os
pip install -e .
```

## No Synthetic Data Policy

Every notebook follows these rules:
- All data comes from live API calls
- If an API fails, a clear error message is shown
- Fake/synthetic data is NEVER generated
- All plots use real data only
- Rate-limit handling with `time.sleep()` delays

## Rate Limit Summary

| API | Free Tier | Delay Used |
|-----|-----------|------------|
| FRED | ~120 req/min | 0.3-0.5s |
| CoinGecko | 10-30 req/min | 1.5s |
| SEC EDGAR | ~10 req/sec | 0.5s |
| Yahoo Finance | Varies (shared IP) | 1s + retries |
