"""
Stage 4 — PAPER TRADING (event-driven)
======================================
A bar-by-bar, event-driven simulation (NOT vectorized) of the top-2 out-of-sample
strategies over the hold-out window, on a $100k notional account.

Sizing: volatility targeting to 10% annualized. Each bar we estimate the asset's
recent annualized volatility and scale exposure so the *position's* annualized
vol ≈ 10% of equity, capped at 1.5x gross leverage. Execution is next-bar at the
open; 3 bp per side is charged on traded notional; positions are closed at EOD.

Outputs:
  results/paper_trades.csv   per-trade log
  results/equity_curve.png   equity curve for both finalists
  results/paper_daily.csv    daily P&L
"""
from __future__ import annotations

import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from data import load
from signals import build_registry
from backtest import build_leaderboard, split_index, COST_PER_SIDE, BARS_PER_YEAR

HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS = os.path.join(os.path.dirname(HERE), "results")
os.makedirs(RESULTS, exist_ok=True)

START_EQUITY = 100_000.0
TARGET_ANN_VOL = 0.10
MAX_LEVERAGE = 1.5
VOL_LOOKBACK = 78                 # ~1 session of 5m bars for vol estimate


def simulate(name: str, target: pd.Series, px: pd.DataFrame) -> dict:
    """Event-driven bar loop. Returns equity series, trade log, daily P&L."""
    idx = px.index
    close = px["Close"].to_numpy()
    openp = px["Open"].to_numpy()
    day = idx.normalize().to_numpy()
    tgt = target.reindex(idx).fillna(0.0).clip(-1, 1).to_numpy()

    # rolling annualized vol estimate (causal)
    barret = pd.Series(close, index=idx).pct_change()
    barret[np.r_[True, day[1:] != day[:-1]]] = np.nan            # drop overnight
    ann_vol = (barret.rolling(VOL_LOOKBACK, min_periods=20).std()
               * np.sqrt(BARS_PER_YEAR)).to_numpy()

    equity = START_EQUITY
    shares = 0.0                 # signed share count currently held
    entry_price = np.nan
    entry_time = None
    entry_dir = 0
    entry_i = 0

    eq_curve = np.empty(len(idx))
    trades = []

    for i in range(len(idx)):
        new_day = (i == 0) or (day[i] != day[i - 1])
        last_bar = (i == len(idx) - 1) or (day[i] != day[i + 1])

        # ---- mark-to-market the existing position on this bar --------------- #
        if i > 0 and not new_day and shares != 0:
            equity += shares * (close[i] - close[i - 1])
        eq_curve[i] = equity

        if i + 1 >= len(idx):
            break

        # desired direction for the NEXT bar, decided on info up to bar i
        desired_dir = 0 if last_bar else int(tgt[i])           # flat into EOD
        av = ann_vol[i]
        if desired_dir == 0 or not np.isfinite(av) or av <= 0:
            desired_shares = 0.0
        else:                                                  # vol targeting
            lev = min(MAX_LEVERAGE, TARGET_ANN_VOL / av)
            desired_shares = desired_dir * lev * equity / close[i]

        # ---- execute the change at the NEXT bar's open --------------------- #
        if abs(desired_shares - shares) > 1e-9:
            exec_price = openp[i + 1]
            equity -= abs(desired_shares - shares) * exec_price * COST_PER_SIDE
            closing = shares != 0 and (desired_shares == 0 or np.sign(desired_shares) != np.sign(shares))
            if closing:
                trades.append(dict(
                    strategy=name, entry_time=entry_time, exit_time=idx[i + 1],
                    direction="long" if entry_dir > 0 else "short",
                    entry_price=round(entry_price, 4), exit_price=round(exec_price, 4),
                    shares=round(shares, 2),
                    pnl=round(shares * (exec_price - entry_price), 2),
                    hold_bars=int((i + 1) - entry_i),
                ))
            opening = desired_shares != 0 and (shares == 0 or np.sign(desired_shares) != np.sign(shares))
            if opening:
                entry_price, entry_time, entry_dir, entry_i = exec_price, idx[i + 1], int(np.sign(desired_shares)), i + 1
            shares = desired_shares

    eq = pd.Series(eq_curve, index=idx, name=name)
    tl = pd.DataFrame(trades)
    daily = eq.groupby(idx.normalize()).last().diff().fillna(eq.iloc[0] - START_EQUITY)
    daily.name = name
    return dict(equity=eq, trades=tl, daily=daily)


def main():
    data = load("5m", 60)
    px = data["SOXX"]
    refs = {"NVDA": data["NVDA"], "SMH": data["SMH"]}
    reg = build_registry(px, refs)
    lb, _ = build_leaderboard(reg, px)
    _, oos_mask, cut = split_index(px, 0.70)
    px_oos = px[oos_mask]

    top2 = lb.head(2)["strategy"].tolist()
    print(f"[stage4] event-driven paper sim over hold-out (from {cut.date()}), "
          f"${START_EQUITY:,.0f}, vol-target {TARGET_ANN_VOL:.0%}")
    print(f"[stage4] finalists (top-2 OOS Sharpe): {top2}")

    all_trades, curves, dailies = [], [], []
    for name in top2:
        res = simulate(name, reg[name][oos_mask], px_oos)
        curves.append(res["equity"])
        dailies.append(res["daily"])
        if not res["trades"].empty:
            all_trades.append(res["trades"])
        final = res["equity"].iloc[-1]
        ntr = len(res["trades"])
        ret = final / START_EQUITY - 1
        print(f"[stage4]   {name:20s} final=${final:,.0f}  ret={ret:+.2%}  trades={ntr}")

    trades_df = pd.concat(all_trades, ignore_index=True) if all_trades else pd.DataFrame(
        columns=["strategy", "entry_time", "exit_time", "direction", "pnl"])
    trades_df.to_csv(os.path.join(RESULTS, "paper_trades.csv"), index=False)
    daily_df = pd.concat(dailies, axis=1)
    daily_df.to_csv(os.path.join(RESULTS, "paper_daily.csv"))

    # ---- equity curve PNG -------------------------------------------------- #
    fig, ax = plt.subplots(figsize=(9, 4.5))
    for eq in curves:
        ax.plot(eq.index, eq.values, label=eq.name, lw=1.3)
    ax.axhline(START_EQUITY, color="k", lw=0.6, ls="--", alpha=0.5)
    ax.set_title(f"SOXX intraday paper trading — hold-out (SYNTHETIC data)\n"
                 f"$100k, vol-targeted 10% ann.", fontsize=10)
    ax.set_ylabel("Equity ($)")
    ax.legend(fontsize=8)
    ax.grid(alpha=0.25)
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(os.path.join(RESULTS, "equity_curve.png"), dpi=110)
    plt.close(fig)

    print(f"[stage4] wrote results/paper_trades.csv ({len(trades_df)} trades), "
          f"results/equity_curve.png, results/paper_daily.csv")
    return trades_df, curves


if __name__ == "__main__":
    main()
