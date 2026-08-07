"""
No-lookahead and correctness tests for the backtester.
Run: python3 src/test_backtest.py   (plain asserts, no pytest needed)
"""
import numpy as np
import pandas as pd

from backtest import (bar_returns, run_backtest, enforce_eod_flat,
                      COST_PER_SIDE, metrics)


def _toy(n_days=3, n_bars=6, seed=0):
    rng = np.random.default_rng(seed)
    idx = []
    for d in range(n_days):
        base = pd.Timestamp("2026-01-05", tz="America/New_York") + pd.Timedelta(days=d)
        base = base + pd.Timedelta(hours=9, minutes=30)
        idx += [base + pd.Timedelta(minutes=5 * k) for k in range(n_bars)]
    idx = pd.DatetimeIndex(idx, name="datetime")
    close = 100 * np.exp(np.cumsum(rng.standard_normal(len(idx)) * 0.002))
    px = pd.DataFrame({"Open": close, "High": close * 1.001, "Low": close * 0.999,
                       "Close": close, "Volume": 1000}, index=idx)
    return px


def test_next_bar_execution_no_lookahead():
    """
    The P&L at bar t must depend only on the position decided at t-1.
    Concretely: perturbing a FUTURE return must not change P&L in the PAST.
    """
    px = _toy()
    tgt = pd.Series(np.sign(np.sin(np.arange(len(px)))), index=px.index)
    r1 = run_backtest(tgt, px, costs=False)

    px2 = px.copy()
    px2.iloc[-1, px2.columns.get_loc("Close")] *= 1.05     # shock only the LAST bar
    r2 = run_backtest(tgt, px2, costs=False)

    # every bar except possibly the last must be identical -> no look-ahead
    assert np.allclose(r1.iloc[:-1].values, r2.iloc[:-1].values), "look-ahead detected!"
    print("  ok: perturbing the future leaves the past P&L unchanged")


def test_position_is_shifted():
    """P&L at t uses target at t-1, not t."""
    px = _toy(n_days=1, n_bars=6)
    tgt = pd.Series([0, 1, 0, 0, 0, 0], index=px.index, dtype=float)
    r = run_backtest(tgt, px, costs=False)
    br = bar_returns(px)
    # long established at bar1 -> earns bar2's return
    assert abs(r.iloc[2] - br.iloc[2]) < 1e-12
    assert abs(r.iloc[1]) < 1e-12
    print("  ok: return at t equals position[t-1] * barreturn[t]")


def test_eod_flat_no_overnight():
    """No position may earn the first (overnight-open) bar of any day."""
    px = _toy(n_days=3, n_bars=6)
    tgt = pd.Series(1.0, index=px.index)                   # always long
    r = run_backtest(tgt, px, costs=False)
    br = bar_returns(px)
    firsts = px.index.normalize().to_series(index=px.index).ne(
        px.index.normalize().to_series(index=px.index).shift())
    assert (br[firsts.values] == 0).all(), "overnight return leaked into a bar"
    # last bar of each day is forced flat -> target 0 there
    t = enforce_eod_flat(tgt, px)
    lasts = px.index.normalize().to_series(index=px.index).ne(
        px.index.normalize().to_series(index=px.index).shift(-1))
    assert (t[lasts.values] == 0).all()
    print("  ok: flat into the open and forced flat at EOD")


def test_costs_reduce_return():
    px = _toy()
    tgt = pd.Series(np.sign(np.sin(np.arange(len(px)))), index=px.index)
    gross = run_backtest(tgt, px, costs=False).sum()
    net = run_backtest(tgt, px, costs=True).sum()
    assert net < gross, "costs did not reduce return"
    print(f"  ok: costs reduce return (gross={gross:.5f} net={net:.5f})")


def test_flat_signal_zero_pnl():
    px = _toy()
    tgt = pd.Series(0.0, index=px.index)
    assert abs(run_backtest(tgt, px, costs=True).sum()) < 1e-12
    print("  ok: flat signal earns exactly zero")


if __name__ == "__main__":
    print("[tests] no-lookahead & backtest correctness")
    test_next_bar_execution_no_lookahead()
    test_position_is_shifted()
    test_eod_flat_no_overnight()
    test_costs_reduce_return()
    test_flat_signal_zero_pnl()
    print("[tests] ALL PASSED")
