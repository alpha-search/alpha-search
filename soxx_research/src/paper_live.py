"""
Stage 4 (live) — paper_live.py
==============================
Pull the latest SOXX (+ NVDA/SMH) 5-minute bars and print the CURRENT signal for
the finalist strategies, so you can watch them during market hours.

Run on a machine with Yahoo access (e.g. your phone terminal):
    python3 src/paper_live.py

It reads results/leaderboard.csv to pick the top-2 by out-of-sample Sharpe
(falls back to gap_fade_h6 / tod_first_hour_L). It does NOT place orders — it
prints the position each strategy would want to hold into the next bar, plus a
vol-targeted share count for a $100k account.

NOTE: the research leaderboard was produced on SYNTHETIC data in a locked-down
sandbox. Re-run the full pipeline here first (python3 src/run_stage3.py) to get a
leaderboard from real bars before trusting the finalist selection.
"""
from __future__ import annotations

import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from data import load, TICKERS                    # noqa: E402
from signals import build_registry                # noqa: E402
from backtest import BARS_PER_YEAR                 # noqa: E402

RESULTS = os.path.join(os.path.dirname(HERE), "results")
DEFAULT_FINALISTS = ["gap_fade_h6", "tod_first_hour_L"]
START_EQUITY = 100_000.0
TARGET_ANN_VOL = 0.10
MAX_LEVERAGE = 1.5
VOL_LOOKBACK = 78


def _finalists() -> list[str]:
    p = os.path.join(RESULTS, "leaderboard.csv")
    if os.path.exists(p):
        lb = pd.read_csv(p)
        return lb.sort_values("sharpe_oos", ascending=False).head(2)["strategy"].tolist()
    return DEFAULT_FINALISTS


def _pull_latest() -> dict[str, pd.DataFrame]:
    """Force a fresh 5m pull (last 5 trading days is enough for the signals)."""
    return load("5m", days=5, force=True)


def main():
    print("[live] pulling latest 5m bars ...")
    data = _pull_latest()
    px = data["SOXX"]
    if px.empty:
        print("[live] no data returned — check network / Yahoo access."); return
    refs = {"NVDA": data.get("NVDA"), "SMH": data.get("SMH")}
    reg = build_registry(px, {k: v for k, v in refs.items() if v is not None})

    last_ts = px.index[-1]
    last_close = float(px["Close"].iloc[-1])
    # current annualized vol for sizing
    br = px["Close"].pct_change()
    first = px.index.normalize().to_series(index=px.index).ne(
        px.index.normalize().to_series(index=px.index).shift())
    br[first.values] = np.nan
    ann_vol = float(br.rolling(VOL_LOOKBACK, min_periods=20).std().iloc[-1] * np.sqrt(BARS_PER_YEAR))

    print(f"[live] SOXX last bar {last_ts}  close={last_close:.2f}  "
          f"est. ann.vol={ann_vol:.1%}")
    print(f"[live] finalist signals (position to hold INTO the next bar):")
    for name in _finalists():
        if name not in reg:
            print(f"   {name:20s} : (not in registry)"); continue
        sig = int(reg[name].iloc[-1])
        word = {1: "LONG ", -1: "SHORT", 0: "FLAT "}[sig]
        if sig != 0 and ann_vol > 0:
            lev = min(MAX_LEVERAGE, TARGET_ANN_VOL / ann_vol)
            shares = sig * lev * START_EQUITY / last_close
            size = f"{lev:.2f}x  ~{abs(shares):.0f} sh (${abs(shares)*last_close:,.0f})"
        else:
            size = "-"
        print(f"   {name:20s} : {word}   {size}")
    print("[live] (paper only — no orders placed)")


if __name__ == "__main__":
    main()
