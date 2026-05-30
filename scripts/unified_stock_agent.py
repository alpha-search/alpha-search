#!/usr/bin/env python3
"""Alpha Search - Unified Stock Opportunity Agent.

This script demonstrates using the alpha_search library's core agent module:
1. Loads the ThematicSignalAgent from the alpha_search.core.agent_signals library.
2. Performs a unified opportunity scan combining ALL technical, sentiment, and alternative data columns.
3. Exports the full aggregated dataset to CSV.
4. Generates an AI analyst report using Google's Gemini API (if GEMINI_API_KEY is configured).
"""

from __future__ import annotations
import os
import sys
import requests
from dotenv import load_dotenv

# Ensure repo root is on sys.path
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

# Load env variables
load_dotenv(os.path.join(_REPO_ROOT, ".env"))

from alpha_search.core.agent_signals import ThematicSignalAgent

def generate_gemini_report(prompt: str) -> str:
    """Calls Google's Gemini API directly to generate the quant report."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return (
            "### [UNIFIED LOCAL QUANT AGENT SUMMARY]\n\n"
            "**GEMINI_API_KEY not found in .env. To enable real AI synthesis, add your Gemini API key.**\n\n"
            "**Quantitative Analysis of Discovered Opportunities**:\n"
            "- Multi-factor setups show strong alignment between retail sentiment, technical Z-scores, and insider accumulation.\n"
            "- Risk warning: Assets with high volatility require tight drawdown limits.\n"
            "- Strategy recommendation: Allocate MVO weights with a 35% single-stock concentration cap."
        )
        
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
    headers = {"Content-Type": "application/json"}
    payload = {
        "contents": [{
            "parts": [{"text": prompt}]
        }]
    }
    try:
        res = requests.post(url, json=payload, headers=headers, timeout=90)
        if res.status_code == 200:
            return res.json()["candidates"][0]["content"]["parts"][0]["text"]
        else:
            return f"[Gemini API Error {res.status_code}]: {res.text}"
    except Exception as e:
        return f"[Gemini Connection Error]: {e}"

def main():
    print("=" * 80)
    print("  ALPHA SEARCH - UNIFIED STOCK OPPORTUNITY AGENT")
    print("=" * 80)
    
    # 1. Initialize library agent
    agent = ThematicSignalAgent()
    
    # 2. Run scan
    theme = "liquid cooling for artificial intelligence server infrastructure"
    print(f"Running scanner for theme: '{theme}'...")
    df_opps = agent.generate_thematic_opportunities(theme)
    
    # 3. Save to CSV
    os.makedirs("outputs", exist_ok=True)
    csv_path = "outputs/unified_opportunities.csv"
    df_opps.to_csv(csv_path, index=False)
    print(f"\nSuccessfully aggregated and saved all columns to: {csv_path}")
    
    # Print the DataFrame columns to show aggregation
    print(f"\nAggregated columns ({len(df_opps.columns)} total):")
    print(list(df_opps.columns))
    
    # Display the top 10 opportunity rows
    print("\n" + df_opps.to_string(index=False))
    
    # 4. Generate AI Analyst Report
    prompt = (
        f"You are the Alpha Search Analyst. Write a detailed quantitative and qualitative "
        f"report for the stock universe matching '{theme}'. Here is the data containing "
        f"technical factors, X sentiment, and alternative insider/patent data:\n\n"
        f"{df_opps.to_string(index=False)}\n\n"
        f"Analyze this multi-factor opportunity matrix and recommend allocation weights."
    )
    
    print("\nGenerating AI Report...")
    report = generate_gemini_report(prompt)
    
    print("\n" + "=" * 80)
    print("  AGENT ANALYSIS REPORT")
    print("=" * 80)
    print(report)
    print("=" * 80)
    
    # Write report
    report_path = "outputs/unified_opportunities_report.md"
    with open(report_path, "w") as f:
        f.write(report)
    print(f"Saved markdown report to: {report_path}")

if __name__ == "__main__":
    main()
