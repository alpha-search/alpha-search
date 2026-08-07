"""
Stage 3 driver — build the leaderboard and the honesty statistics, then persist:
  results/leaderboard.csv     (sorted by out-of-sample Sharpe)
  results/stats.json          (deflated Sharpe + permutation test + metadata)
"""
from __future__ import annotations

import json
import os

import numpy as np
import pandas as pd

from data import load
from signals import build_registry
from backtest import (build_leaderboard, deflated_sharpe, permutation_test,
                      run_backtest, split_index, metrics, BARS_PER_YEAR)

HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS = os.path.join(os.path.dirname(HERE), "results")
os.makedirs(RESULTS, exist_ok=True)


def main():
    data = load("5m", 60)
    px = data["SOXX"]
    refs = {"NVDA": data["NVDA"], "SMH": data["SMH"]}
    prov = json.load(open(os.path.join(os.path.dirname(HERE), "data", "_provenance.json")))

    reg = build_registry(px, refs)
    lb, cut = build_leaderboard(reg, px)
    lb.to_csv(os.path.join(RESULTS, "leaderboard.csv"), index=False)

    # ---- multiple-testing statistics on the OOS winner --------------------- #
    winner = lb.iloc[0]["strategy"]
    all_full_sharpes = lb["sharpe_full"].to_numpy()
    is_mask, oos_mask, _ = split_index(px, 0.70)

    winner_ret_full = run_backtest(reg[winner], px, costs=True)
    winner_ret_oos = run_backtest(reg[winner][oos_mask], px[oos_mask], costs=True)

    dsr = deflated_sharpe(winner_ret_full, all_full_sharpes)
    perm = permutation_test(reg[winner], px, n_iter=500)
    perm_oos = permutation_test(reg[winner][oos_mask], px[oos_mask], n_iter=500)

    # how many strategies "survive": positive OOS Sharpe AND beat cost
    survivors = lb[(lb["sharpe_oos"] > 0) & (lb["sharpe_full"] > 0)]
    died_from_costs = lb[(lb["sharpe_nocost"] > 0.5) & (lb["sharpe_full"] <= 0)]

    stats = dict(
        data_source=prov,
        n_configurations=int(len(reg)),
        n_sessions=int(px.index.normalize().nunique()),
        n_bars=int(len(px)),
        train_test_cut=str(cut.date()),
        winner_by_oos_sharpe=winner,
        winner_sharpe_is=float(lb.iloc[0]["sharpe_is"]),
        winner_sharpe_oos=float(lb.iloc[0]["sharpe_oos"]),
        winner_sharpe_full=float(lb.iloc[0]["sharpe_full"]),
        deflated_sharpe=dsr,
        permutation_full=perm,
        permutation_oos=perm_oos,
        n_survivors_oos_positive=int(len(survivors)),
        survivors=survivors["strategy"].tolist()[:10],
        n_died_from_costs_alone=int(len(died_from_costs)),
        died_from_costs=died_from_costs["strategy"].tolist()[:10],
        best_oos_sharpe=float(lb["sharpe_oos"].max()),
        median_oos_sharpe=float(lb["sharpe_oos"].median()),
    )
    json.dump(stats, open(os.path.join(RESULTS, "stats.json"), "w"), indent=2, default=str)

    # ---- terminal progress ------------------------------------------------- #
    print(f"[stage3] tested {len(reg)} configs on {stats['n_sessions']} sessions "
          f"({prov.get('5m','?')} data)")
    print(f"[stage3] OOS winner: {winner}  IS={stats['winner_sharpe_is']:.2f} "
          f"OOS={stats['winner_sharpe_oos']:.2f}")
    print(f"[stage3] deflated-Sharpe prob (winner is real): "
          f"{dsr['deflated_sharpe_prob']:.3f}  | E[max Sharpe from luck]="
          f"{dsr['expected_max_sharpe_from_luck']:.2f}")
    print(f"[stage3] permutation OOS p-value: {perm_oos['p_value']:.3f} "
          f"(winner at {perm_oos['percentile']:.0f}th pct of null)")
    print(f"[stage3] survivors (OOS>0 & full>0): {len(survivors)}/{len(reg)}; "
          f"died from costs alone: {len(died_from_costs)}")
    print(f"[stage3] leaderboard -> results/leaderboard.csv")
    print("\n[stage3] top 8 by OOS Sharpe:")
    cols = ["strategy", "sharpe_is", "sharpe_oos", "sharpe_nocost", "cost_drag",
            "max_dd_full", "trades_per_day"]
    with pd.option_context("display.width", 200, "display.max_columns", 20):
        print(lb[cols].head(8).to_string(index=False,
              formatters={c: (lambda v: f"{v:.2f}") for c in cols if c != "strategy"}))
    return lb, stats


if __name__ == "__main__":
    main()
