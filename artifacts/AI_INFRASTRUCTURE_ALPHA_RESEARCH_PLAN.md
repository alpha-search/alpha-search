# AI Infrastructure & Semiconductor Alpha Research Plan

**Document Status:** Pre-registered. Parameters and success criteria recorded
before any backtest results are observed. No post-hoc tuning is permitted.

**Last Updated:** 2026-05-29

---

## 1. Research Objective

Determine whether systematic quantitative strategies applied to the US AI
infrastructure and semiconductor equity universe generate statistically
significant risk-adjusted alpha after realistic transaction costs, relative to
sector benchmarks (SOXX, SMH) and broad market benchmarks (QQQ, SPY).

Four distinct strategy families are evaluated — cross-sectional momentum, trend
following, mean reversion, and Donchian breakout — using a single pre-registered
parameter set per family. The primary deliverable is a research report with net
Sharpe ratios, alpha/beta decomposition, in-sample/out-of-sample stability, and
a mechanical pass/fail verdict. Results are reported as-is regardless of outcome.

---

## 2. Hypothesis (Pre-Registered)

**H1 — Cross-Sectional Momentum (primary):**
AI-infrastructure and semiconductor stocks with the strongest trailing 12-1 month
returns continue to outperform the bottom tercile over the subsequent month. A
long/short dollar-neutral tercile portfolio generates a positive net Sharpe ratio
greater than 1.0 with an alpha t-statistic greater than 2.0.

**H2 — Trend Following:**
Stocks in the universe that trade above their 50-, 100-, and 200-day simple
moving averages exhibit positive momentum persistence. An equal-weight long-only
portfolio of qualifying names generates a net Sharpe ratio greater than the SOXX
benchmark over the same period.

**H3 — Mean Reversion:**
Stocks in the universe that deviate 2 standard deviations or more below their
20-day rolling mean tend to revert toward that mean within the subsequent month.
A long-only equal-weight portfolio of qualifying names at each monthly rebalance
generates a positive net Sharpe ratio.

**H4 — Donchian Breakout:**
Stocks that close above their prior 20-day Donchian channel high (computed on
data ending at t−1 to prevent look-ahead) exhibit positive continuation. A
long-only equal-weight portfolio of qualifying names at each monthly rebalance
generates a positive net Sharpe ratio.

All hypotheses are tested at a single pre-registered parameter configuration.
No parameter search is conducted after observing results.

---

## 3. Universe Construction Logic

### 3.1 Constituent Tickers

**Semiconductors (18 names):**
NVDA, AMD, AVGO, TSM, QCOM, TXN, INTC, MU, ADI, NXPI, MCHP, ON, MRVL, MPWR,
SWKS, QRVO, LSCC, ARM

**Semiconductor Equipment (6 names):**
ASML, AMAT, LRCX, KLAC, TER, ENTG

**AI Infrastructure (8 names):**
ANET, VRT, SMCI, DELL, CRDO, ALAB, CIEN, COHR

**Total universe: 32 names** (de-duplicated; all US-listed or ADR on Yahoo Finance)

**Benchmarks (not in tradeable universe):**
SOXX (iShares Semiconductor ETF), SMH (VanEck Semiconductor ETF),
QQQ (Invesco Nasdaq-100 ETF), SPY (SPDR S&P 500 ETF)

### 3.2 Liquidity Screen

At each monthly rebalance date, a symbol is eligible for portfolio selection
only if its median daily dollar volume over the trailing 63 trading bars meets
or exceeds **$25,000,000** (USD). Symbols that fail this screen are excluded
from the current rebalance's long or short legs but remain in the universe for
future rebalance dates.

### 3.3 Minimum Eligible Names

A strategy rebalance is skipped (portfolio stays flat) if fewer than **6**
universe names pass both the liquidity screen and the signal filter at a given
rebalance date. This prevents degenerate single-name portfolios.

### 3.4 History Requirement

Symbols with fewer than 504 trading days of valid history (~2 years) are flagged
in the validation report. They may still trade if they pass the liquidity screen,
but they are excluded from the IS/OOS stability split comparison.

---

## 4. Data Requirements

| Field | Source | Frequency | Notes |
|---|---|---|---|
| Open, High, Low, Close | Yahoo Finance (yfinance) | Daily | Adjusted for splits and dividends (auto_adjust=True) |
| Volume | Yahoo Finance (yfinance) | Daily | Shares traded |
| Benchmark prices | Yahoo Finance (yfinance) | Daily | SOXX, SMH, QQQ, SPY |

