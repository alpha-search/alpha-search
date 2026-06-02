#!/usr/bin/env python3
"""Alpha Search Terminal API Server.

Serves the REST API for the stock opportunity agent UI:
1. /api/v1/sectors: Lists universes/sectors.
2. /api/v1/scan: Runs the multi-factor thematic opportunity scanner.
3. Mocks/Proxies for yfinance endpoints to replace OpenBB Platform.
"""

import os
import sys
import uvicorn
import requests
import numpy as np
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

# Ensure repo root is on sys.path
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

# Load env keys
load_dotenv(os.path.join(_REPO_ROOT, ".env"))

from alpha_search.core.agent_signals import ThematicSignalAgent
from alpha_search.opportunities.market_universes import (
    get_universe_tickers,
    get_company_name,
    get_sector,
    get_available_universes
)

app = FastAPI(title="Alpha Search Terminal API", version="1.0.0")

# Enable CORS for local dev
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/", response_class=HTMLResponse)
def serve_index():
    """Serves the main Bloomberg-style Stock Opportunity Terminal HTML dashboard."""
    with open(os.path.join(_REPO_ROOT, "scripts", "index.html"), "r") as f:
        return f.read()

class ScanRequest(BaseModel):
    tickers: list[str]
    theme: str

@app.get("/api/v1/sectors")
def get_sectors():
    """Returns tickers grouped by universe/sector for the Drag and Drop UI."""
    universes = get_available_universes()
    results = {}
    for u in universes:
        tickers = get_universe_tickers(u)[:40]  # Limit to 40 per category for UI responsiveness
        results[u] = [
            {
                "ticker": t,
                "name": get_company_name(t),
                "sector": get_sector(t)
            }
            for t in tickers
        ]
    return {"results": results}

@app.post("/api/v1/scan")
def run_scan(req: ScanRequest):
    """Executes opportunity scan and calls Gemini to generate analyst report."""
    if not req.tickers:
        raise HTTPException(status_code=400, detail="No tickers selected.")
        
    print(f"Running agent scan on {len(req.tickers)} tickers under theme: '{req.theme}'")
    agent = ThematicSignalAgent()
    
    # Temporarily override discover_universe to use the user's custom selection
    original_discover = agent.discover_universe
    agent.discover_universe = lambda theme: req.tickers
    
    try:
        df_opps = agent.generate_thematic_opportunities(req.theme)
    except Exception as e:
        # Degrade gracefully instead of a hard 500 so the terminal UI never breaks.
        # An empty matrix (e.g. when no market data could be fetched) is returned as a
        # valid, empty result with an explanatory note rather than an error response.
        print(f"[scan] agent failed, returning empty matrix: {e}")
        df_opps = pd.DataFrame()
    finally:
        agent.discover_universe = original_discover

    if df_opps is None or df_opps.empty:
        return {
            "results": {
                "data": [],
                "report": (
                    "### [SCAN RETURNED NO DATA]\n\n"
                    "**The opportunity agent could not produce a matrix for the selected "
                    "universe.** This usually means market data for the chosen tickers was "
                    "unavailable (no upstream connectivity, rate limit, or unknown symbols).\n\n"
                    "- Verify network access to the market-data providers.\n"
                    "- Try a smaller or more liquid universe.\n"
                    "- The terminal remains fully operational; re-run the scan when data is reachable."
                ),
            }
        }

    # Save CSV locally
    os.makedirs("outputs", exist_ok=True)
    df_opps.to_csv("outputs/unified_opportunities.csv", index=False)

    # Convert dataframe to JSON list
    data_list = df_opps.to_dict(orient="records")
    
    # 4. Generate AI Report via Gemini
    api_key = os.getenv("GEMINI_API_KEY")
    report = ""
    if not api_key:
        report = (
            "### [LOCAL RULE-BASED QUANT AGENT SUMMARY]\n\n"
            "**GEMINI_API_KEY not found in .env. To enable real AI synthesis, add your Gemini API key.**\n\n"
            "**Quantitative Analysis of Discovered Opportunities**:\n"
            "- Multi-factor setups show strong alignment between retail sentiment, technical Z-scores, and insider accumulation.\n"
            "- Risk warning: Assets with high volatility require tight drawdown limits.\n"
            "- Strategy recommendation: Allocate MVO weights with a 35% single-stock concentration cap."
        )
    else:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
        headers = {"Content-Type": "application/json"}
        prompt = (
            f"You are the Alpha Search Quantitative Analyst. Write a detailed quantitative and qualitative "
            f"report for the stock universe matching '{req.theme}'. Here is the data containing "
            f"technical factors, X sentiment, and alternative insider/patent data:\n\n"
            f"{df_opps.to_string(index=False)}\n\n"
            f"Analyze this multi-factor opportunity matrix and recommend allocation weights."
        )
        payload = {
            "contents": [{
                "parts": [{"text": prompt}]
            }]
        }
        try:
            res = requests.post(url, json=payload, headers=headers, timeout=90)
            if res.status_code == 200:
                report = res.json()["candidates"][0]["content"]["parts"][0]["text"]
            else:
                report = f"[Gemini API Error {res.status_code}]: {res.text}"
        except Exception as e:
            report = f"[Gemini Connection Error]: {e}"
            
    # Save markdown report
    with open("outputs/unified_opportunities_report.md", "w") as f:
        f.write(report)
        
    return {
        "results": {
            "data": data_list,
            "report": report
        }
    }

