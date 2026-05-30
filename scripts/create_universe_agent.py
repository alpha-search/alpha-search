#!/usr/bin/env python3
"""Alpha Search - Agent to Find Stock Universes using Google Antigravity SDK.

This script demonstrates how to define an autonomous AI agent to:
1. Search/Discover stock symbols for a given theme.
2. Screen for liquidity (Volume, Market Cap).
3. Compute and clean pairwise correlations.
4. Output a Pydantic-structured list of clean tickers.
"""

import os
import sys
import asyncio
import pydantic
import pandas as pd
import yfinance as yf
import numpy as np

# Ensure repo root is on sys.path
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

# Import Antigravity SDK
try:
    from google.antigravity import Agent, LocalAgentConfig
    SDK_AVAILABLE = True
except ImportError:
    SDK_AVAILABLE = False

# =====================================================================
# 1. Define Tools for the Agent
# =====================================================================

def search_theme_companies(theme: str) -> list[str]:
    """Search for companies related to a specific theme.
    
    Args:
        theme: The sector/theme to search for, e.g., "liquid cooling for AI servers".
    """
    # In a real-world scenario, this tool would call a Web Search API (Tavily, Google)
    # or query a SEC RAG database.
    # Here we mock the search results for common themes as an illustration.
    print(f"[Agent Tool] Searching web & filings for theme: '{theme}'...")
    theme_lower = theme.lower()
    if "cooling" in theme_lower or "thermal" in theme_lower:
        return ["VRT", "SMCI", "MOD", "DELL", "AAPL", "NVDA", "AAON", "CIEN"]
    elif "gpu" in theme_lower or "semiconductor" in theme_lower:
        return ["NVDA", "AMD", "INTC", "TSM", "AVGO", "TXN", "MU", "QCOM", "ARM"]
    return ["AAPL", "MSFT", "GOOGL", "AMZN", "META", "NVDA", "TSLA"]

def filter_by_liquidity(tickers: list[str], min_volume_m: float = 25.0) -> list[str]:
    """Filter stocks by 63-day median daily volume ($M).
    
    Args:
        tickers: List of ticker symbols to screen.
        min_volume_m: Minimum median daily dollar volume in Millions.
    """
    print(f"[Agent Tool] Screening {len(tickers)} symbols for liquidity (> ${min_volume_m}M daily)...")
    valid_tickers = []
    for ticker in tickers:
        try:
            stock = yf.Ticker(ticker)
            hist = stock.history(period="3mo")
            if hist.empty:
                continue
            dollar_vol = hist["Close"] * hist["Volume"]
            median_vol = dollar_vol.median()
            if median_vol >= min_volume_m * 1e6:
                valid_tickers.append(ticker)
                print(f"  - {ticker} passed (ADV: ${median_vol/1e6:.1f}M)")
            else:
                print(f"  - {ticker} failed (ADV: ${median_vol/1e6:.1f}M)")
        except Exception:
            print(f"  - {ticker} failed (download error)")
    return valid_tickers

def prune_correlated_assets(tickers: list[str], max_corr: float = 0.55) -> list[str]:
    """Removes highly correlated assets using a greedy algorithm.
    
    Args:
        tickers: List of ticker symbols to filter.
        max_corr: Maximum pairwise Pearson correlation allowed.
    """
    print(f"[Agent Tool] Running correlation filter (max correlation <= {max_corr})...")
    if len(tickers) <= 1:
        return tickers
    
    # Download daily price history
    data = yf.download(tickers, period="1y", interval="1d", progress=False)["Close"]
    returns = data.pct_change().dropna()
    
    corr_matrix = returns.corr(method="pearson")
    avg_corr = corr_matrix.abs().mean().sort_values()
    candidates = list(avg_corr.index)
    
    selected = []
    for asset in candidates:
        if not selected:
            selected.append(asset)
            continue
        correlations = corr_matrix.loc[asset, selected]
        if (correlations.abs() <= max_corr).all():
            selected.append(asset)
            
    print(f"  - Selected uncorrelated assets: {selected}")
    return selected

# =====================================================================
# 2. Define Pydantic Schema for Structured Output
# =====================================================================

class StockUniverse(pydantic.BaseModel):
    theme: str
    rationale: str
    discovered_tickers: list[str]
    liquidity_passed_tickers: list[str]
    uncorrelated_tickers: list[str]

# =====================================================================
# 3. Main Agent Execution
# =====================================================================

async def run_agent():
    if not SDK_AVAILABLE:
        print("Google Antigravity SDK is not installed or available.")
        return

    print("Initializing Google Antigravity Universe Finder Agent...")
    
    config = LocalAgentConfig(
        tools=[search_theme_companies, filter_by_liquidity, prune_correlated_assets],
        response_schema=StockUniverse,
        system_instructions=(
            "You are a professional quantitative research assistant. Your task is to construct "
            "a diversified stock universe for a specific theme. "
            "Follow these steps in order:\n"
            "1. Call `search_theme_companies` to find candidates for the theme.\n"
            "2. Call `filter_by_liquidity` on the candidates (minimum $25M daily volume).\n"
            "3. Call `prune_correlated_assets` on the passing tickers to ensure pairwise correlation <= 0.55.\n"
            "4. Return the structured StockUniverse JSON."
        )
    )

    async with Agent(config) as agent:
        prompt = "Create a stock universe for the 'liquid cooling and heat management for AI servers' theme."
        print(f"User Prompt: '{prompt}'\n")
        
        response = await agent.chat(prompt)
        
        # Access the structured output
        print("Parsing agent's structured response...")
        data = await response.structured_output()
        print("\n" + "=" * 80)
        print("  AGENT OUTPUT (STRUCTURED UNIVERSE)")
        print("=" * 80)
        import json
        print(json.dumps(data, indent=2))
        print("=" * 80)

if __name__ == "__main__":
    if SDK_AVAILABLE:
        asyncio.run(run_agent())
    else:
        # Standard fallback output demonstrating the agent logic
        print("SDK not available. Demonstrating the workflow logic directly:\n")
        discovered = search_theme_companies("liquid cooling for AI servers")
        passed = filter_by_liquidity(discovered, min_volume_m=25.0)
        final = prune_correlated_assets(passed, max_corr=0.55)
        
        result = StockUniverse(
            theme="liquid cooling and heat management for AI servers",
            rationale="Discovered thematic assets, screened for $25M liquidity, and filtered pairwise correlation <= 0.55.",
            discovered_tickers=discovered,
            liquidity_passed_tickers=passed,
            uncorrelated_tickers=final
        )
        print("\n" + "=" * 80)
        print("  FALLBACK WORKFLOW OUTPUT")
        print("=" * 80)
        print(result.model_dump_json(indent=2))
        print("=" * 80)