**No synthetic or fabricated data.** If a symbol cannot be downloaded, it is
recorded as skipped with the reason. The pipeline does not substitute synthetic
prices for missing tickers under any circumstances.

**Date range:** Controlled by the `period` parameter (default `"5y"`). The
`interval` parameter controls bar granularity (default `"1d"`).

**Data validation checks performed before any backtesting:**
- Non-positive close prices (symbol skipped if found)
- Single-day price moves exceeding ±60% (flagged as possible data error)
- Symbols with fewer than the minimum history bars (flagged; eligible
  for selection after screen)
- Missing value coverage (percentage reported per symbol)

---

## 5. Strategy Families

### 5.1 Cross-Sectional Momentum

**Type:** Market-neutral long/short (or long-only if `--long-only` flag set)
**Rebalance:** Monthly (month-end)
**Leg construction:** Equal-weight top and bottom tercile of eligible names
**Direction:** Long top tercile, short bottom tercile (dollar-neutral default)

### 5.2 Trend Following

**Type:** Long-only, fully invested when signal is active
**Rebalance:** Monthly (month-end snapshot of daily signal)
**Leg construction:** Equal-weight across all names where close > MA(50) AND
close > MA(100) AND close > MA(200)

### 5.3 Mean Reversion

**Type:** Long-only, fully invested when signal is active
**Rebalance:** Monthly (month-end snapshot of daily signal)
**Leg construction:** Equal-weight across names where z-score < −2.0; hold
until z-score reverts above 0 (exit handled at next monthly rebalance)

### 5.4 Donchian Breakout

**Type:** Long-only, fully invested when signal is active
**Rebalance:** Monthly (month-end snapshot of daily signal)
**Leg construction:** Equal-weight across names where close > 20-day Donchian
channel high, computed with explicit look-ahead prevention

---

## 6. Signal Definitions (Exact Formulas)

### 6.1 Cross-Sectional Momentum Signal

```
momentum_signal[t, i] = close[t - skip, i] / close[t - lookback, i] - 1
```

where:
- `lookback = 252` trading days (~12 months)
- `skip = 21` trading days (~1 month, to avoid short-term reversal)
- `i` = symbol index
- `t` = current rebalance date

Signals are computed using only data available at time `t`. At each rebalance,
symbols are ranked by this signal and the top and bottom `quantile = 1/3`
fraction of eligible names form the long and short legs respectively.

Eligible names at `t`: those where `momentum_signal[t, i]` is non-NaN AND
median daily dollar volume over the trailing 63 bars is >= $25M.

**Dollar volume:** `dollar_vol[t, i] = rolling_median(close[t, i] * volume[t, i], 63)`

### 6.2 Trend Following Signal

```
trend_signal[t, i] = 1  if  close[t, i] > MA(50)[t, i]
                         AND close[t, i] > MA(100)[t, i]
                         AND close[t, i] > MA(200)[t, i]
                   = 0  otherwise
```

where `MA(w)[t, i] = mean(close[t-w+1 : t+1, i])` — a trailing simple moving
average using only data up to and including `t`.

Weights at monthly rebalance: equal across names where `trend_signal = 1`,
subject to the minimum eligible count of 6.

### 6.3 Mean Reversion Signal

```
z_score[t, i] = (close[t, i] - rolling_mean(close, 20)[t, i])
                / rolling_std(close, 20)[t, i]

mr_signal[t, i] = 1  if  z_score[t, i] < -2.0
                = 0  otherwise
```

where `rolling_mean` and `rolling_std` use a 20-bar trailing window. Rolling
standard deviation of zero is replaced with NaN to avoid division by zero.

Weights at monthly rebalance: equal across names where `mr_signal = 1`,
subject to the minimum eligible count of 6. Short side is not used (long-only).

### 6.4 Donchian Breakout Signal

```
channel_high[t, i]  = rolling_max(close[t-1, i], 20)
                    = max(close[t-20 : t, i])   # EXCLUDES current bar

breakout_signal[t, i] = 1  if  close[t, i] > channel_high[t, i]
                       = 0  otherwise
```

**Critical implementation note:** `shift(1)` is applied to the price series
**before** the `rolling(20).max()` operation. This ensures the channel high at
time `t` is the maximum of bars `[t−20, t−1]`, explicitly excluding the current
bar. Failure to shift before rolling would introduce look-ahead bias.