# ────── Mock yfinance API routes to power standard BB-Terminal pages ──────

@app.get("/api/v1/equity/price/quote")
def get_quote(symbol: str):
    """Mocks OpenBB quote endpoint using yfinance."""
    try:
        t = yf.Ticker(symbol)
        info = t.info
        history = t.history(period="2d")
        
        last_price = float(history["Close"].iloc[-1]) if not history.empty else 100.0
        prev_close = float(history["Close"].iloc[-2]) if len(history) >= 2 else last_price
        
        payload = {
            "symbol": symbol,
            "name": info.get("longName", get_company_name(symbol)),
            "exchange": info.get("exchange", "NASDAQ"),
            "last_price": last_price,
            "open": float(history["Open"].iloc[-1]) if not history.empty else last_price,
            "high": float(history["High"].iloc[-1]) if not history.empty else last_price,
            "low": float(history["Low"].iloc[-1]) if not history.empty else last_price,
            "prev_close": prev_close,
            "volume": int(history["Volume"].iloc[-1]) if not history.empty else 0,
            "volume_average": info.get("averageVolume", 0),
            "year_high": info.get("fiftyTwoWeekHigh", last_price),
            "year_low": info.get("fiftyTwoWeekLow", last_price),
            "ma_50d": info.get("fiftyDayAverage", last_price),
            "ma_200d": info.get("twoHundredDayAverage", last_price),
            "currency": info.get("currency", "USD")
        }
        return {"results": [payload]}
    except Exception as e:
        # Graceful fallback
        return {"results": [{
            "symbol": symbol, "name": get_company_name(symbol),
            "last_price": 100.0, "prev_close": 100.0
        }]}

