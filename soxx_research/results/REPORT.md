# SOXX Intraday Research — Honest Verdict

> ## ⚠️ DATA PROVENANCE — READ FIRST
> This run was executed in a sandbox whose network policy **blocks all
> market-data hosts** (Yahoo, Stooq, AlphaVantage, Polygon, IEX, Nasdaq — all 403).
> Live SOXX bars could not be fetched here, so the pipeline ran on a
> **clearly-labeled SYNTHETIC dataset** generated as a near-random-walk.
>
> **Nothing in this report is evidence of a real market edge.** The synthetic
> series has, by construction, no exploitable structure. The value here is that
> the *code* is correct and ready: run `python3 src/run_stage3.py` on your phone
> (where Yahoo is reachable) to regenerate every table below from real data.

## 1. What was tested

- **Instrument:** SOXX 5-minute bars (SMH & NVDA pulled as correlated references).
- **Sample:** 44 trading sessions, 3,432 bars (~60 calendar days).
- **Data source:** `SYNTHETIC`.
- **Configurations tested:** **30** across 7 signal families
  (TS-momentum, opening-range breakout, VWAP-z / Bollinger / RSI(2) mean-reversion,
  vol-regime breakout, time-of-day, cross-asset lead-lag, gap continuation/fade).
- **Backtest:** vectorized, **next-bar execution** (no look-ahead — asserted in
  `src/test_backtest.py`), 1 bp commission + 2 bp slippage per side, flat at EOD.
- **Split:** train on first 70% of sessions, hold out the last 30%
  (cut at **2026-07-20**).

## 2. Leaderboard — in-sample vs out-of-sample (top 12 by OOS Sharpe)

| strategy | Sharpe IS | Sharpe OOS | Sharpe (no cost) | cost drag | max DD | hit | trades/day |
|---|---|---|---|---|---|---|---|
| gap_fade_h6 | 0.07 | 10.70 | 4.97 | 1.27 | -0.03 | 0.55 | 0.91 |
| tod_first_hour_L | 1.70 | 6.52 | 4.28 | 1.03 | -0.04 | 0.57 | 1.00 |
| tod_last_hour_S | 1.64 | 6.49 | 4.10 | 1.03 | -0.04 | 0.66 | 1.00 |
| tsmom_n24 | -1.70 | 4.88 | 3.88 | 3.53 | -0.08 | 0.32 | 5.25 |
| gap_fade_h3 | -3.22 | 4.71 | 1.38 | 1.79 | -0.04 | 0.53 | 0.91 |
| volregime_high_l12 | -4.49 | 4.70 | 2.06 | 3.89 | -0.07 | 0.40 | 2.84 |
| tod_lunch_L | -4.83 | 1.69 | -1.24 | 1.59 | -0.08 | 0.48 | 1.00 |
| tsmom_n12 | -5.44 | 0.76 | 2.16 | 5.69 | -0.21 | 0.28 | 9.39 |
| vwapz_w24_z2.5 | -1.46 | 0.06 | 0.41 | 1.42 | -0.04 | 0.56 | 0.89 |
| orb_30m | -1.76 | -1.15 | -0.67 | 0.91 | -0.15 | 0.44 | 1.45 |
| orb_15m | -2.13 | -1.41 | -0.93 | 0.98 | -0.16 | 0.41 | 1.73 |
| vwapz_w48_z2.0 | 5.30 | -3.26 | 4.00 | 1.41 | -0.05 | 0.71 | 1.18 |

*Full table: `results/leaderboard.csv` (all 30 configs).*
*Sharpe here is annualized from 5-minute bars; for sparse, low-turnover strategies
this **overstates** Sharpe (many flat bars shrink the denominator) — treat the
absolute numbers with suspicion and compare strategies to each other, not to a
daily-Sharpe intuition.*

## 3. Did anything survive costs?

- **Survived costs (full-sample Sharpe still > 0 after 3 bp/side):**
  4 of 30 configs also kept a positive OOS Sharpe.
- **Killed by costs alone** (positive gross Sharpe > 0.5 flipped ≤ 0 net):
  **6** configs — gap_fade_h3, volregime_high_l12, tsmom_n12, volregime_low_l6, tod_lunch_S, boll_w20_k2.0.
  These are the high-turnover strategies (short-N momentum, RSI(2)); slippage eats them.
- The `cost drag` column shows how much annualized Sharpe each side of costs removes —
  for the fastest strategies it is the difference between "looks great" and "loses money".

## 4. Is the winner real, or luck?

The out-of-sample winner is **`gap_fade_h6`** (IS Sharpe 0.07,
OOS Sharpe 10.70).

Three independent checks — all point the same way:

1. **In-sample vs out-of-sample divergence.** The winner's Sharpe moved by
   **10.64** between train and holdout (IS 0.07
   → OOS 10.70). A *real* edge shows up in **both** halves.
   A strategy that is flat/negative in-sample and only shines out-of-sample is the
   textbook signature of a lucky draw in a small holdout, not a discovered edge.

2. **Deflated Sharpe Ratio (Bailey & López de Prado).** Correcting for the
   30 trials, the **expected maximum Sharpe from luck alone is
   12.36** (annualized). The winner does not
   clear that bar, so the deflated-Sharpe probability that its skill is real is
   **0.000** — i.e. ≈ 0. When you test dozens of
   strategies on a short sample, *some* will post a high Sharpe by chance; this one
   is within what chance produces.

3. **Permutation test.** Shuffling the bar returns 500× and re-scoring puts the
   winner at the 100th percentile of the null
   (p = 0.004). **Caveat that matters:** the winner was
   *selected* by OOS Sharpe and then tested on the *same* OOS window, so this p-value
   is optimistically biased (selection + evaluation on one sample). Taken honestly it
   is **not** independent evidence of skill.

## 5. Verdict

**This is noise.** Because the data is synthetic, that conclusion is guaranteed a priori — there is no edge to find. But the statistics would say the same thing about *real* SOXX data at
this sample size: with 30 configurations and only
44 sessions, the best Sharpe you observe is consistent with random
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