```python
# Correct (no look-ahead):
chan_high = close.shift(1).rolling(window).max()
signal = (close > chan_high).astype(float)
```

Weights at monthly rebalance: equal across names where `breakout_signal = 1`,
subject to the minimum eligible count of 6.

---

## 7. Backtest Assumptions

| Assumption | Value | Rationale |
|---|---|---|
| Bar frequency | Daily (1d) | Standard equity research convention |
| Rebalance frequency | Month-end | Balances turnover vs signal decay |
| Position sizing | Equal weight within each leg | Avoids optimisation bias |
| Weight cap | ±100% per position | Prevents degenerate single-name exposure |
| Position lag | 1 bar (shift-1 rule) | Weights derived at `t` take effect at `t+1` |
| Shorting | Allowed in CS-momentum (default) | Can be suppressed with `--long-only` |
| Universe | Fixed pre-defined list | No survivorship-bias filtering applied |
| Data look-ahead | None | Enforced via shift-1 rule and Donchian shift |
| IS/OOS split | Temporal midpoint (50/50) | Not chosen to maximise IS or minimise OOS |

**Position lag implementation:**
```python
# Gross daily PnL at time t:
pnl[t] = sum_i( weights[t-1, i] * daily_return[t, i] )
```

Weights at `t-1` (established at the previous rebalance) are multiplied by
next-bar returns. This is the strict no-look-ahead condition.

---

## 8. Cost Assumptions

| Cost Component | Default | Unit |
|---|---|---|
| Commission | 10 bps | One-way, per side |
| Slippage | 10 bps | One-way, per side |
| **Total round-trip** | **40 bps** | Both sides, both components |

Costs are charged on **traded notional** at each rebalance date. The cost
series is:

```
cost[t] = sum_i( |delta_weight[t, i]| ) * cost_rate
```

where `delta_weight[t, i] = weight[t, i] - weight[t_prev, i]` is the change in
position weight at rebalance `t`, and `cost_rate = (cost_bps + slippage_bps) / 10000`.

Initial deployment costs (first rebalance) are treated as turnover equal to the
sum of absolute initial weights.

**rf = 0.0 (no FRED).** No risk-free rate is subtracted from strategy returns
when computing the Sharpe ratio. This is a known limitation that slightly
overstates Sharpe in high interest rate environments. The caveat is flagged
in every output file and the disclaimer.

---

## 9. Risk Controls

| Control | Setting | Purpose |
|---|---|---|
| Minimum eligible names | 6 | Prevents degenerate portfolios |
| Maximum position weight | ±100% | Clips extreme single-name allocations |
| Liquidity screen | $25M median daily $-vol (63-bar) | Ensures names are tradeable |
| Negative-price filter | Skip symbol | Removes data errors |
| No look-ahead enforcement | shift-1 rule, Donchian shift(1) | Research integrity |
| No synthetic data | Hard constraint | Avoids false performance attribution |
| Single parameter set | Pre-registered | No multiple-testing inflation |
| No parameter tuning after results | Pre-registration commitment | Avoids data snooping |

**Out-of-sample stability check:** The full-period backtest for cross-sectional
momentum is additionally split at the temporal midpoint. IS and OOS Sharpe ratios
are reported side-by-side. A large gap (IS >> OOS) is interpreted as overfitting
even though no parameters were tuned.

---

## 10. Portfolio Construction

### 10.1 Long/Short (Cross-Sectional Momentum, default)

At each month-end rebalance date:
1. Compute momentum signal for all eligible names (pass liquidity screen + non-NaN signal).
2. Sort by signal value ascending.
3. Assign `+1/k` weight to the top `k = max(1, round(n * 1/3))` names.
4. Assign `−1/k` weight to the bottom `k` names.
5. Clip all weights to [−1, +1].
6. Forward-fill weights until the next rebalance.

Dollar neutrality: long and short legs are independently equal-weighted at
`1/k` each. The portfolio is approximately dollar-neutral but not enforced to
be exact (gross exposure = 2 × 1/k × k = 2.0 in a balanced portfolio).

### 10.2 Long-Only (Trend Following, Mean Reversion, Breakout)

At each month-end rebalance date:
1. Snapshot the daily signal DataFrame for the rebalance date.
2. Select names where signal > 0 (trend, breakout) or signal = 1 (mean reversion).
3. If at least `min_eligible = 6` names qualify, assign `1/n` weight equally.
4. If fewer than 6 qualify, assign zero weight to all names (flat).
5. Forward-fill weights until the next rebalance.

