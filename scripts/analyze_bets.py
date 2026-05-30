#!/usr/bin/env python3
"""Alpha Search - Analyze Strategy Bets and Weighting Events."""

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
)
from scripts.run_semiconductor_optimized import find_uncorrelated_assets, optimize_portfolio_mvo
from scripts.run_semiconductor_drawdown_control import run_backtest_with_drawdown_scaling, run_backtest_with_vol_and_drawdown_targeting

def analyze_strategy_bets(weights_df: pd.DataFrame, daily_weights_held: pd.DataFrame) -> dict:
    """Analyze the number of bets and reweightings.
    
    Parameters:
    - weights_df: Monthly target weights (rebalance dates x tickers)
    - daily_weights_held: Actual daily weights held in simulation (daily dates x tickers)
    """
    # 1. Total Rebalance Events (number of monthly rebalance dates)
    total_rebal_dates = len(weights_df)
    
    # 2. Number of rebalances with active positions
    active_rebal_dates = (weights_df.abs().sum(axis=1) > 1e-5).sum()
    
    # 3. Average active positions (bets) when active
    active_mask = weights_df.abs() > 1e-5
    active_counts = active_mask.sum(axis=1)
    avg_active_positions = active_counts[active_counts > 0].mean() if active_rebal_dates > 0 else 0.0
    
    # 4. Total reweighting events (trades) in the target weights schedule
    # Count how many times a ticker's weight changes from one rebalance date to the next
    reweight_changes = weights_df.diff().fillna(weights_df.iloc[0]).abs() > 1e-5
    total_target_trades = reweight_changes.sum().sum()
    
    # 5. Daily weighting events (including stop-loss/drawdown exit/re-entry events)
    # A daily trade is triggered when daily weight changes
    daily_changes = daily_weights_held.diff().fillna(daily_weights_held.iloc[0]).abs() > 1e-5
    total_daily_trades = daily_changes.sum().sum()
    
    # 6. Total Position-Days (number of days * tickers where we held a non-zero position)
    total_position_days = (daily_weights_held.abs() > 1e-5).sum().sum()
    
    return {
        "total_rebal_dates": total_rebal_dates,
        "active_rebal_dates": active_rebal_dates,
        "avg_active_positions": avg_active_positions,
        "total_target_trades": total_target_trades,
        "total_daily_trades": total_daily_trades,
        "total_position_days": total_position_days,
    }

