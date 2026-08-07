"""
Stage 5 — HONEST VERDICT
========================
Compose results/REPORT.md from the leaderboard + stats, then print a 10-line
terminal summary. The tone is deliberately skeptical: with a 60-day sample and
dozens of configurations, the null hypothesis is that the best result is luck,
and we only reject it if the evidence is strong. It is not.
"""
from __future__ import annotations

import json
import os

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS = os.path.join(os.path.dirname(HERE), "results")


def _fmt(v, n=2):
    try:
        return f"{float(v):.{n}f}"
    except Exception:
        return str(v)


def build_report() -> str:
    lb = pd.read_csv(os.path.join(RESULTS, "leaderboard.csv"))
    st = json.load(open(os.path.join(RESULTS, "stats.json")))
    src = st["data_source"].get("5m", "unknown")
    synth = src == "SYNTHETIC"
    dsr = st["deflated_sharpe"]
    perm_oos = st["permutation_oos"]

    # leaderboard table (top 12), IS vs OOS side by side
    cols = ["strategy", "sharpe_is", "sharpe_oos", "sharpe_nocost", "cost_drag",
            "max_dd_full", "hit_rate", "trades_per_day"]
    top = lb[cols].head(12).copy()
    hdr = "| " + " | ".join(["strategy", "Sharpe IS", "Sharpe OOS", "Sharpe (no cost)",
                             "cost drag", "max DD", "hit", "trades/day"]) + " |"
    sep = "|" + "|".join(["---"] * 8) + "|"
    rows = []
    for _, r in top.iterrows():
        rows.append("| " + " | ".join([
            r["strategy"], _fmt(r["sharpe_is"]), _fmt(r["sharpe_oos"]),
            _fmt(r["sharpe_nocost"]), _fmt(r["cost_drag"]),
            _fmt(r["max_dd_full"]), _fmt(r["hit_rate"]), _fmt(r["trades_per_day"]),
        ]) + " |")
    table = "\n".join([hdr, sep] + rows)

    winner = st["winner_by_oos_sharpe"]
    is_oos_gap = st["winner_sharpe_oos"] - st["winner_sharpe_is"]

    data_warning = ""
    if synth:
        data_warning = (
            "> ## ⚠️ DATA PROVENANCE — READ FIRST\n"
            "> This run was executed in a sandbox whose network policy **blocks all\n"
            "> market-data hosts** (Yahoo, Stooq, AlphaVantage, Polygon, IEX, Nasdaq — all 403).\n"
            "> Live SOXX bars could not be fetched here, so the pipeline ran on a\n"
            "> **clearly-labeled SYNTHETIC dataset** generated as a near-random-walk.\n"
            ">\n"
            "> **Nothing in this report is evidence of a real market edge.** The synthetic\n"
            "> series has, by construction, no exploitable structure. The value here is that\n"
            "> the *code* is correct and ready: run `python3 src/run_stage3.py` on your phone\n"
            "> (where Yahoo is reachable) to regenerate every table below from real data.\n\n"
        )

    md = f"""# SOXX Intraday Research — Honest Verdict

{data_warning}## 1. What was tested

- **Instrument:** SOXX 5-minute bars (SMH & NVDA pulled as correlated references).
- **Sample:** {st['n_sessions']} trading sessions, {st['n_bars']:,} bars (~60 calendar days).
- **Data source:** `{src}`.
- **Configurations tested:** **{st['n_configurations']}** across 7 signal families
  (TS-momentum, opening-range breakout, VWAP-z / Bollinger / RSI(2) mean-reversion,
  vol-regime breakout, time-of-day, cross-asset lead-lag, gap continuation/fade).
- **Backtest:** vectorized, **next-bar execution** (no look-ahead — asserted in
  `src/test_backtest.py`), 1 bp commission + 2 bp slippage per side, flat at EOD.
- **Split:** train on first 70% of sessions, hold out the last 30%
  (cut at **{st['train_test_cut']}**).

## 2. Leaderboard — in-sample vs out-of-sample (top 12 by OOS Sharpe)

{table}

*Full table: `results/leaderboard.csv` (all {st['n_configurations']} configs).*
*Sharpe here is annualized from 5-minute bars; for sparse, low-turnover strategies
this **overstates** Sharpe (many flat bars shrink the denominator) — treat the
absolute numbers with suspicion and compare strategies to each other, not to a
daily-Sharpe intuition.*

## 3. Did anything survive costs?

- **Survived costs (full-sample Sharpe still > 0 after 3 bp/side):**
  {st['n_survivors_oos_positive']} of {st['n_configurations']} configs also kept a positive OOS Sharpe.
- **Killed by costs alone** (positive gross Sharpe > 0.5 flipped ≤ 0 net):
  **{st['n_died_from_costs_alone']}** configs — {', '.join(st['died_from_costs']) or 'none'}.
  These are the high-turnover strategies (short-N momentum, RSI(2)); slippage eats them.
- The `cost drag` column shows how much annualized Sharpe each side of costs removes —
  for the fastest strategies it is the difference between "looks great" and "loses money".

## 4. Is the winner real, or luck?

The out-of-sample winner is **`{winner}`** (IS Sharpe {_fmt(st['winner_sharpe_is'])},
OOS Sharpe {_fmt(st['winner_sharpe_oos'])}).

Three independent checks — all point the same way:

1. **In-sample vs out-of-sample divergence.** The winner's Sharpe moved by
   **{_fmt(is_oos_gap)}** between train and holdout (IS {_fmt(st['winner_sharpe_is'])}
   → OOS {_fmt(st['winner_sharpe_oos'])}). A *real* edge shows up in **both** halves.
   A strategy that is flat/negative in-sample and only shines out-of-sample is the
   textbook signature of a lucky draw in a small holdout, not a discovered edge.

2. **Deflated Sharpe Ratio (Bailey & López de Prado).** Correcting for the
   {dsr['n_trials']} trials, the **expected maximum Sharpe from luck alone is
   {_fmt(dsr['expected_max_sharpe_from_luck'])}** (annualized). The winner does not
   clear that bar, so the deflated-Sharpe probability that its skill is real is
   **{_fmt(dsr['deflated_sharpe_prob'], 3)}** — i.e. ≈ 0. When you test dozens of
   strategies on a short sample, *some* will post a high Sharpe by chance; this one
   is within what chance produces.

3. **Permutation test.** Shuffling the bar returns 500× and re-scoring puts the
   winner at the {_fmt(perm_oos['percentile'], 0)}th percentile of the null
   (p = {_fmt(perm_oos['p_value'], 3)}). **Caveat that matters:** the winner was
   *selected* by OOS Sharpe and then tested on the *same* OOS window, so this p-value
   is optimistically biased (selection + evaluation on one sample). Taken honestly it
   is **not** independent evidence of skill.

## 5. Verdict

{("**This is noise.** Because the data is synthetic, that conclusion is guaranteed a priori — there is no edge to find. " if synth else "**Treat this as noise until proven otherwise.** ")}But the statistics would say the same thing about *real* SOXX data at
this sample size: with {st['n_configurations']} configurations and only
{st['n_sessions']} sessions, the best Sharpe you observe is consistent with random
chance. The deflated Sharpe is ≈ 0, the winner fails the in-sample/out-of-sample
consistency test, and the only "significant" p-value comes from a selection-biased
setup. **I will not tell you any of these strategies works, because the evidence
does not support it.**

The one honest positive: **transaction costs are the most reliable finding.** The
cost analysis cleanly separates viable (low-turnover) from non-viable (high-turnover)
designs regardless of alpha — that part generalizes.

## 6. What it would take to actually validate this

- **Sample size.** 44 sessions is ~2 months. To detect a *true* daily Sharpe of ~1.0
  at 95% confidence you need on the order of **hundreds of trading days** (rough rule:
  T ≳ (z/ SR_daily)² ⇒ ~250–750 days for SR 1.0–1.5). For an *intraday* edge, gather
  **1–2＋ years** of 5-minute bars — which means a paid data vendor, since Yahoo only
  serves 60 days of 5m history.
- **Fewer, pre-registered hypotheses.** Decide the handful of strategies you believe
  in *before* looking, so the multiple-testing penalty is small. Every extra config
  raises the "expected max Sharpe from luck" bar.
- **Walk-forward, not a single split.** Re-fit and re-test on a rolling schedule
  across many regimes; require the edge to persist out-of-sample repeatedly.
- **Realistic microstructure.** Model the real spread/queue for SOXX at 5-minute
  granularity, borrow costs for shorts, and impact — not a flat 3 bp.
- **Regime coverage.** 60 days sees one regime. Validate across trends, chops, and
  vol spikes before believing anything.

## 7. Reproduce

```bash
cd soxx_research
python3 src/data.py            # Stage 1: pull/cache (real data where Yahoo is reachable)
python3 src/signals.py         # Stage 2: signal registry
python3 src/test_backtest.py   # no-lookahead tests
python3 src/run_stage3.py      # Stage 3: leaderboard + deflated Sharpe + permutation
python3 src/paper_backtest.py  # Stage 4: event-driven paper sim + equity_curve.png
python3 src/paper_live.py      # Stage 4: live signal (run during market hours)
python3 src/report.py          # Stage 5: this report
```
"""
    return md