---

## 11. Agent Workflow

The research pipeline integrates five specialised agents from the Alpha Search
multi-agent system. Each agent runs in sequence during Step 3 of the pipeline,
before any strategy backtesting begins.

### 11.1 DataEngineerAgent

**Role:** Data quality gatekeeper.

**Responsibilities:**
- Validates downloaded OHLCV for the universe and benchmark tickers.
- Flags non-positive prices, large single-day moves (>60%), gaps, and
  insufficient history.
- Reports coverage statistics (percentage of non-NaN bars per symbol).
- Records validation findings to the output `agent_review.md` file.

**Output:** List of `CritiqueMessage` objects with severity levels (INFO,
WARNING, ERROR).

### 11.2 OpportunityAgent

**Role:** Pre-backtest opportunity ranking.

**Responsibilities:**
- Ranks the universe by trailing return, volatility-adjusted return, and
  dollar volume.
- Identifies names with anomalous patterns (e.g., price gaps, volume spikes)
  that may require manual review.
- Produces a ranked opportunity table appended to `agent_review.md`.

**Output:** List of `CritiqueMessage` objects summarising opportunity scores.

### 11.3 QuantEngineerAgent

**Role:** Signal construction validator.

**Responsibilities:**
- Verifies that all signal computations produce valid, finite outputs for a
  representative sample of dates.
- Checks that no future data bleeds into signal values (look-ahead detection
  heuristic: correlation between signal at `t` and return at `t` vs `t+1`).
- Reports signal coverage (percentage of rebalance dates with at least one
  eligible name).

**Output:** Signal audit report appended to `agent_review.md`.

### 11.4 RiskManagerAgent

**Role:** Portfolio-level risk monitor.

**Responsibilities:**
- Computes concentration metrics for each rebalance (Herfindahl-Hirschman
  Index on absolute weights).
- Flags rebalance dates where a single name constitutes more than 50% of the
  long or short leg.
- Reports drawdown depth and duration for the primary strategy.
- Flags any period where the strategy's 63-day rolling volatility exceeds
  three times the full-period average.

**Output:** Risk audit report appended to `agent_review.md`.

### 11.5 ResearchAgent

**Role:** Summary and interpretation.

**Responsibilities:**
- Aggregates findings from the four strategy backtests.
- Applies the mechanical success/failure criteria (Section 14/15) to produce
  a pass/fail verdict for each strategy.
- Writes the narrative summary section of `report.md`, including IS/OOS
  comparison, benchmark comparison table, and methodology notes.
- Logs all strategy results to MemoryStore for cross-run retrieval.

**Output:** Narrative research report (`report.md`) and MemoryStore records.

### 11.6 Agent Fallback Behaviour

All agent invocations are wrapped in try/except blocks. If an agent is
unavailable (ImportError, connection failure, or any exception), the pipeline
logs a warning and continues. The quantitative backtest results are unaffected.

---

## 12. Memory Logging Plan

All research findings are persisted to the Alpha Search MemoryStore for
longitudinal tracking across runs and to support agent retrieval.

### 12.1 Records Written Per Run

| Record Type | Title Template | Content |
|---|---|---|
| `architecture_decision` | AI Infra Alpha Research — parameter registration | Pre-registered parameters, universe size, skipped symbols, run timestamp |
| `strategy_result` | AI Infra — {strategy_name} — {verdict} | Net Sharpe, Max DD, annualised return, alpha vs benchmark, verdict |
| `data_quality_issue` | AI Infra — skipped symbols | List of skipped tickers with reason (non-positive prices) |

### 12.2 Importance Scores

- `promising` or `marginal_positive` verdict: `importance_score = 0.8`
- All other verdicts: `importance_score = 0.5`
- Parameter registration record: `importance_score = 0.9`

### 12.3 Tags

Each record is tagged with: `["ai_infra", "{strategy_name}", "{verdict}"]`
for retrieval by strategy family, verdict type, or universe.

### 12.4 Failure Handling

If MemoryStore is unavailable (import error, database lock, or any exception),
the pipeline logs a WARNING and continues. Memory logging failure does not
abort the research run or invalidate the results.

---

## 13. Output Files

All outputs are written to a timestamped directory under the base output path:

