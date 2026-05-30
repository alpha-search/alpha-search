#!/usr/bin/env python3
"""Alpha Search - Find Thematic Stock Opportunities.

This script fetches daily price and volume data for the US AI Infrastructure &
Semiconductors universe, calculates key metric indicators for finding opportunities,
prunes highly correlated assets, and exports the final dataset to a CSV file.
"""

from __future__ import annotations
import os
import sys
import numpy as np
import pandas as pd
import yfinance as yf

# Ensure repo root is on sys.path
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from alpha_search.research.ai_infra_strategy_pipeline import get_ai_infra_universe

def main():
    print("=" * 80)
    print("  ALPHA SEARCH - THEMATIC OPPORTUNITY SCANNER")
    print("=" * 80)
    
    # 1. Fetch thematic universe
    universe = get_ai_infra_universe()
    all_tickers = [t for tickers in universe.values() for t in tickers]
    
    # Add SPY for beta computation
    download_tickers = list(set(all_tickers + ["SPY"]))
    print(f"Downloading data for {len(download_tickers)} symbols (1 Year)...")
    
    # 2. Ingest 2 years of daily data to ensure 252-day lookbacks are available
    raw_data = yf.download(download_tickers, period="2y", interval="1d", progress=False)
    close = raw_data["Close"]
    volume = raw_data["Volume"]
    
    # Clean returns
    returns = close.pct_change()
    spy_returns = returns["SPY"]
    
    # Exclude SPY from asset calculations
    asset_tickers = [t for t in all_tickers if t in close.columns]
    
    # 3. Calculate metrics per ticker
    records = []
    
    # Calculate pairwise correlation matrix among all assets
    corr_matrix = returns[asset_tickers].corr(method="pearson")
    
    # Apply Greedy Uncorrelated Selection to flag selected assets
    avg_corr = corr_matrix.abs().mean().sort_values()
    candidates = list(avg_corr.index)
    
    uncorrelated_selected = []
    for asset in candidates:
        if not uncorrelated_selected:
            uncorrelated_selected.append(asset)
            continue
        correlations = corr_matrix.loc[asset, uncorrelated_selected]
        if (correlations.abs() <= 0.55).all():
            uncorrelated_selected.append(asset)
            
    print(f"Running metric calculations and scanning for opportunities...")
    for t in asset_tickers:
        t_close = close[t].dropna()
        t_vol = volume[t].dropna()
        
        if len(t_close) < 63:
            continue
            
        current_price = float(t_close.iloc[-1])
        
        # Liquidity: 63-day median daily dollar volume ($ Millions)
        dollar_vol_63 = (t_close * t_vol).rolling(63).median()
        med_val_m = float(dollar_vol_63.iloc[-1]) / 1e6
        
        # Volatility: 21-day realized volatility (annualized)
        vol_21 = float(returns[t].rolling(21).std().iloc[-1] * np.sqrt(252))
        
        # Momentum: 12-1 Month return (using 252-day lookback, 21-day skip)
        mom_12_1 = np.nan
        if len(t_close) >= 252:
            mom_12_1 = float(t_close.iloc[-21] / t_close.iloc[-252] - 1.0)
            
        # Z-Score: Distance from 20-day SMA (mean reversion signal)
        sma_20 = t_close.rolling(20).mean()
        std_20 = t_close.rolling(20).std()
        z_score_20 = float((t_close.iloc[-1] - sma_20.iloc[-1]) / std_20.iloc[-1]) if std_20.iloc[-1] > 0 else 0.0
        
        # Breakout metric: Distance to 20-day high (%)
        high_20 = t_close.rolling(20).max().iloc[-1]
        dist_high_20 = float((current_price - high_20) / high_20)
        
        # Beta vs SPY
        aligned = pd.concat([returns[t], spy_returns], axis=1).dropna()
        cov = aligned.cov().values
        beta_spy = float(cov[0, 1] / cov[1, 1]) if cov[1, 1] > 0 else 1.0
        
        # Average correlation with others
        mean_corr = float(corr_matrix[t].abs().mean())
        
        # Determine theme category
        category = "Unknown"
        for cat, stocks in universe.items():
            if t in stocks:
                category = cat
                break
                
        records.append({
            "Ticker": t,
            "Category": category,
            "Current_Close": current_price,
            "Med_Dollar_Vol_63d_M": med_val_m,
            "Volatility_21d_Ann": vol_21,
            "Momentum_12_1M": mom_12_1,
            "Z_Score_20d": z_score_20,
            "Dist_to_20d_High_Pct": dist_high_20,
            "Beta_vs_SPY": beta_spy,
            "Mean_Pairwise_Correlation": mean_corr,
            "Is_Selected_Uncorrelated": 1 if t in uncorrelated_selected else 0
        })
        
    df_opp = pd.DataFrame(records)
    
    # Sort by momentum (highest first)
    df_opp = df_opp.sort_values(by="Momentum_12_1M", ascending=False)
    
    # Ensure output directory exists
    os.makedirs("outputs", exist_ok=True)
    csv_path = "outputs/thematic_opportunities.csv"
    df_opp.to_csv(csv_path, index=False)
    print(f"\nSuccessfully exported {len(df_opp)} stock records to: {csv_path}")
    
    # Display Top Breakout Candidates (Close to 20-day high)
    print("\n" + "=" * 80)
    print("  TOP BREAKOUT OPPORTUNITIES (Ordered by Momentum, Distance to 20d High >= -3%)")
    print("=" * 80)
    breakouts = df_opp[df_opp["Dist_to_20d_High_Pct"] >= -0.03].head(5)
    print(breakouts[["Ticker", "Category", "Current_Close", "Momentum_12_1M", "Dist_to_20d_High_Pct", "Is_Selected_Uncorrelated"]].to_string(index=False))
    
    # Display Deepest Mean-Reversion Dips (Z-Score <= -1.5)
    print("\n" + "=" * 80)
    print("  DEEPEST MEAN-REVERSION DIPS (Z-Score <= -1.5)")
    print("=" * 80)
    dips = df_opp[df_opp["Z_Score_20d"] <= -1.5]
    if not dips.empty:
        print(dips[["Ticker", "Category", "Current_Close", "Volatility_21d_Ann", "Z_Score_20d", "Is_Selected_Uncorrelated"]].to_string(index=False))
    else:
        print("No tickers currently meeting Z-Score <= -1.5 condition.")
    print("=" * 80)

if __name__ == "__main__":
    main()