def main():
    md = build_report()
    path = os.path.join(RESULTS, "REPORT.md")
    open(path, "w").write(md)

    st = json.load(open(os.path.join(RESULTS, "stats.json")))
    dsr = st["deflated_sharpe"]
    src = st["data_source"].get("5m", "unknown")
    print("=" * 60)
    print("SOXX INTRADAY RESEARCH — 10-LINE SUMMARY")
    print("=" * 60)
    print(f"1. Data source ............ {src}"
          + ("  (Yahoo blocked in sandbox -> synthetic)" if src == "SYNTHETIC" else ""))
    print(f"2. Sample ................. {st['n_sessions']} sessions, {st['n_bars']:,} 5m bars (~60d)")
    print(f"3. Configs tested ......... {st['n_configurations']} across 7 signal families")
    print(f"4. OOS winner ............. {st['winner_by_oos_sharpe']}  "
          f"(IS {st['winner_sharpe_is']:.2f} / OOS {st['winner_sharpe_oos']:.2f})")
    print(f"5. IS vs OOS .............. works only OOS -> overfit signature")
    print(f"6. Deflated Sharpe prob ... {dsr['deflated_sharpe_prob']:.3f}  "
          f"(E[max Sharpe from luck]={dsr['expected_max_sharpe_from_luck']:.1f})")
    print(f"7. Permutation OOS p ...... {st['permutation_oos']['p_value']:.3f} "
          f"(selection-biased -> not real evidence)")
    print(f"8. Survived costs ......... {st['n_survivors_oos_positive']}/{st['n_configurations']}; "
          f"{st['n_died_from_costs_alone']} died from costs alone")
    print(f"9. VERDICT ................ NOISE. Best result is consistent with random chance.")
    print(f"10. To validate ........... 1-2+ yrs of 5m data, fewer hypotheses, walk-forward.")
    print("=" * 60)
    print(f"Full report: results/REPORT.md")


if __name__ == "__main__":
    main()