```
{output_dir}/
└── {YYYYMMDD_HHMMSS}/
    ├── metadata.json
    ├── universe_used.csv
    ├── skipped_symbols.csv
    ├── strategy_results_summary.csv
    ├── cross_sectional_momentum_results.csv
    ├── trend_following_results.csv
    ├── mean_reversion_results.csv
    ├── breakout_results.csv
    ├── benchmark_comparison.csv
    ├── agent_review.md
    ├── report.md
    ├── report.docx                         (optional; requires python-docx)
    └── figures/
        ├── equity_curve.png
        ├── drawdown_curve.png
        ├── rolling_sharpe.png
        ├── strategy_comparison.png
        ├── benchmark_comparison.png
        └── correlation_heatmap.png
```

### 13.1 File Descriptions

**`metadata.json`** — Run parameters: timestamp, period, interval, cost_bps,
long_only, rf_annual, universe_used, symbols_skipped, primary_benchmark,
duration_seconds, disclaimer text.

**`universe_used.csv`** — Single-column CSV listing all symbols that passed
data validation and were included in strategy backtesting.

**`skipped_symbols.csv`** — Single-column CSV listing all symbols excluded due
to non-positive prices or download failure.

**`strategy_results_summary.csv`** — One row per strategy: verdict, net Sharpe,
gross Sharpe, annualised return, annualised volatility, max drawdown, alpha vs
benchmark, beta vs benchmark, alpha t-stat, R-squared, turnover per rebalance.

**`{strategy}_results.csv`** — Daily net return series for each strategy (date,
net_return columns).

**`benchmark_comparison.csv`** — Performance metrics for SOXX, SMH, QQQ, SPY
over the same period.

**`agent_review.md`** — Formatted output from all five agents: data quality
findings, opportunity rankings, signal audit, risk audit, data quality summary,
per-symbol validation report.

**`report.md`** — Comprehensive Markdown research report including: header with
run metadata, data quality section, strategy results table, IS/OOS stability
table for cross-sectional momentum, benchmark comparison table, overall verdict
with narrative, methodology notes, disclaimer.

**`figures/equity_curve.png`** — Cumulative net equity curves for all four
strategies on a log scale, starting at 1.0.

**`figures/drawdown_curve.png`** — Drawdown series for all four strategies
(negative convention; −0.25 = 25% drawdown).

**`figures/rolling_sharpe.png`** — 63-bar rolling Sharpe ratio for
cross-sectional momentum (net), with reference lines at 0 and 1.0.

**`figures/strategy_comparison.png`** — Side-by-side bar chart of gross vs net
Sharpe ratio for all four strategies.

**`figures/benchmark_comparison.png`** — Sharpe ratio bar chart comparing SOXX,
SMH, QQQ, SPY, and the cross-sectional momentum strategy.

**`figures/correlation_heatmap.png`** — Pairwise return correlation heatmap of
the four strategy net return series.

---

## 14. Success Criteria

A strategy is classified as **"promising"** (passes) if and only if ALL of the
following conditions are satisfied simultaneously:

1. **Net Sharpe ratio > 1.0** over the full backtest period (after deducting
   commission and slippage at 10 bps each, one-way).
2. **Alpha t-statistic |t(α)| ≥ 2.0** from the OLS regression of daily strategy
   returns on the primary benchmark (SOXX by default), providing statistical
   evidence that the alpha is distinguishable from zero.

These thresholds apply to net-of-cost returns. Gross Sharpe ratios are reported
alongside for transparency but are not used in the pass/fail determination.

For strategies classified as "promising," the research report additionally
recommends walk-forward validation before any deployment consideration.

A secondary classification **"marginal_positive"** is applied when:
- Net Sharpe > 0.5 but ≤ 1.0, regardless of t-statistic.

A classification of **"marginal"** is applied when:
- Net Sharpe > 0.0 but ≤ 0.5.

All classifications are recorded in the output `strategy_results_summary.csv`
and in the `verdict` field of each strategy's results dictionary.

---

## 15. Failure Criteria

A strategy is classified as **"unprofitable"** (fails) if:

1. **Net Sharpe ratio ≤ 0** — the strategy destroys value after costs over
   the full backtest period, or
2. **No trades generated** — the signal never fires (zero rebalances with
   non-zero positions), in which case the verdict is **"no_results"**.

Results are **never massaged** to avoid a failure verdict. Negative Sharpe
ratios are reported as-is with the full metric set. A failure result means:

