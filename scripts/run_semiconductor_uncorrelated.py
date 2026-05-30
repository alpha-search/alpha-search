#!/usr/bin/env python3
"""Alpha Search - Semiconductor & AI Infrastructure Uncorrelated Momentum Study.

This script executes a research pipeline:
1. Select Universe: US AI Infrastructure & Semiconductors (32 symbols).
2. Volume Filter: Daily volume >= $25M (63-day median).
3. Correlation Filter: Greedy selection of assets with pairwise correlation <= 0.55.
4. Signal: 12-month momentum.
5. Backtest: Vectorized monthly rebalance net-of-costs (20 bps round-trip).
6. Performance comparison: Full Universe vs. Uncorrelated Universe.
"""

from __future__ import annotations
import os
import sys
import numpy as np
import pandas as pd

# Ensure repo root is on sys.path
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from alpha_search.research.ai_infra_strategy_pipeline import (
    get_ai_infra_universe,
    download_ai_infra_data,
    validate_ai_infra_data,
    build_cross_sectional_momentum_signal,
    run_strategy_backtest,
    calculate_strategy_metrics,
    calculate_alpha_beta_vs_benchmark,
)

def find_uncorrelated_assets(returns_df: pd.DataFrame, max_correlation: float = 0.55) -> list[str]:
    """Greedy algorithm to find a subset of uncorrelated assets."""
    corr_matrix = returns_df.corr(method="pearson")
    # Sort assets by average absolute correlation with others (lowest first)
    avg_corr = corr_matrix.abs().mean().sort_values()
    candidates = list(avg_corr.index)
    
    selected_assets = []
    for asset in candidates:
        if not selected_assets:
            selected_assets.append(asset)
            continue
        # Check correlation of the candidate with all selected assets
        correlations = corr_matrix.loc[asset, selected_assets]
        if (correlations.abs() <= max_correlation).all():
            selected_assets.append(asset)
            
    return selected_assets