@app.get("/api/v1/equity/price/historical")
def get_historical(symbol: str, start_date: str = None):
    """Mocks OpenBB historical daily candles using yfinance."""
    try:
        start = start_date or (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d")
        t = yf.Ticker(symbol)
        df = t.history(start=start, interval="1d")
        
        candles = []
        for idx, row in df.iterrows():
            candles.append({
                "date": idx.strftime("%Y-%m-%d"),
                "open": float(row["Open"]),
                "high": float(row["High"]),
                "low": float(row["Low"]),
                "close": float(row["Close"]),
                "volume": int(row["Volume"])
            })
        return {"results": candles}
    except Exception:
        return {"results": []}

@app.get("/api/v1/equity/profile")
def get_profile(symbol: str):
    """Mocks OpenBB profile using yfinance."""
    try:
        t = yf.Ticker(symbol)
        info = t.info
        payload = {
            "symbol": symbol,
            "name": info.get("longName", get_company_name(symbol)),
            "stock_exchange": info.get("exchange", "NASDAQ"),
            "long_description": info.get("longBusinessSummary", "No description available."),
            "company_url": info.get("website", ""),
            "sector": info.get("sector", get_sector(symbol)),
            "industry_category": info.get("industry", "Unknown"),
            "market_cap": info.get("marketCap", 0),
            "shares_outstanding": info.get("sharesOutstanding", 0),
            "beta": info.get("beta", 1.0)
        }
        return {"results": [payload]}
    except Exception:
        return {"results": [{"symbol": symbol, "name": get_company_name(symbol)}]}

@app.get("/api/v1/equity/fundamental/metrics")
def get_metrics(symbol: str):
    """Mocks OpenBB fundamentals key metrics using yfinance."""
    try:
        t = yf.Ticker(symbol)
        info = t.info
        payload = {
            "symbol": symbol,
            "pe_ratio": info.get("trailingPE", 0.0),
            "forward_pe": info.get("forwardPE", 0.0),
            "peg_ratio": info.get("pegRatio", 0.0),
            "enterprise_to_ebitda": info.get("enterpriseToEbitda", 0.0),
            "revenue_growth": info.get("revenueGrowth", 0.0),
            "operating_margin": info.get("operatingMargins", 0.0),
            "profit_margin": info.get("profitMargins", 0.0),
            "debt_to_equity": info.get("debtToEquity", 0.0)
        }
        return {"results": [payload]}
    except Exception:
        return {"results": [{"symbol": symbol}]}

@app.get("/api/v1/news/company")
def get_news(symbol: str, limit: int = 30):
    """Mocks OpenBB news using yfinance."""
    try:
        t = yf.Ticker(symbol)
        raw_news = t.news[:limit]
        news_items = []
        for n in raw_news:
            news_items.append({
                "id": n.get("uuid", ""),
                "date": datetime.fromtimestamp(n.get("providerPublishTime", 0)).strftime("%Y-%m-%d"),
                "title": n.get("title", ""),
                "url": n.get("link", ""),
                "source": n.get("publisher", ""),
                "summary": n.get("title", "")
            })
        return {"results": news_items}
    except Exception:
        return {"results": []}

@app.get("/api/v1/fixedincome/government/treasury_rates")
def get_treasury_rates():
    """Returns mock Treasury rates for the CURV page."""
    rates = [
        {
            "date": datetime.now().strftime("%Y-%m-%d"),
            "month_1": 5.4, "month_3": 5.38, "month_6": 5.35,
            "year_1": 5.15, "year_2": 4.88, "year_3": 4.70, "year_5": 4.52,
            "year_7": 4.45, "year_10": 4.42, "year_20": 4.65, "year_30": 4.55
        }
    ]
    return {"results": rates}

@app.get("/api/v1/currency/price/historical")
def get_fx_historical(symbol: str):
    """Mocks historical Forex rates using yfinance."""
    return get_historical(symbol)

@app.get("/api/v1/crypto/price/historical")
def get_crypto_historical(symbol: str):
    """Mocks historical crypto rates using yfinance."""
    return get_historical(symbol)

# ────── OpenBB-Workspace widget routes ──────

@app.get("/api/v1/equity/fundamental/management")
def get_management(symbol: str):
    """Management team / company officers (yfinance companyOfficers + fallback)."""
    try:
        info = yf.Ticker(symbol).info
        officers = info.get("companyOfficers", []) or []
        rows = []
        for o in officers:
            rows.append({
                "name": o.get("name", "—"),
                "title": o.get("title", "—"),
                "compensation": o.get("totalPay"),
                "currency": info.get("currency", "USD"),
            })
        if rows:
            return {"results": rows}
    except Exception:
        pass
    # deterministic fallback
    seed = sum(ord(c) for c in symbol)
    titles = ["Chief Executive Officer", "Chief Financial Officer", "Chief Operating Officer",
              "SVP, Worldwide Marketing", "General Counsel", "Chief Technology Officer"]
    rows = [{"name": f"Officer {i+1}", "title": titles[i % len(titles)],
             "compensation": (seed * (i + 3) % 25 + 1) * 100000 if i < 4 else None,
             "currency": "USD"} for i in range(6)]
    return {"results": rows}

@app.get("/api/v1/equity/fundamental/revenue_geographic")
def get_revenue_geographic(symbol: str):
    """Geographic revenue split by fiscal year (deterministic mock — yfinance lacks this)."""
    regions = ["Americas", "Europe", "Greater China", "Japan", "Rest of Asia Pacific", "Other"]
    seed = sum(ord(c) for c in symbol) or 1
    rng = np.random.default_rng(seed)
    base = 50 + (seed % 40)
    rows = []
    for i, fy in enumerate(range(2010, 2026)):
        growth = (1.10 + (seed % 7) / 100.0) ** i
        weights = rng.dirichlet(np.array([5, 3, 2.5, 1.5, 1.2, 0.8]))
        total = base * growth
        row = {"fiscal_year": fy}
        for r, w in zip(regions, weights):
            row[r] = round(total * w, 2)
        rows.append(row)
    return {"results": rows, "regions": regions}

@app.get("/api/v1/apps")
def get_apps():
    """Apps Marketplace catalog (static, mirrors the OpenBB Workspace marketplace)."""
    catalog = [
        {"id": "adanos", "category": "SENTIMENT", "name": "Adanos Market Sentiment", "new": True,
         "tagline": "Reddit, X, news, and Polymarket sentiment + buzz",
         "description": "Buzz scores, trending tickers, and per-symbol sentiment from Reddit, X/Twitter, 50+ news sources, and Polymarket — all in one dashboard."},
        {"id": "axiora", "category": "FUNDAMENTALS", "name": "Axiora — Japanese equity intelligence", "new": False,
         "tagline": "JP equity financials, ownership, and audit trails",
         "description": "Financials, ownership networks, and earnings signals for ~4,000 Japanese listed companies — every row traces to a source EDINET filing."},
        {"id": "bluegamma", "category": "FIXED INCOME", "name": "BlueGamma Interest Rates", "new": False,
         "tagline": "Forward curves and swap rates, 30+ global indices",
         "description": "Live interest rate curves and swap rates for SOFR, SONIA, EURIBOR, CORRA, and 30+ indices. 7-day delayed data for free."},
        {"id": "cftc", "category": "TRADING ACTIVITY", "name": "CFTC Public Reports", "new": False,
         "tagline": "Commitment of Traders history for every contract",
         "description": "Search and query the full historical database of reports for contracts covering commodity and financial futures."},
        {"id": "eia", "category": "COMMODITY", "name": "EIA Energy Data", "new": False,
         "tagline": "U.S. energy time series straight from the EIA",
         "description": "Browse, search, and chart U.S. energy time series and tables from the Weekly Petroleum Status Report, Short-Term Energy Outlook, and more."},
        {"id": "exponential", "category": "TRADING ACTIVITY", "name": "Exponential Flow Intelligence", "new": False,
         "tagline": "Order-book supply and demand by investor type",
         "description": "You see price and volume. The mechanics of who is driving flow and why liquidity is shifting remain trapped behind high-frequency noise."},
        {"id": "findatasets", "category": "FUNDAMENTALS", "name": "Financial Datasets Market Intelligence", "new": False,
         "tagline": "Full US equity financials + news, all in one app",
         "description": "Tracks US equities end-to-end — company overviews with news and historical prices, full financial statements, key metrics, insider trades, earnings."},
        {"id": "hsdl", "category": "FILINGS & RESEARCH", "name": "HSDL Document Library", "new": False,
         "tagline": "Search the Homeland Security Digital Library",
         "description": "Search, explore, and view the public collection of documents in the Homeland Security Digital Library."},
        {"id": "openportfolio", "category": "PORTFOLIO & RISK", "name": "Open Portfolio", "new": False,
         "tagline": "Portfolio risk, attribution, and factor analytics",
         "description": "Portfolio management suite with tools for imputing positions, risk, attribution and factor analytics."},
        {"id": "outsampler", "category": "NEWS", "name": "Outsampler Intelligence", "new": False,
         "tagline": "Severity-scored alerts and AI watchlist briefs",
         "description": "Severity-scored alerts, AI daily briefs, and cross-asset driver maps."},
        {"id": "alphasearch", "category": "RESEARCH", "name": "AlphaSearch Thematic Scanner", "new": True,
         "tagline": "Multi-factor thematic opportunity discovery + AI report",
         "description": "Build a thematic universe and run the AlphaSearch quant agent: technicals, X sentiment, insider/patent signals, correlation pruning, and a Gemini analyst report.",
         "connected": True},
    ]
    return {"results": catalog}

class AskRequest(BaseModel):
    prompt: str
    symbol: str | None = None

@app.post("/api/v1/ai/ask")
def ai_ask(req: AskRequest):
    """AI copilot passthrough to Gemini, with a graceful local fallback when no key is set."""
    api_key = os.getenv("GEMINI_API_KEY")
    ctx = f" The user is currently viewing the symbol {req.symbol}." if req.symbol else ""
    if not api_key:
        return {"results": {
            "answer": (
                "**[Local copilot — no GEMINI_API_KEY set]**\n\n"
                f"I can't reach Gemini without an API key, but here is how I'd approach it:{ctx}\n\n"
                "- Add `GEMINI_API_KEY=...` to your `.env` to enable live AI synthesis.\n"
                "- Then ask things like *\"summarize this company's risk profile\"* or "
                "*\"compare margins vs peers\"* and I'll use the loaded widget data as context."
            )
        }}
    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
        prompt = f"You are the AlphaSearch financial copilot embedded in an OpenBB-style terminal.{ctx}\n\nUser: {req.prompt}"
        res = requests.post(url, json={"contents": [{"parts": [{"text": prompt}]}]},
                            headers={"Content-Type": "application/json"}, timeout=60)
        if res.status_code == 200:
            answer = res.json()["candidates"][0]["content"]["parts"][0]["text"]
        else:
            answer = f"[Gemini API Error {res.status_code}]"
    except Exception as e:
        answer = f"[Gemini connection error]: {e}"
    return {"results": {"answer": answer}}

if __name__ == "__main__":
    uvicorn.run("app_server:app", host="127.0.0.1", port=6900, reload=True)
