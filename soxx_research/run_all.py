"""
End-to-end driver: Stage 1 -> 5. Run from the soxx_research/ directory:
    python3 run_all.py
Each stage prints a short progress line. Safe to re-run (data is cached).
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))

import data          # noqa: E402
import test_backtest # noqa: E402
import run_stage3    # noqa: E402
import paper_backtest# noqa: E402
import report        # noqa: E402


def main():
    print("\n=== STAGE 1: DATA ===")
    data.load("5m", 60)
    data.load("1m", 7)

    print("\n=== TESTS: no-lookahead ===")
    test_backtest.test_next_bar_execution_no_lookahead()
    test_backtest.test_position_is_shifted()
    test_backtest.test_eod_flat_no_overnight()
    test_backtest.test_costs_reduce_return()
    test_backtest.test_flat_signal_zero_pnl()

    print("\n=== STAGE 3: BACKTEST + STATS ===")
    run_stage3.main()

    print("\n=== STAGE 4: PAPER TRADING ===")
    paper_backtest.main()

    print("\n=== STAGE 5: HONEST VERDICT ===")
    report.main()


if __name__ == "__main__":
    main()