def main():
    print("=" * 80)
    print("  ALPHA SEARCH - UNCORRELATED SEMICONDUCTOR MOMENTUM RESEARCH STUDY")
    print("=" * 80)
    
    # 1. Select Universe
    universe = get_ai_infra_universe()
    all_symbols = [t for tickers in universe.values() for t in tickers]
    print(f"Initial Universe: {len(all_symbols)} symbols across semiconductors, semi-equipment, & AI infra.")
    
    # 2. Download Data
    print("\nDownloading 5 years of daily price & volume data via yfinance...")
    close, volume, bench_close = download_ai_infra_data(symbols=all_symbols, period="5y", interval="1d")
    
    # 3. Clean and Validate
    all_valid, val_report, skipped, valid_close, valid_volume = validate_ai_infra_data(close, volume)
    print(f"Data validation complete. Valid symbols: {len(valid_close.columns)} (Skipped: {len(skipped)})")
    
    # 4. Apply Liquidity Constraint ($25M median daily volume)
    dollar_vol = (valid_close * valid_volume).rolling(63).median()
    last_date = valid_close.index[-1]
    liq_eligible = [sym for sym in valid_close.columns if dollar_vol.loc[last_date, sym] >= 25e6]
    print(f"Liquidity Screen ($25M daily volume threshold): {len(liq_eligible)} / {len(valid_close.columns)} symbols passed.")
    
    liq_close = valid_close[liq_eligible]
    liq_volume = valid_volume[liq_eligible]
    liq_returns = liq_close.pct_change()
    
    # 5. Add Uncorrelated Selection Step (max pairwise correlation <= 0.55)
    uncorrelated_symbols = find_uncorrelated_assets(liq_returns, max_correlation=0.55)
    print(f"\nUncorrelated Selection Filter (max pairwise correlation <= 0.55):")
    print(f"  Selected {len(uncorrelated_symbols)} uncorrelated symbols: {uncorrelated_symbols}")
    
    # 6. Create 12-Month Momentum Signal & Backtest
    print("\nGenerating 12-month momentum signals (long-only, monthly rebalance)...")
    
    # Run backtest for Full (Liquidity-filtered) Universe (quantile = 0.5 to match)
    full_weights, _ = build_cross_sectional_momentum_signal(
        liq_close, liq_volume,
        lookback=252, skip=21,
        liq_window=63, min_dollar_vol=25e6,
        quantile=0.5, freq="ME",
        long_only=True
    )
    full_backtest = run_strategy_backtest(
        daily_returns=liq_returns,
        target_weights=full_weights,
        cost_bps=10.0,
    )
    full_metrics = calculate_strategy_metrics(full_backtest["net"])
    
    # Run backtest for Uncorrelated Universe only
    uncorr_close = liq_close[uncorrelated_symbols]
    uncorr_volume = liq_volume[uncorrelated_symbols]
    uncorr_returns = liq_returns[uncorrelated_symbols]
    
    uncorr_weights, _ = build_cross_sectional_momentum_signal(
        uncorr_close, uncorr_volume,
        lookback=252, skip=21,
        liq_window=63, min_dollar_vol=25e6,
        quantile=0.5, freq="ME",
        long_only=True
    )
    uncorr_backtest = run_strategy_backtest(
        daily_returns=uncorr_returns,
        target_weights=uncorr_weights,
        cost_bps=10.0,
    )
    uncorr_metrics = calculate_strategy_metrics(uncorr_backtest["net"])
    
    # Calculate Benchmarks
    bench_returns = bench_close["SOXX"].pct_change().dropna()
    bench_metrics = calculate_strategy_metrics(bench_returns)
    
    # Alpha & Beta Regression
    full_ab = calculate_alpha_beta_vs_benchmark(full_backtest["net"], bench_returns)
    uncorr_ab = calculate_alpha_beta_vs_benchmark(uncorr_backtest["net"], bench_returns)
    
    # 7. Print Performance Comparison Table
    print("\n" + "=" * 80)
    print("  PERFORMANCE COMPARISON (Net of 20 bps transaction costs)")
    print("=" * 80)
    
    metrics_compare = pd.DataFrame({
        "Full Liquidity Universe": {
            "Traded Symbols": len(liq_eligible),
            "Annualized Return": f"{full_metrics['annualized_return']:.2%}",
            "Annualized Volatility": f"{full_metrics['annualized_vol']:.2%}",
            "Max Drawdown": f"{full_metrics['max_drawdown']:.2%}",
            "Sharpe Ratio": f"{full_metrics['sharpe_ratio']:.3f}",
            "Annualized Alpha": f"{full_ab['ann_alpha']:.2%}",
            "Beta vs SOXX": f"{full_ab['beta']:.3f}",
            "t-stat(Alpha)": f"{full_ab['t_alpha']:.2f}"
        },
        "Uncorrelated Universe (rho <= 0.55)": {
            "Traded Symbols": len(uncorrelated_symbols),
            "Annualized Return": f"{uncorr_metrics['annualized_return']:.2%}",
            "Annualized Volatility": f"{uncorr_metrics['annualized_vol']:.2%}",
            "Max Drawdown": f"{uncorr_metrics['max_drawdown']:.2%}",
            "Sharpe Ratio": f"{uncorr_metrics['sharpe_ratio']:.3f}",
            "Annualized Alpha": f"{uncorr_ab['ann_alpha']:.2%}",
            "Beta vs SOXX": f"{uncorr_ab['beta']:.3f}",
            "t-stat(Alpha)": f"{uncorr_ab['t_alpha']:.2f}"
        },
        "SOXX Benchmark": {
            "Traded Symbols": 30,
            "Annualized Return": f"{bench_metrics['annualized_return']:.2%}",
            "Annualized Volatility": f"{bench_metrics['annualized_vol']:.2%}",
            "Max Drawdown": f"{bench_metrics['max_drawdown']:.2%}",
            "Sharpe Ratio": f"{bench_metrics['sharpe_ratio']:.3f}",
            "Annualized Alpha": "0.00%",
            "Beta vs SOXX": "1.000",
            "t-stat(Alpha)": "n/a"
        }
    })
    
    print(metrics_compare.to_string())
    print("=" * 80)
    print("Research Complete.")

if __name__ == "__main__":
    main()