def main():
    universe = get_ai_infra_universe()
    all_symbols = [t for tickers in universe.values() for t in tickers]
    close, volume, bench_close = download_ai_infra_data(symbols=all_symbols, period="5y", interval="1d")
    _, _, _, valid_close, valid_volume = validate_ai_infra_data(close, volume)
    daily_returns = valid_close.pct_change()
    
    dollar_vol = (valid_close * valid_volume).rolling(63).median()
    momentum_signals = valid_close.shift(21) / valid_close.shift(252) - 1.0
    
    rebal_dates = valid_close.resample("ME").last().index
    rebal_dates = [d for d in rebal_dates if d in valid_close.index]
    
    # Generate weights
    full_ew = pd.DataFrame(0.0, index=rebal_dates, columns=valid_close.columns)
    static_uncorr_ew = pd.DataFrame(0.0, index=rebal_dates, columns=valid_close.columns)
    dynamic_uncorr_ew = pd.DataFrame(0.0, index=rebal_dates, columns=valid_close.columns)
    dynamic_uncorr_mvo = pd.DataFrame(0.0, index=rebal_dates, columns=valid_close.columns)
    
    static_uncorr_symbols = find_uncorrelated_assets(daily_returns, max_correlation=0.55)

    for d in rebal_dates:
        liq = dollar_vol.loc[d]
        liq_eligible = [sym for sym in valid_close.columns if liq[sym] >= 25e6]
        eligible = [sym for sym in liq_eligible if pd.notna(momentum_signals.loc[d, sym])]
        if len(eligible) < 6:
            continue
            
        # Full EW
        moms_full = momentum_signals.loc[d, eligible].sort_values()
        k_full = len(moms_full) // 2
        longs_full = moms_full.index[-k_full:]
        full_ew.loc[d, longs_full] = 1.0 / k_full
        
        # Static Uncorr
        eligible_static = [sym for sym in eligible if sym in static_uncorr_symbols]
        moms_static = momentum_signals.loc[d, eligible_static].sort_values()
        k_static = max(1, len(moms_static) // 2)
        longs_static = moms_static.index[-k_static:]
        static_uncorr_ew.loc[d, longs_static] = 1.0 / k_static
        
        # Dynamic Uncorr
        idx_loc = daily_returns.index.get_loc(d)
        if idx_loc < 252:
            continue
        hist_returns = daily_returns.iloc[idx_loc-252:idx_loc][eligible]
        dyn_uncorr_symbols = find_uncorrelated_assets(hist_returns, max_correlation=0.55)
        pos_mom_dyn = [sym for sym in dyn_uncorr_symbols if momentum_signals.loc[d, sym] > 0.0]
        
        if pos_mom_dyn:
            dynamic_uncorr_ew.loc[d, pos_mom_dyn] = 1.0 / len(pos_mom_dyn)
            
            # MVO
            opt_w_dict = optimize_portfolio_mvo(
                returns_df=hist_returns[pos_mom_dyn],
                momentum_signals=momentum_signals.loc[d],
                max_weight=0.35,
            )
            for ticker, w in opt_w_dict.items():
                dynamic_uncorr_mvo.loc[d, ticker] = w

    # Run simulations to obtain actual daily weights held
    from scripts.run_semiconductor_optimized import run_backtest_with_stop_loss
    
    # 1. Full EW
    bt_full = run_backtest_with_stop_loss(daily_returns, full_ew, stop_loss_threshold=-1.0)
    # 2. Static Uncorr
    bt_static = run_backtest_with_stop_loss(daily_returns, static_uncorr_ew, stop_loss_threshold=-1.0)
    # 3. Dynamic Uncorr EW
    bt_dyn_ew = run_backtest_with_stop_loss(daily_returns, dynamic_uncorr_ew, stop_loss_threshold=-1.0)
    # 4. MVO (No Control)
    bt_mvo = run_backtest_with_stop_loss(daily_returns, dynamic_uncorr_mvo, stop_loss_threshold=-1.0)
    # 5. MVO + Stop Loss (-15%)
    bt_mvo_risk = run_backtest_with_stop_loss(daily_returns, dynamic_uncorr_mvo, stop_loss_threshold=-0.15, lockout_days=21)
    # 6. DD Scaling (18% Cap)
    bt_scale_20 = run_backtest_with_drawdown_scaling(daily_returns, dynamic_uncorr_mvo, max_dd_cap=0.18)
    # 7. DD Scaling (13% Cap)
    bt_scale_15 = run_backtest_with_drawdown_scaling(daily_returns, dynamic_uncorr_mvo, max_dd_cap=0.13)
    # 8. Vol + DD Scaling (18% Cap)
    bt_vol_dd = run_backtest_with_vol_and_drawdown_targeting(daily_returns, dynamic_uncorr_mvo, max_dd_cap=0.18, target_vol=0.18)
    
    # Analyze bets
    stats = {
        "Full EW": analyze_strategy_bets(full_ew, bt_full["weights"]),
        "Static Uncorr EW": analyze_strategy_bets(static_uncorr_ew, bt_static["weights"]),
        "Dynamic Uncorr EW": analyze_strategy_bets(dynamic_uncorr_ew, bt_dyn_ew["weights"]),
        "Base MVO (No Control)": analyze_strategy_bets(dynamic_uncorr_mvo, bt_mvo["weights"]),
        "MVO + Stop Loss (-15%)": analyze_strategy_bets(dynamic_uncorr_mvo, bt_mvo_risk["weights"]),
        "DD Scaling (18% Cap)": analyze_strategy_bets(dynamic_uncorr_mvo, bt_scale_20["weights"]),
        "DD Scaling (13% Cap)": analyze_strategy_bets(dynamic_uncorr_mvo, bt_scale_15["weights"]),
        "Vol+DD Target (18% Cap)": analyze_strategy_bets(dynamic_uncorr_mvo, bt_vol_dd["weights"]),
    }
    
    df_stats = pd.DataFrame(stats).T
    print("\n" + "=" * 100)
    print("  BET AND WEIGHTING STATISTICS ACROSS STRATEGIES")
    print("=" * 100)
    print(df_stats.to_string())
    print("=" * 100)

if __name__ == "__main__":
    main()
