#!/usr/bin/env python3
"""Alpha Search - Semiconductor & AI Infrastructure Optimized Portfolio Research.

This script executes a advanced portfolio research pipeline:
1. Select Universe: US AI Infrastructure & Semiconductors (32 symbols).
2. Volume Filter: Daily volume >= $25M (63-day median).
3. Dynamic Correlation Filter: Dynamic selection of assets with pairwise correlation <= 0.55 over trailing 252 days.
4. Signal: 12-1 Month momentum.
5. Portfolio Optimization: Mean-Variance Optimization (MVO) with a 35% single-stock concentration cap.
6. Risk Controls: -15% drawdown stop-loss that rotates to cash for 1 month (21 trading days), resetting peak equity baseline on re-entry.
7. Backtest: Vectorized monthly rebalance net-of-costs (20 bps round-trip).
8. Performance comparison of various configurations.
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

def find_uncorrelated_assets(returns_df: pd.DataFrame, max_correlation: float = 0.55) -> list[str]:
    """Greedy algorithm to find a subset of uncorrelated assets."""
    if returns_df.empty:
        return []
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

def optimize_portfolio_mvo(
    returns_df: pd.DataFrame,
    momentum_signals: pd.Series,
    max_weight: float = 0.35,
) -> dict[str, float]:
    """Solves Mean-Variance Optimization using SciPy.
    
    Objective: Maximize utility = w.T * mu - 0.5 * w.T * Sigma * w
    Constraints: sum(w) = 1.0, 0.0 <= w_i <= max(max_weight, 1/n)
    """
    tickers = list(returns_df.columns)
    n = len(tickers)
    if n == 0:
        return {}
    if n == 1:
        return {tickers[0]: 1.0}

    # Expected returns based on momentum signals
    mu = momentum_signals.loc[tickers].values
    # Covariance matrix (annualized)
    cov = returns_df.cov().values * 252
    
    # Ensure positive semi-definite covariance
    eigvals = np.linalg.eigvalsh(cov)
    if np.min(eigvals) < 1e-8:
        cov = cov + np.eye(n) * 1e-6

    from scipy.optimize import minimize

    # Minimize negative utility
    def objective(w):
        return - np.sum(w * mu) + 0.5 * np.dot(w, np.dot(cov, w))

    # Constraints: sum to 1.0
    constraints = [{"type": "eq", "fun": lambda w: np.sum(w) - 1.0}]
    
    # Bounds: long-only with concentration cap
    upper_bound = max(max_weight, 1.0 / n)
    bounds = [(0.0, upper_bound)] * n
    
    x0 = np.ones(n) / n
    try:
        res = minimize(
            objective,
            x0,
            method="SLSQP",
            bounds=bounds,
            constraints=constraints,
            options={"maxiter": 1000, "ftol": 1e-9},
        )
        if res.success:
            weights = np.maximum(res.x, 0.0)
            weights /= np.sum(weights) if np.sum(weights) > 0 else 1.0
            return {t: float(w) for t, w in zip(tickers, weights)}
    except Exception:
        pass
    
    # Fallback to equal weight
    return {t: 1.0 / n for t in tickers}

def run_backtest_with_stop_loss(
    daily_returns: pd.DataFrame,
    target_weights: pd.DataFrame,
    cost_bps: float = 10.0,
    stop_loss_threshold: float = -0.15,
    lockout_days: int = 21,
) -> dict:
    """Simulates daily portfolio returns with transaction costs and path-dependent stop-loss.
    
    Drawdown stop-loss rotates portfolio to cash for lockout_days.
    Resets peak equity baseline upon re-entry.
    """
    cost_rate = cost_bps / 10000.0
    dates = daily_returns.index
    tickers = daily_returns.columns
    n_assets = len(tickers)

    # Align target_weights to all daily dates via forward-fill
    daily_target_w = target_weights.reindex(dates, method="ffill").fillna(0.0)

    # Initialize structures
    portfolio_weights = pd.DataFrame(0.0, index=dates, columns=tickers)
    gross_returns = pd.Series(0.0, index=dates)
    net_returns = pd.Series(0.0, index=dates)
    equity_curve = pd.Series(1.0, index=dates)
    drawdown = pd.Series(0.0, index=dates)

    current_equity = 1.0
    peak_equity = 1.0
    active_weights = np.zeros(n_assets)  # weights held yesterday

    lockout_timer = 0
    is_stopped_out = False

    for i, date in enumerate(dates):
        day_rets = daily_returns.loc[date].values

        # 1. Compute today's return based on active_weights (held from yesterday)
        gross_ret = np.nansum(active_weights * day_rets)
        
        # 2. Determine target weights for today's close
        target_w = daily_target_w.loc[date].values

        if is_stopped_out:
            lockout_timer -= 1
            if lockout_timer <= 0:
                # Lockout ends. Re-enter at today's close using target_w
                is_stopped_out = False
                new_weights = target_w
                # Reset peak equity baseline to new equity level
                peak_equity = current_equity * (1.0 + gross_ret)
            else:
                # Remain in cash
                new_weights = np.zeros(n_assets)
        else:
            # Normal state
            new_weights = target_w

        # 3. Calculate turnover and transaction cost for today's rebalance
        turnover = np.sum(np.abs(new_weights - active_weights))
        cost = turnover * cost_rate

        net_ret = gross_ret - cost
        current_equity *= (1.0 + net_ret)

        # Track metrics
        gross_returns.loc[date] = gross_ret
        net_returns.loc[date] = net_ret
        equity_curve.loc[date] = current_equity

        # 4. Check for stop-loss trigger (based on today's equity)
        peak_equity = max(peak_equity, current_equity)
        dd = (current_equity - peak_equity) / peak_equity
        drawdown.loc[date] = dd

        if dd <= stop_loss_threshold and not is_stopped_out:
            # Trigger stop-loss today. Rotate to cash at today's close
            is_stopped_out = True
            lockout_timer = lockout_days
            
            # Apply exit transaction cost immediately
            exit_turnover = np.sum(np.abs(new_weights))
            exit_cost = exit_turnover * cost_rate
            net_ret -= exit_cost
            current_equity /= (1.0 + exit_cost)
            
            equity_curve.loc[date] = current_equity
            dd = (current_equity - peak_equity) / peak_equity
            drawdown.loc[date] = dd
            
            new_weights = np.zeros(n_assets)

        # Save weights held for tomorrow
        portfolio_weights.loc[date] = new_weights
        active_weights = new_weights

    return {
        "gross": gross_returns,
        "net": net_returns,
        "equity": equity_curve,
        "drawdown": drawdown,
        "weights": portfolio_weights,
    }

def main():
    print("=" * 80)
    print("  ALPHA SEARCH - ADVANCED SEMICONDUCTOR MOMENTUM PORTFOLIO RESEARCH")
    print("=" * 80)
    
    # 1. Select Universe
    universe = get_ai_infra_universe()
    all_symbols = [t for tickers in universe.values() for t in tickers]
    print(f"Initial Universe: {len(all_symbols)} symbols.")
    
    # 2. Download Data
    print("\nDownloading 5 years of daily price & volume data via yfinance...")
    close, volume, bench_close = download_ai_infra_data(symbols=all_symbols, period="5y", interval="1d")
    
    # 3. Clean and Validate
    _, _, skipped, valid_close, valid_volume = validate_ai_infra_data(close, volume)
    print(f"Data validation complete. Valid symbols: {len(valid_close.columns)} (Skipped: {len(skipped)})")
    
    daily_returns = valid_close.pct_change()
    
    # Pre-calculate rolling median dollar volume for liquidity screen
    dollar_vol = (valid_close * valid_volume).rolling(63).median()
    
    # Pre-calculate 12-1 Month momentum signals
    momentum_signals = valid_close.shift(21) / valid_close.shift(252) - 1.0
    
    rebal_dates = valid_close.resample("ME").last().index
    rebal_dates = [d for d in rebal_dates if d in valid_close.index]
    
    # Initialize target weight DataFrames
    full_ew_weights = pd.DataFrame(0.0, index=rebal_dates, columns=valid_close.columns)
    static_uncorr_ew_weights = pd.DataFrame(0.0, index=rebal_dates, columns=valid_close.columns)
    dynamic_uncorr_ew_weights = pd.DataFrame(0.0, index=rebal_dates, columns=valid_close.columns)
    dynamic_uncorr_mvo_weights = pd.DataFrame(0.0, index=rebal_dates, columns=valid_close.columns)
    
    # Define Static Uncorrelated Universe for comparative testing
    static_uncorr_symbols = find_uncorrelated_assets(daily_returns, max_correlation=0.55)
    print(f"Static Uncorrelated Symbols (overall): {len(static_uncorr_symbols)} assets: {static_uncorr_symbols}")

    print("\nGenerating strategy target weights dynamically at each rebalance date...")
    for d in rebal_dates:
        # Determine liquidity-eligible assets at date d
        liq = dollar_vol.loc[d]
        liq_eligible = [sym for sym in valid_close.columns if liq[sym] >= 25e6]
        
        # Ensure they have historical momentum signals
        eligible = [sym for sym in liq_eligible if pd.notna(momentum_signals.loc[d, sym])]
        if len(eligible) < 6:
            continue
            
        # 1. Full Universe EW (top 50% momentum)
        moms_full = momentum_signals.loc[d, eligible].sort_values()
        k_full = len(moms_full) // 2
        longs_full = moms_full.index[-k_full:]
        full_ew_weights.loc[d, longs_full] = 1.0 / k_full
        
        # 2. Static Uncorrelated EW (top 50% momentum within the static subset)
        eligible_static = [sym for sym in eligible if sym in static_uncorr_symbols]
        moms_static = momentum_signals.loc[d, eligible_static].sort_values()
        k_static = max(1, len(moms_static) // 2)
        longs_static = moms_static.index[-k_static:]
        static_uncorr_ew_weights.loc[d, longs_static] = 1.0 / k_static
        
        # 3. Dynamic Uncorrelated Selection
        # Get historical returns for correlation estimation
        # We need historical daily returns up to date d (trailing 252 days)
        idx_loc = daily_returns.index.get_loc(d)
        if idx_loc < 252:
            continue
        hist_returns = daily_returns.iloc[idx_loc-252:idx_loc][eligible]
        
        # Dynamic Uncorrelated subset
        dyn_uncorr_symbols = find_uncorrelated_assets(hist_returns, max_correlation=0.55)
        
        # Filter to positive momentum confirmation
        pos_mom_dyn = [sym for sym in dyn_uncorr_symbols if momentum_signals.loc[d, sym] > 0.0]
        
        if pos_mom_dyn:
            # Equal weight on positive momentum dynamic uncorrelated assets
            dynamic_uncorr_ew_weights.loc[d, pos_mom_dyn] = 1.0 / len(pos_mom_dyn)
            
            # 4. MVO with 35% concentration cap
            # Pass historical returns of selected assets
            opt_w_dict = optimize_portfolio_mvo(
                returns_df=hist_returns[pos_mom_dyn],
                momentum_signals=momentum_signals.loc[d],
                max_weight=0.35,
            )
            for ticker, w in opt_w_dict.items():
                dynamic_uncorr_mvo_weights.loc[d, ticker] = w

    # 5. Run backtests
    print("\nSimulating daily portfolios net of 10 bps costs...")
    
    # A. Full Universe EW (no stop-loss)
    bt_full_ew = run_backtest_with_stop_loss(daily_returns, full_ew_weights, stop_loss_threshold=-1.0)
    metrics_full_ew = calculate_strategy_metrics(bt_full_ew["net"])
    
    # B. Static Uncorrelated EW (no stop-loss)
    bt_static_uncorr = run_backtest_with_stop_loss(daily_returns, static_uncorr_ew_weights, stop_loss_threshold=-1.0)
    metrics_static_uncorr = calculate_strategy_metrics(bt_static_uncorr["net"])
    
    # C. Dynamic Uncorrelated EW (no stop-loss)
    bt_dyn_uncorr_ew = run_backtest_with_stop_loss(daily_returns, dynamic_uncorr_ew_weights, stop_loss_threshold=-1.0)
    metrics_dyn_uncorr_ew = calculate_strategy_metrics(bt_dyn_uncorr_ew["net"])
    
    # D. Dynamic Uncorrelated MVO (no stop-loss)
    bt_dyn_uncorr_mvo = run_backtest_with_stop_loss(daily_returns, dynamic_uncorr_mvo_weights, stop_loss_threshold=-1.0)
    metrics_dyn_uncorr_mvo = calculate_strategy_metrics(bt_dyn_uncorr_mvo["net"])
    
    # E. Dynamic Uncorrelated MVO + Risk Controls (-15% drawdown stop-loss, 35% cap)
    bt_dyn_uncorr_mvo_risk = run_backtest_with_stop_loss(
        daily_returns, dynamic_uncorr_mvo_weights, stop_loss_threshold=-0.15, lockout_days=21
    )
    metrics_dyn_uncorr_mvo_risk = calculate_strategy_metrics(bt_dyn_uncorr_mvo_risk["net"])
    
    # SOXX Benchmark
    bench_returns = bench_close["SOXX"].pct_change().dropna()
    metrics_bench = calculate_strategy_metrics(bench_returns)
    
    # Regressions
    ab_full = calculate_alpha_beta_vs_benchmark(bt_full_ew["net"], bench_returns)
    ab_static = calculate_alpha_beta_vs_benchmark(bt_static_uncorr["net"], bench_returns)
    ab_dyn_ew = calculate_alpha_beta_vs_benchmark(bt_dyn_uncorr_ew["net"], bench_returns)
    ab_dyn_mvo = calculate_alpha_beta_vs_benchmark(bt_dyn_uncorr_mvo["net"], bench_returns)
    ab_dyn_mvo_risk = calculate_alpha_beta_vs_benchmark(bt_dyn_uncorr_mvo_risk["net"], bench_returns)

    # 6. Performance Comparison Table
    print("\n" + "=" * 100)
    print("  STRATEGY PERFORMANCE COMPARISON (Net of 20 bps transaction costs round-trip)")
    print("=" * 100)
    
    metrics_compare = pd.DataFrame({
        "Full EW (No Filter)": {
            "Annualized Return": f"{metrics_full_ew['annualized_return']:.2%}",
            "Annualized Volatility": f"{metrics_full_ew['annualized_vol']:.2%}",
            "Max Drawdown": f"{metrics_full_ew['max_drawdown']:.2%}",
            "Sharpe Ratio": f"{metrics_full_ew['sharpe_ratio']:.3f}",
            "Calmar Ratio": f"{metrics_full_ew['calmar_ratio']:.3f}",
            "Annualized Alpha": f"{ab_full['ann_alpha']:.2%}",
            "Beta vs SOXX": f"{ab_full['beta']:.3f}",
            "t-stat(Alpha)": f"{ab_full['t_alpha']:.2f}"
        },
        "Static Uncorr EW": {
            "Annualized Return": f"{metrics_static_uncorr['annualized_return']:.2%}",
            "Annualized Volatility": f"{metrics_static_uncorr['annualized_vol']:.2%}",
            "Max Drawdown": f"{metrics_static_uncorr['max_drawdown']:.2%}",
            "Sharpe Ratio": f"{metrics_static_uncorr['sharpe_ratio']:.3f}",
            "Calmar Ratio": f"{metrics_static_uncorr['calmar_ratio']:.3f}",
            "Annualized Alpha": f"{ab_static['ann_alpha']:.2%}",
            "Beta vs SOXX": f"{ab_static['beta']:.3f}",
            "t-stat(Alpha)": f"{ab_static['t_alpha']:.2f}"
        },
        "Dynamic Uncorr EW": {
            "Annualized Return": f"{metrics_dyn_uncorr_ew['annualized_return']:.2%}",
            "Annualized Volatility": f"{metrics_dyn_uncorr_ew['annualized_vol']:.2%}",
            "Max Drawdown": f"{metrics_dyn_uncorr_ew['max_drawdown']:.2%}",
            "Sharpe Ratio": f"{metrics_dyn_uncorr_ew['sharpe_ratio']:.3f}",
            "Calmar Ratio": f"{metrics_dyn_uncorr_ew['calmar_ratio']:.3f}",
            "Annualized Alpha": f"{ab_dyn_ew['ann_alpha']:.2%}",
            "Beta vs SOXX": f"{ab_dyn_ew['beta']:.3f}",
            "t-stat(Alpha)": f"{ab_dyn_ew['t_alpha']:.2f}"
        },
        "Dynamic MVO (35% Cap)": {
            "Annualized Return": f"{metrics_dyn_uncorr_mvo['annualized_return']:.2%}",
            "Annualized Volatility": f"{metrics_dyn_uncorr_mvo['annualized_vol']:.2%}",
            "Max Drawdown": f"{metrics_dyn_uncorr_mvo['max_drawdown']:.2%}",
            "Sharpe Ratio": f"{metrics_dyn_uncorr_mvo['sharpe_ratio']:.3f}",
            "Calmar Ratio": f"{metrics_dyn_uncorr_mvo['calmar_ratio']:.3f}",
            "Annualized Alpha": f"{ab_dyn_mvo['ann_alpha']:.2%}",
            "Beta vs SOXX": f"{ab_dyn_mvo['beta']:.3f}",
            "t-stat(Alpha)": f"{ab_dyn_mvo['t_alpha']:.2f}"
        },
        "MVO + Risk Controls": {
            "Annualized Return": f"{metrics_dyn_uncorr_mvo_risk['annualized_return']:.2%}",
            "Annualized Volatility": f"{metrics_dyn_uncorr_mvo_risk['annualized_vol']:.2%}",
            "Max Drawdown": f"{metrics_dyn_uncorr_mvo_risk['max_drawdown']:.2%}",
            "Sharpe Ratio": f"{metrics_dyn_uncorr_mvo_risk['sharpe_ratio']:.3f}",
            "Calmar Ratio": f"{metrics_dyn_uncorr_mvo_risk['calmar_ratio']:.3f}",
            "Annualized Alpha": f"{ab_dyn_mvo_risk['ann_alpha']:.2%}",
            "Beta vs SOXX": f"{ab_dyn_mvo_risk['beta']:.3f}",
            "t-stat(Alpha)": f"{ab_dyn_mvo_risk['t_alpha']:.2f}"
        },
        "SOXX Benchmark": {
            "Annualized Return": f"{metrics_bench['annualized_return']:.2%}",
            "Annualized Volatility": f"{metrics_bench['annualized_vol']:.2%}",
            "Max Drawdown": f"{metrics_bench['max_drawdown']:.2%}",
            "Sharpe Ratio": f"{metrics_bench['sharpe_ratio']:.3f}",
            "Calmar Ratio": f"{metrics_bench['calmar_ratio']:.3f}",
            "Annualized Alpha": "0.00%",
            "Beta vs SOXX": "1.000",
            "t-stat(Alpha)": "n/a"
        }
    })
    
    print(metrics_compare.to_string())
    print("=" * 100)
    print("Backtest & Analysis Complete.")

if __name__ == "__main__":
    main()