- The strategy hypothesis is not supported by historical data for this universe
  and time period.
- No adjustments are made to parameters, universe, or date range after observing
  a failure result.
- The failure is documented in MemoryStore for reference in future research runs.

A "no_results" classification (no trades) may arise when:
- The universe is too small for tercile formation (fewer than 6 eligible names).
- A lookback longer than the available history leaves no valid signal bars.
- All names fail the liquidity screen at every rebalance date.

---

## 16. Limitations

**1. Survivorship Bias**
The universe is constructed as of the research date (2026-05-29) and includes
only companies that currently exist as listed equities. Companies that were
delisted, acquired, went bankrupt, or were removed from the AI-infrastructure
category between the start of the backtest period and today are not included.
This introduces upward bias in all strategy results — particularly for the
5-year default period. The magnitude of survivorship bias is not quantified in
this study.

**2. rf = 0 Caveat**
No risk-free rate is subtracted from strategy returns when computing the Sharpe
ratio (`rf_annual = 0.0`). In high interest rate environments (e.g., 2022–2024
when the fed funds rate reached 5.25–5.50%), this overstates the Sharpe ratio
of long-only strategies relative to a genuine risk-adjusted measure. The caveat
is displayed in every output file, the run banner, the summary table, and the
disclaimer. All figures and tables show the `rf = 0` assumption explicitly.

**3. No Market Impact Model**
The cost model applies a flat per-side slippage assumption (default 10 bps) to
all trades regardless of position size, stock liquidity, or order urgency. Real
market impact is a non-linear function of order size relative to average daily
volume. For large positions in less liquid names (e.g., LSCC, CRDO, ALAB,
QRVO), actual round-trip costs may substantially exceed the modelled 40 bps.
No Kyle lambda or square-root market impact model is applied.

**4. Look-Ahead Risk in Data**
Although all signal computations enforce the shift-1 rule and Donchian breakout
uses `shift(1)` before `rolling`, adjusted price data from Yahoo Finance may
incorporate adjustments (splits, dividends) that are applied retroactively using
future information. Post-hoc adjustment factors are applied uniformly to the
entire price history, which is an industry-standard practice but technically
introduces a minor form of look-ahead in the adjusted close series.

**5. Transaction Timing**
The backtest assumes all rebalance trades are executed at the closing price of
the rebalance date (month-end close). In practice, month-end closes may
experience elevated volatility and spreads. Using next-open or VWAP execution
prices would be more realistic and would likely increase slippage.

**6. Single Time Period**
The backtest covers a single contiguous historical period determined by the
`period` parameter. Results are not validated across multiple sub-periods,
different market regimes, or out-of-sample windows beyond the single 50/50
temporal split. Structural breaks in the relationship between AI-infra stock
performance and cross-sectional momentum signals are not modelled.

**7. No Leverage or Margin Costs**
The long/short cross-sectional momentum strategy implies short positions but
does not model borrow costs (stock lending fees), margin requirements, or
leverage constraints. Borrow costs for high-momentum AI-infra names during
momentum drawdowns can be materially expensive and are omitted from the cost
model.

**8. Tax and Regulatory Considerations**
No tax effects (short-term capital gains, wash-sale rules), regulatory
constraints (Regulation SHO, position limits), or institutional mandate
restrictions are modelled.

---

## 17. Research Disclaimer

> **This research plan and all associated outputs are for informational and
> educational purposes ONLY. They do NOT constitute investment advice, a
> solicitation, an offer, or a recommendation to buy, sell, or hold any
> security, fund, or financial product.**

> **Past performance, including simulated backtest performance, is NOT
> indicative of future results. All backtest results are simulated with the
> benefit of hindsight and are subject to survivorship bias, look-ahead risk,
> model risk, and parameter risk. Simulated returns do not account for all
> costs, taxes, or practical execution constraints that a real investor would
> face.**

> **rf = 0 (no risk-free rate adjustment) is applied throughout. This
> assumption overstates Sharpe ratios relative to measures that subtract
> prevailing interest rates. All Sharpe ratios in this research should be
> interpreted with this caveat in mind.**

> **No representation is made that any investment strategy described herein
> will or is likely to achieve profits, losses, or results similar to those
> shown. Quantitative strategies can and do fail, and loss of capital is
> possible.**

> **Always consult a qualified and regulated financial professional before
> making any investment decision. The authors of this research accept no
> liability for any investment decisions made in reliance on this material.**
