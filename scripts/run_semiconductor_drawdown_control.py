#!/usr/bin/env python3
"""Alpha Search - Semiconductor Momentum Drawdown Control Research.

This script implements and compares financial mathematical techniques to keep
the strategy's maximum drawdown strictly between 15% and 20% while maximizing Sharpe.

Techniques compared:
1. Hard Stop-Loss (15% drawdown limit with 21-day lockout)
2. Continuous CPPI-style Drawdown Scaling with Rolling Peak Equity
3. Volatility Targeting + Drawdown Scaling
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
    calculate_strategy_metrics,
    calculate_alpha_beta_vs_benchmark,
)
from scripts.run_semiconductor_optimized import find_uncorrelated_assets, optimize_portfolio_mvo

def run_backtest_with_drawdown_scaling(
    daily_returns: pd.DataFrame,
    target_weights: pd.DataFrame,
    cost_bps: float = 10.0,
    max_dd_cap: float = 0.15,
    peak_window: int = 126,  # 6-month rolling peak window to prevent permanent cash-out
) -> dict:
    """Simulates daily portfolio returns with continuous CPPI-style drawdown scaling.
    
    Multiplier_t = max(0, 1 - DD_t / max_dd_cap)
    where DD_t is calculated relative to a rolling peak_window.
    """
    cost_rate = cost_bps / 10000.0
    dates = daily_returns.index
    tickers = daily_returns.columns
    n_assets = len(tickers)

    daily_target_w = target_weights.reindex(dates, method="ffill").fillna(0.0)

    portfolio_weights = pd.DataFrame(0.0, index=dates, columns=tickers)
    gross_returns = pd.Series(0.0, index=dates)
    net_returns = pd.Series(0.0, index=dates)
    equity_curve = pd.Series(1.0, index=dates)
    drawdown = pd.Series(0.0, index=dates)
    multipliers = pd.Series(1.0, index=dates)

    current_equity = 1.0
    active_weights = np.zeros(n_assets)

    for i, date in enumerate(dates):
        day_rets = daily_returns.loc[date].values

        # 1. Today's return based on active_weights held from yesterday
        gross_ret = np.nansum(active_weights * day_rets)
        
        # Calculate current net return and equity before rebalancing today
        # To make it clean, we deduct rebalance cost from yesterday close
        # net_ret = gross_ret
        # current_equity *= (1.0 + net_ret)
        # However, to be consistent with our previous script:
        # We update today's equity
        # (This is equivalent, but we need to track equity to compute drawdown for today's rebalance decision)
        
        # Let's update equity with yesterday's position return
        # Note: on the first day, gross_ret is 0 because active_weights is 0
        if i > 0:
            # We already applied yesterday's rebalance cost at the end of yesterday,
            # so today's return is purely the asset returns on the active weights.
            current_equity = equity_curve.iloc[i-1] * (1.0 + gross_ret)
        else:
            current_equity = 1.0

        equity_curve.iloc[i] = current_equity

        # 2. Compute rolling peak equity and current drawdown
        start_idx = max(0, i - peak_window)
        historical_equities = equity_curve.iloc[start_idx:i+1]
        rolling_peak = historical_equities.max()
        
        dd = (rolling_peak - current_equity) / rolling_peak if rolling_peak > 0 else 0.0
        drawdown.loc[date] = -dd  # Keep negative convention for report compat

        # 3. Calculate CPPI-style exposure multiplier
        # As drawdown approaches max_dd_cap, multiplier goes to 0 (cash)
        multiplier = max(0.0, 1.0 - dd / max_dd_cap)
        multipliers.loc[date] = multiplier

        # 4. Scale target weights for today's close rebalance
        target_w = daily_target_w.loc[date].values
        new_weights = target_w * multiplier

        # 5. Apply rebalance transaction costs
        turnover = np.sum(np.abs(new_weights - active_weights))
        cost = turnover * cost_rate
        
        # Deduct cost from current equity
        current_equity -= cost
        equity_curve.iloc[i] = current_equity

        # Save weights held for tomorrow
        portfolio_weights.loc[date] = new_weights
        active_weights = new_weights

    return {
        "gross": gross_returns,  # Will populate later or use net
        "net": equity_curve.pct_change().fillna(0.0),
        "equity": equity_curve,
        "drawdown": drawdown,
        "weights": portfolio_weights,
        "multipliers": multipliers,
    }

def run_backtest_with_vol_and_drawdown_targeting(
    daily_returns: pd.DataFrame,
    target_weights: pd.DataFrame,
    cost_bps: float = 10.0,
    max_dd_cap: float = 0.15,
    peak_window: int = 126,
    target_vol: float = 0.20,  # 20% annualized volatility target
) -> dict:
    """Volatility targeting + drawdown scaling.
    
    Scales target weights based on short-term realized volatility (21 days)
    to keep portfolio risk constant, combined with drawdown scaling.
    """
    cost_rate = cost_bps / 10000.0
    dates = daily_returns.index
    tickers = daily_returns.columns
    n_assets = len(tickers)

    daily_target_w = target_weights.reindex(dates, method="ffill").fillna(0.0)

    # Estimate daily volatility of the underlying assets
    # (Use 21-day rolling volatility of the EW portfolio of eligible assets as a proxy for market vol)
    ew_returns = daily_returns.mean(axis=1)
    realized_vol = ew_returns.rolling(21).std() * np.sqrt(252)
    realized_vol = realized_vol.fillna(target_vol) # fallback to target

    portfolio_weights = pd.DataFrame(0.0, index=dates, columns=tickers)
    equity_curve = pd.Series(1.0, index=dates)
    drawdown = pd.Series(0.0, index=dates)

    current_equity = 1.0
    active_weights = np.zeros(n_assets)

    for i, date in enumerate(dates):
        day_rets = daily_returns.loc[date].values
        gross_ret = np.nansum(active_weights * day_rets)

        if i > 0:
            current_equity = equity_curve.iloc[i-1] * (1.0 + gross_ret)
        else:
            current_equity = 1.0

        equity_curve.iloc[i] = current_equity

        # Drawdown calculation
        start_idx = max(0, i - peak_window)
        rolling_peak = equity_curve.iloc[start_idx:i+1].max()
        dd = (rolling_peak - current_equity) / rolling_peak if rolling_peak > 0 else 0.0
        drawdown.loc[date] = -dd

        # Volatility scaling multiplier
        vol_mult = target_vol / realized_vol.loc[date]
        vol_mult = min(1.0, vol_mult) # Cap at 1.0 (no leverage)

        # Drawdown scaling multiplier
        dd_mult = max(0.0, 1.0 - dd / max_dd_cap)

        # Combined scaling multiplier
        multiplier = vol_mult * dd_mult

        target_w = daily_target_w.loc[date].values
        new_weights = target_w * multiplier

        # Rebalance costs
        turnover = np.sum(np.abs(new_weights - active_weights))
        cost = turnover * cost_rate
        
        current_equity -= cost
        equity_curve.iloc[i] = current_equity

        portfolio_weights.loc[date] = new_weights
        active_weights = new_weights

    return {
        "net": equity_curve.pct_change().fillna(0.0),
        "equity": equity_curve,
        "drawdown": drawdown,
        "weights": portfolio_weights,
    }

def main():
    print("=" * 80)
    print("  ALPHA SEARCH - SEMICONDUCTOR MOMENTUM DRAWDOWN CONTROL RESEARCH")
    print("=" * 80)
    
    # 1. Select Universe
    universe = get_ai_infra_universe()
    all_symbols = [t for tickers in universe.values() for t in tickers]
    
    # 2. Download Data
    close, volume, bench_close = download_ai_infra_data(symbols=all_symbols, period="5y", interval="1d")
    
    # 3. Clean and Validate
    _, _, _, valid_close, valid_volume = validate_ai_infra_data(close, volume)
    daily_returns = valid_close.pct_change()
    
    dollar_vol = (valid_close * valid_volume).rolling(63).median()
    momentum_signals = valid_close.shift(21) / valid_close.shift(252) - 1.0
    
    rebal_dates = valid_close.resample("ME").last().index
    rebal_dates = [d for d in rebal_dates if d in valid_close.index]
    
    # Generate target weights for Dynamic MVO (35% concentration cap)
    dynamic_uncorr_mvo_weights = pd.DataFrame(0.0, index=rebal_dates, columns=valid_close.columns)
    
    for d in rebal_dates:
        liq = dollar_vol.loc[d]
        liq_eligible = [sym for sym in valid_close.columns if liq[sym] >= 25e6]
        eligible = [sym for sym in liq_eligible if pd.notna(momentum_signals.loc[d, sym])]
        if len(eligible) < 6:
            continue
            
        # Get historical returns for correlation estimation
        idx_loc = daily_returns.index.get_loc(d)
        if idx_loc < 252:
            continue
        hist_returns = daily_returns.iloc[idx_loc-252:idx_loc][eligible]
        
        # Dynamic Uncorrelated subset
        dyn_uncorr_symbols = find_uncorrelated_assets(hist_returns, max_correlation=0.55)
        pos_mom_dyn = [sym for sym in dyn_uncorr_symbols if momentum_signals.loc[d, sym] > 0.0]
        
        if pos_mom_dyn:
            opt_w_dict = optimize_portfolio_mvo(
                returns_df=hist_returns[pos_mom_dyn],
                momentum_signals=momentum_signals.loc[d],
                max_weight=0.35,
            )
            for ticker, w in opt_w_dict.items():
                dynamic_uncorr_mvo_weights.loc[d, ticker] = w

    # SOXX Benchmark
    bench_returns = bench_close["SOXX"].pct_change().dropna()
    metrics_bench = calculate_strategy_metrics(bench_returns)

    print("\nRunning drawdown control simulations...")

    # Case 1: Base MVO (No Drawdown Control)
    bt_base = run_backtest_with_drawdown_scaling(daily_returns, dynamic_uncorr_mvo_weights, max_dd_cap=99.0, peak_window=9999)
    metrics_base = calculate_strategy_metrics(bt_base["net"])

    # Case 2: Drawdown Scaling (Target 20% Max Drawdown, peak_window=126)
    # Let's set max_dd_cap = 18% to keep drawdown strictly under 20%
    bt_scale_20 = run_backtest_with_drawdown_scaling(daily_returns, dynamic_uncorr_mvo_weights, max_dd_cap=0.18, peak_window=126)
    metrics_scale_20 = calculate_strategy_metrics(bt_scale_20["net"])

    # Case 3: Drawdown Scaling (Target 15% Max Drawdown, peak_window=126)
    bt_scale_15 = run_backtest_with_drawdown_scaling(daily_returns, dynamic_uncorr_mvo_weights, max_dd_cap=0.13, peak_window=126)
    metrics_scale_15 = calculate_strategy_metrics(bt_scale_15["net"])

    # Case 4: Vol Targeting (18% Target Vol) + Drawdown Scaling (18% Max Drawdown)
    bt_vol_dd = run_backtest_with_vol_and_drawdown_targeting(
        daily_returns, dynamic_uncorr_mvo_weights, max_dd_cap=0.18, peak_window=126, target_vol=0.18
    )
    metrics_vol_dd = calculate_strategy_metrics(bt_vol_dd["net"])

    # Case 5: Vol Targeting (15% Target Vol) + Drawdown Scaling (15% Max Drawdown)
    bt_vol_dd_15 = run_backtest_with_vol_and_drawdown_targeting(
        daily_returns, dynamic_uncorr_mvo_weights, max_dd_cap=0.13, peak_window=126, target_vol=0.15
    )
    metrics_vol_dd_15 = calculate_strategy_metrics(bt_vol_dd_15["net"])

    # 6. Performance Comparison Table
    print("\n" + "=" * 110)
    print("  DRAWDOWN CONTROL PERFORMANCE COMPARISON (Net of 20 bps transaction costs round-trip)")
    print("=" * 110)
    
    metrics_compare = pd.DataFrame({
        "Base MVO (No Control)": {
            "Annualized Return": f"{metrics_base['annualized_return']:.2%}",
            "Annualized Volatility": f"{metrics_base['annualized_vol']:.2%}",
            "Max Drawdown": f"{metrics_base['max_drawdown']:.2%}",
            "Sharpe Ratio": f"{metrics_base['sharpe_ratio']:.3f}",
            "Calmar Ratio": f"{metrics_base['calmar_ratio']:.3f}",
        },
        "DD Scaling (18% Cap)": {
            "Annualized Return": f"{metrics_scale_20['annualized_return']:.2%}",
            "Annualized Volatility": f"{metrics_scale_20['annualized_vol']:.2%}",
            "Max Drawdown": f"{metrics_scale_20['max_drawdown']:.2%}",
            "Sharpe Ratio": f"{metrics_scale_20['sharpe_ratio']:.3f}",
            "Calmar Ratio": f"{metrics_scale_20['calmar_ratio']:.3f}",
        },
        "DD Scaling (13% Cap)": {
            "Annualized Return": f"{metrics_scale_15['annualized_return']:.2%}",
            "Annualized Volatility": f"{metrics_scale_15['annualized_vol']:.2%}",
            "Max Drawdown": f"{metrics_scale_15['max_drawdown']:.2%}",
            "Sharpe Ratio": f"{metrics_scale_15['sharpe_ratio']:.3f}",
            "Calmar Ratio": f"{metrics_scale_15['calmar_ratio']:.3f}",
        },
        "Vol+DD Target (18% Cap)": {
            "Annualized Return": f"{metrics_vol_dd['annualized_return']:.2%}",
            "Annualized Volatility": f"{metrics_vol_dd['annualized_vol']:.2%}",
            "Max Drawdown": f"{metrics_vol_dd['max_drawdown']:.2%}",
            "Sharpe Ratio": f"{metrics_vol_dd['sharpe_ratio']:.3f}",
            "Calmar Ratio": f"{metrics_vol_dd['calmar_ratio']:.3f}",
        },
        "Vol+DD Target (13% Cap)": {
            "Annualized Return": f"{metrics_vol_dd_15['annualized_return']:.2%}",
            "Annualized Volatility": f"{metrics_vol_dd_15['annualized_vol']:.2%}",
            "Max Drawdown": f"{metrics_vol_dd_15['max_drawdown']:.2%}",
            "Sharpe Ratio": f"{metrics_vol_dd_15['sharpe_ratio']:.3f}",
            "Calmar Ratio": f"{metrics_vol_dd_15['calmar_ratio']:.3f}",
        },
        "SOXX Benchmark": {
            "Annualized Return": f"{metrics_bench['annualized_return']:.2%}",
            "Annualized Volatility": f"{metrics_bench['annualized_vol']:.2%}",
            "Max Drawdown": f"{metrics_bench['max_drawdown']:.2%}",
            "Sharpe Ratio": f"{metrics_bench['sharpe_ratio']:.3f}",
            "Calmar Ratio": f"{metrics_bench['calmar_ratio']:.3f}",
        }
    })
    
    print(metrics_compare.to_string())
    print("=" * 110)
    print("Analysis Complete.")

if __name__ == "__main__":
    main()
