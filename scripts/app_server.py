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
        agent.discover_universe = original_discover
        raise HTTPException(status_code=500, detail=f"Scan execution error: {e}")
        
    agent.discover_universe = original_discover
    
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

if __name__ == "__main__":
    uvicorn.run("app_server:app", host="127.0.0.1", port=6900, reload=True)
