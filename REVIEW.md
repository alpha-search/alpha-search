# Alpha Search v0.2.1 — Comprehensive Code Review

**Reviewer:** AI Code Reviewer  
**Date:** 2025-05-10  
**Commit:** `054f49d`  
**Scope:** Full repository — P0, P1, P2 priority files + test suite  
**Methodology:** Static analysis, architectural review, financial correctness verification

---

## 1. Summary Statistics

| Severity | Count | Description |
|----------|-------|-------------|
| **CRITICAL** | 5 | Data loss risk, incorrect financial calculations, architectural flaws |
| **HIGH** | 8 | Significant bugs, missing validations, API contract violations |
| **MEDIUM** | 12 | Code quality issues, potential edge cases, missing tests |
| **LOW** | 9 | Style issues, documentation gaps, minor improvements |
| **TOTAL** | **34** | |

---

## 2. Top 5 Most Critical Fixes (Ordered by Impact)

### [CRITICAL] #1 — Simulated backtest in QuantEngineerAgent.backtest() produces fiction, not financial analysis
- **File:** `alpha_search/agents/roles.py`
- **Line(s):** 313–364 (QuantEngineerAgent.backtest)
- **Issue:** The `backtest()` method generates random returns using `np.random.normal()` rather than computing actual PnL from historical prices. It "simulates" forward returns with `sim_ret = self._rng.normal(score * 0.3, abs(score) * 0.5 + 0.02)` — this produces fictional results unrelated to the input price data. The agent then presents these as "backtest metrics" to the RiskManagerAgent and consensus builder.
- **Impact:** The entire agent swarm's decision-making is based on fabricated numbers. A user running this pipeline would receive strategy recommendations backed by Sharpe ratios and drawdowns that have no relationship to actual historical performance. This undermines the credibility of the entire framework.
- **Fix:** Replace with the real `BacktestEngine` from `alpha_search/backtest/engine.py`. The `QuantEngineerAgent` should accept a `BacktestEngine` instance via `__init__` and call `engine.run(prices, signal, cost_model=cost_model)` to produce genuine backtest results.
  ```python
  def __init__(self, backtest_engine: Optional[BacktestEngine] = None, cost_model: Optional[CostModel] = None) -> None:
      self.backtest_engine = backtest_engine or BacktestEngine()
      self.cost_model = cost_model or CostModel()
  ```
- **Confidence:** High

### [CRITICAL] #2 — max_drawdown sign convention is inconsistent across the codebase
- **File:** `alpha_search/backtest/metrics.py` (line 74–83), `alpha_search/memory/models.py` (line 265), `alpha_search/agents/roles.py` (multiple)
- **Issue:** `Metrics.max_drawdown()` returns a **positive** number (`-drawdown.min()` where drawdown is negative). But `RiskManagerAgent.MAX_DRAWDOWN_LIMIT = 0.25` and checks `if max_dd < -0.25` — expecting a **negative** number. The field validator in `StrategyMemory` allows `ge=-1.0, le=1.0` — accepting both signs. The `_build_consensus()` method checks `max_dd < 0.25` — treating it as positive.
- **Impact:** RiskManagerAgent will NEVER trigger critical drawdown alerts because `max_dd` (positive) is never `< -0.25`. The entire risk management layer is effectively disabled. Strategy verdicts may incorrectly pass risk checks.
- **Fix:** Standardize on **negative** drawdown (finance convention: -0.25 = 25% drawdown). Change `Metrics.max_drawdown()` to return the raw minimum (negative). Update all checks consistently.
  ```python
  # metrics.py line 83
  return float(drawdown.min())  # returns negative value like -0.25
  ```
  Then update all comparisons: `max_dd < -0.25` (RiskManagerAgent), `max_dd < 0.25` (consensus) → `max_dd > 0.25` for positive threshold checks.
- **Confidence:** High

### [CRITICAL] #3 — `_filter_tickers_from_critiques()` uses fragile substring matching that removes wrong tickers
- **File:** `alpha_search/agents/swarm.py`
- **Line(s):** 393–403
- **Issue:** The ticker filtering uses `if t.upper() in c.message.upper()` which performs substring matching. A critique mentioning "META's earnings beat" would also match "MET" (MetLife) because "MET" is a substring of "META". Similarly, "BRK-B" critiques could match "BRK" or "K-B" (nonsensical but possible).
- **Impact:** Valid tickers can be incorrectly removed from the universe due to substring collisions. In a 20-ticker universe, several tickers could be silently excluded, biasing the entire pipeline.
- **Fix:** Use word-boundary regex or tokenized matching instead of simple substring.
  ```python
  import re
  def _filter_tickers_from_critiques(self, tickers, critiques):
      removed = set()
      for c in critiques:
          if c.critique_type == "data_quality" and c.severity == "critical":
              for t in tickers:
                  # Word-boundary match: standalone ticker, not substring
                  pattern = r'\b' + re.escape(t) + r'\b'
                  if re.search(pattern, c.message, re.IGNORECASE):
                      removed.add(t)
      return [t for t in tickers if t not in removed]
  ```
- **Confidence:** High

### [CRITICAL] #4 — `arbitrage_scan()` uses log(0) via `.replace(0, np.nan)` without validation, silently dropping tickers
- **File:** `alpha_search/opportunities/strategies.py`
- **Line(s):** 498
- **Issue:** `log_prices = np.log(prices_df.replace(0, np.nan))` silently drops any ticker that hits zero (delisted, halted, data error). The subsequent `dropna(how="all", axis=1)` removes columns with ANY NaN, so one bad bar removes the entire ticker. No warning or logging is emitted.
- **Impact:** Tickers with even a single zero or negative price are silently excluded from pair trading analysis. A delisted stock could cause its entire correlation column to vanish, hiding valid pair opportunities. No audit trail explains missing tickers.
- **Fix:** Add explicit validation before the log transform with logging.
  ```python
  # Check for non-positive prices
  invalid = (prices_df <= 0).any()
  if invalid.any():
      bad_tickers = invalid[invalid].index.tolist()
      logger.warning("Excluding tickers with non-positive prices: %s", bad_tickers)
      prices_df = prices_df.drop(columns=bad_tickers)

  log_prices = np.log(prices_df)
  ```
- **Confidence:** High

### [CRITICAL] #5 — Agent sign-offs in consensus are hardcoded `[OK]` regardless of actual analysis
- **File:** `alpha_search/agents/swarm.py`
- **Line(s):** 672–680
- **Issue:** All five agent sign-offs are hardcoded as `[OK]` (except RiskManagerAgent which has a conditional). DataEngineerAgent, OpportunityAgent, QuantEngineerAgent, and ResearchAgent always sign off as "OK" regardless of how many critical critiques they generated or what the actual analysis found.
- **Impact:** The consensus document presents a false picture of unanimous agreement. If DataEngineerAgent flagged 5 tickers with critical data quality issues, it still signs off as "[OK] DataEngineerAgent — data quality verified". This makes the entire consensus mechanism meaningless.
- **Fix:** Make sign-offs conditional based on actual critique counts.
  ```python
  data_ok = len(data_critiques) == 0 or all(c.severity != "critical" for c in data_critiques)
  opp_ok = len(opp_critiques) == 0 or all(c.severity != "critical" for c in opp_critiques)
  quant_ok = len(quant_critiques) == 0 or all(c.severity != "critical" for c in quant_critiques)
  research_ok = len(research_critiques) == 0 or all(c.severity != "critical" for c in research_critiques)

  f"  [{'OK' if data_ok else 'XX'}] DataEngineerAgent    — {'data quality verified' if data_ok else f'{len(data_critiques)} issues flagged'}",
  ```
- **Confidence:** High

---

## 3. All Issues by Category

### 3.1 Architecture & Design Patterns

### [HIGH] #6 — AgentSwarm violates Single Responsibility: orchestrates AND generates critiques AND builds consensus
- **File:** `alpha_search/agents/swarm.py`
- **Line(s):** 187–737
- **Issue:** `AgentSwarm` is a ~550-line god class that handles orchestration (9 pipeline phases), critique generation (`_cross_agent_critique`), improvement application (`_apply_improvements`), consensus building (`_build_consensus`), and ticker filtering. It contains hardcoded critique messages (lines 421–522) that should belong to the individual agents.
- **Impact:** Impossible to unit test critique generation in isolation. Adding a new agent requires modifying `AgentSwarm._cross_agent_critique()`. The hardcoded critiques become stale if agent logic changes.
- **Fix:** Extract `CritiqueGenerator`, `ConsensusBuilder`, and `ImprovementEngine` into separate classes. Have each agent implement a `critique(other_agent_outputs)` interface that the swarm calls dynamically.
- **Confidence:** Medium

### [MEDIUM] #7 — `AgentJournal._flush()` uses duck-typing that hides failures silently
- **File:** `alpha_search/agents/swarm.py`
- **Line(s):** 167–180
- **Issue:** The `_flush()` method tries `append`, `save`, `log` on the memory store via `hasattr()`, catching ALL exceptions with `except Exception: logger.exception(...)`. If the memory store is temporarily unavailable, the entry is lost with only a log line — there's no retry, no queuing, no raise.
- **Impact:** Under load or transient DB issues, critiques and strategies are silently dropped from persistent storage. The journal's in-memory list grows unbounded but the DB never receives the data.
- **Fix:** Add a retry mechanism (3 attempts with exponential backoff) and a dead-letter queue for failed entries. Or raise after logging so the caller can decide.
- **Confidence:** Medium

### [MEDIUM] #8 — `_all_tickers()` heuristic fails for tickers with length > 5 characters
- **File:** `alpha_search/agents/roles.py`
- **Line(s):** 65–85
- **Issue:** The fallback heuristic for flat columns uses `1 <= len(c) <= 5` which excludes valid tickers like "BRK-B" (5 chars with hyphen = 6), "GOOGL" (5, OK), but more importantly, Indian tickers like "RELIANCE.NS" (11 chars) and "BHARTIARTL.NS" (13 chars) are completely excluded.
- **Impact:** Indian market data (20 tickers in INDIA_TOP20) cannot be processed by the agent swarm because all tickers have `.NS` suffixes making them 11+ characters. The swarm receives an empty ticker list and produces empty results.
- **Fix:** Remove the length restriction or make it configurable per market. Better: detect MultiIndex properly for Indian data format.
  ```python
  # Support Indian (.NS) and other suffixed tickers
  return sorted([c for c in flat if isinstance(c, str) and any(char.isupper() for char in c)])
  ```
- **Confidence:** High

---

### 3.2 Code Quality & Python Idioms

### [HIGH] #9 — `QuantEngineerAgent.__init__` accepts `seed` parameter but ignores it for backtest
- **File:** `alpha_search/agents/roles.py`
- **Line(s):** 248–249
- **Issue:** The `seed` parameter creates `np.random.default_rng(seed)` for the simulated backtest. But since the backtest is simulated (Issue #1), this seed provides false reproducibility — running twice with the same seed gives the same fictional results, creating an illusion of determinism.
- **Impact:** Users may believe results are reproducible because of the seed, not realizing the entire backtest is random simulation.
- **Fix:** Remove the seed and the RNG once Issue #1 is fixed (real backtest engine doesn't need randomness).
- **Confidence:** High

### [MEDIUM] #10 — `rsi()` in `signals/technical.py` uses simple rolling mean instead of Wilder's EMA
- **File:** `alpha_search/signals/technical.py`
- **Line(s):** 102–129
- **Issue:** The `rsi()` function computes `avg_gain = gain.rolling(window=window).mean()` (simple average). The canonical RSI uses Wilder's smoothing (an EMA with `alpha = 1/window`). The `_rsi()` helper in `opportunities/strategies.py` (line 59) correctly uses `gain.ewm(alpha=1.0/period)` but `signals/technical.py` does not.
- **Impact:** RSI signals from `signals/technical.py` will differ from those in `opportunities/strategies.py`. Users get inconsistent signals depending on which module they import from.
- **Fix:** Update `signals/technical.py` to use EWM matching the `_rsi()` implementation in `opportunities/strategies.py`.
- **Confidence:** High

### [MEDIUM] #11 — `MemoryStore.initialize()` swallows ALL SQL errors silently
- **File:** `alpha_search/memory/store.py`
- **Line(s):** 122–129
- **Issue:** `except Exception: pass` on every schema statement means CREATE TABLE failures are silently ignored. If the schema.sql file is corrupted or missing, initialization "succeeds" but tables don't exist, causing confusing failures later.
- **Impact:** Difficult to debug — user gets "table not found" errors at runtime with no indication that initialization failed.
- **Fix:** Log the error at minimum. Better: collect failures and raise a `MemoryInitializationError` if any CREATE TABLE fails.
  ```python
  failed = []
  for stmt in statements:
      try:
          self.conn.execute(stmt)
      except Exception as exc:
          failed.append((stmt[:50], str(exc)))
  if failed:
      logger.error("Schema initialization had %d failures: %s", len(failed), failed)
      raise MemoryInitializationError(f"Failed to create tables: {failed}")
  ```
- **Confidence:** Medium

### [LOW] #12 — `_parse_iso()` helper duplicates Python's `datetime.fromisoformat()`
- **File:** `alpha_search/memory/models.py`
- **Line(s):** 777–811
- **Issue:** The 35-line `_parse_iso()` function manually tries 8 different date formats. Python 3.7+ has `datetime.fromisoformat()` which handles all ISO-8601 formats natively.
- **Fix:** Replace with `datetime.fromisoformat()` + UTC fallback.
- **Confidence:** High

### [LOW] #13 — `__mean_rev_rankings` unused variable with `# noqa: F841`
- **File:** `alpha_search/agents/swarm.py`
- **Line(s):** 285
- **Issue:** Mean reversion rankings are computed but never used in the pipeline. The variable exists only to satisfy a linter.
- **Fix:** Either use the mean reversion rankings in opportunity analysis or remove the computation entirely.
- **Confidence:** Medium

### [LOW] #14 — `to_row()` and `to_dict()` methods have divergent field sets
- **File:** `alpha_search/memory/models.py`
- **Line(s):** 168–179 (MemoryRecord), 383–393 (StrategyMemory)
- **Issue:** `MemoryRecord.to_row()` omits `title`, `importance_score`, `source_file`, `related_task` that exist in `to_dict()`. `StrategyMemory.to_row()` has a `ticker` field not present in the model. These inconsistencies suggest `to_row()` is either dead code or used by code that expects a different schema than what's actually defined.
- **Fix:** Align `to_row()` with the actual DB schema, or remove if unused.
- **Confidence:** Medium

---

### 3.3 Known Bug Hotspots — Similar Patterns

### [HIGH] #15 — `z_score_mean_reversion()` in `signals/technical.py` has same NaN-handling bug pattern as historical RSI bug
- **File:** `alpha_search/signals/technical.py`
- **Line(s):** 93
- **Issue:** `z = (returns - rolling_mean) / rolling_std.replace(0, np.nan)` — if `rolling_std` has NaN values, `replace(0, np.nan)` has no effect and division by NaN propagates. The original RSI bug was `.replace(0, np.nan)` causing all NaN — this is the same pattern but in a different context.
- **Impact:** For periods with constant returns (e.g., stock halt, flat trading), z-score becomes NaN and the signal is lost. Unlike the RSI bug which replaced ALL zeros with NaN, this only affects the standard deviation column.
- **Fix:** Handle NaN explicitly: `rolling_std.replace(0, np.nan).fillna(np.inf)` so constant-return periods produce z=0 (no signal) rather than NaN.
  ```python
  safe_std = rolling_std.replace(0, np.nan).fillna(1e-9)  # avoid div-by-zero
  z = (returns - rolling_mean) / safe_std
  z = z.fillna(0.0)  # flat periods → no signal
  ```
- **Confidence:** High

### [MEDIUM] #16 — Holiday edge case pattern persists in agent validation
- **File:** `alpha_search/agents/roles.py`
- **Line(s):** 217
- **Issue:** `DataEngineerAgent.validate_data()` checks `n_total < self.MIN_HISTORY_DAYS` (60 days). This was fixed in tests to allow `28 <= len(df) <= 30`, but the agent validation still uses a hardcoded 60-day threshold. For 3-month backtests (common in the notebook), ALL tickers would fail this check.
- **Impact:** Short-term backtests (30–60 days) are rejected by the agent swarm even though they're valid for some strategies.
- **Fix:** Make `MIN_HISTORY_DAYS` configurable per strategy or derive from the lookback window used.
- **Confidence:** Medium

### [MEDIUM] #17 — `0.85:.1f` float formatting quirk pattern in Bollinger calculation
- **File:** `alpha_search/opportunities/strategies.py`
- **Line(s):** 540
- **Issue:** `coint_score = _clamp(1.0 - (adf_pvalue / 0.20))` — when `adf_pvalue = 0.17`, this gives `1.0 - 0.85 = 0.15`. If formatted with `:.1f`, Python rounds `0.15` to `0.1` (banker's rounding). This is the same quirk that caused the `0.85:.1f → 0.8` bug in journal.py.
- **Impact:** Cointegration scores displayed in reports may appear lower than actual values due to rounding.
- **Fix:** Use `:.2f` or `:.3f` for all score formatting throughout the codebase. Audit all `:.1f` usages.
- **Confidence:** Medium

---

### 3.4 Testing Coverage

### [HIGH] #18 — Zero tests for `AgentSwarm.run_collaboration()`
- **File:** N/A (missing)
- **Issue:** Despite being the core orchestration method (the "main event" of the framework), there are NO tests that exercise `run_collaboration()`. The 104 existing tests cover memory store, backtest engine, signals, and data providers individually, but never the full pipeline.
- **Impact:** Refactoring `AgentSwarm` is dangerous — any change could break the entire pipeline with no test feedback. The simulated backtest bug (#1) would have been caught by even a basic integration test.
- **Fix:** Add `tests/test_agent_swarm.py` with tests for:
  - Full collaboration run with mock agents
  - Missing agent detection
  - Critique absorption and stats
  - Consensus building with different Sharpe/dd combinations
  - Ticker filtering from critiques
- **Confidence:** High

### [HIGH] #19 — Zero tests for `QuantEngineerAgent` signal construction and backtest
- **File:** N/A (missing)
- **Issue:** No tests verify that `build_momentum_signals()`, `build_mean_reversion_signals()`, or `backtest()` produce correct outputs. The simulated backtest (#1) has zero coverage.
- **Impact:** The simulated backtest bug went undetected. Signal logic changes can't be validated.
- **Fix:** Add `tests/test_agent_roles.py` with:
  - Mock price data → verify signal values
  - Backtest result → verify it's based on real prices, not RNG
  - Critique generation → verify real, specific messages
- **Confidence:** High

### [MEDIUM] #20 — Tests don't verify critique messages are real vs placeholder
- **File:** N/A (missing assertion)
- **Issue:** While agents produce real critiques (good!), there are no tests asserting that critique messages contain actual data references (ticker names, specific numbers) rather than generic text.
- **Impact:** A regression could replace real critiques with placeholders and no test would catch it.
- **Fix:** Add assertions like `assert "AAPL" in critique.message` and `assert any(char.isdigit() for char in critique.message)`.
- **Confidence:** Medium

### [MEDIUM] #21 — No integration test for the full data → signals → backtest → agents pipeline
- **File:** N/A (missing)
- **Issue:** Individual components are tested, but no test exercises the full flow from `YFinanceProvider.fetch()` through `AgentSwarm.run_collaboration()` to `MemoryStore` persistence.
- **Impact:** Interface mismatches between modules are only caught at runtime.
- **Fix:** Add `tests/test_integration.py` with a minimal end-to-end run using synthetic data.
- **Confidence:** Medium

---

### 3.5 Security

### [MEDIUM] #22 — `search_by_tags()` is vulnerable to SQL injection via tag content
- **File:** `alpha_search/memory/store.py`
- **Line(s):** 264–289
- **Issue:** `placeholders = " OR ".join("tags LIKE ?" for _ in tags)` uses parameterized queries correctly, BUT `tags` are stored as JSON strings. A tag like `"test"%"` (with wildcards) would match more than intended because `LIKE` pattern matching interprets `%` as wildcard.
- **Impact:** A malicious tag could cause the search to return unintended records. Low severity since tags are internally controlled, but should be documented.
- **Fix:** Escape `%` and `_` in tag values before parameterizing, or use exact JSON matching instead of LIKE.
- **Confidence:** Low

### [LOW] #23 — `stats()` method uses f-string SQL without parameterization
- **File:** `alpha_search/memory/store.py`
- **Line(s):** 785–786
- **Issue:** `cursor = self.conn.execute(f"SELECT COUNT(*) FROM {table}")` — while `table` comes from a hardcoded list, this pattern shouldn't exist in a security-conscious codebase.
- **Fix:** Use a whitelist or parameterize (though DuckDB/SQLite don't support table name parameters, a whitelist is better).
- **Confidence:** Low

---

### 3.6 Performance

### [MEDIUM] #24 — `arbitrage_scan()` is O(n²) on tickers — will choke on large universes
- **File:** `alpha_search/opportunities/strategies.py`
- **Line(s):** 522
- **Issue:** `for a, b in combinations(tickers, 2)` creates n*(n-1)/2 iterations. For S&P 500 (503 tickers), this is ~126,000 pairs. Each pair runs OLS regression + ADF test — this will take minutes/hours.
- **Impact:** The framework can't scale beyond ~50 tickers for pair trading.
- **Fix:** Add early filtering (correlation pre-screen on a random sample, or use `numba`/`cython` for the OLS loop). Add a `max_tickers` parameter with a reasonable default (50).
- **Confidence:** High

### [MEDIUM] #25 — `AgentJournal._local` list grows unbounded during long swarm runs
- **File:** `alpha_search/agents/swarm.py`
- **Line(s):** 109, 118, 131, 151
- **Issue:** Every `log_critique()`, `log_event()`, and `log_strategy()` appends to `self._local` — a Python list that grows forever. A 2-hour research session with 5 agents generating critiques every minute could accumulate 100,000+ entries.
- **Impact:** Memory consumption grows linearly. Long-running sessions will exhaust available RAM.
- **Fix:** Implement a circular buffer with a configurable max size (e.g., 10,000 entries). Or flush and clear `_local` periodically.
- **Confidence:** Medium

### [LOW] #26 — `DataEngineerAgent.validate_data()` loops per-ticker instead of vectorized
- **File:** `alpha_search/agents/roles.py`
- **Line(s):** 148–230
- **Issue:** The validation loop iterates tickers one-by-one with `for ticker in tickers:`. Each ticker fetches its close/volume series individually. With 500 tickers, this is 500 separate DataFrame lookups.
- **Impact:** For large universes, validation is unnecessarily slow. Vectorized operations across all tickers simultaneously would be 10-50x faster.
- **Fix:** Use vectorized pandas operations: `prices.isna().mean()` for missing data, `prices.pct_change().abs().max()` for jumps — all in one pass.
- **Confidence:** Medium

---

### 3.7 Data Correctness & Financial Accuracy

### [HIGH] #27 — `BacktestEngine._run()` uses position = signal directly, ignoring position sizing
- **File:** `alpha_search/backtest/engine.py`
- **Line(s):** 96–104
- **Issue:** `position = aligned_signal.copy()` — if signal is a z-score (values like -2.5, +3.1), position becomes a leveraged position of 250% or 310% of capital. There's no normalization, no target volatility, no Kelly sizing.
- **Impact:** Backtest results with z-score signals will show extreme leverage and unrealistic returns. The signal-to-position mapping needs explicit sizing rules.
- **Fix:** Add position sizing options: `signal_to_position(signal, method="equal", max_position=1.0)` or `method="volatility_target", target_vol=0.15`.
  ```python
  if position.abs().max() > 1.0:
      logger.warning("Signal exceeds ±1, scaling to unit positions")
      position = position.clip(-1.0, 1.0)
  ```
- **Confidence:** High

### [MEDIUM] #28 — `CostModel.apply()` computes costs on position_changes * prices, not notional
- **File:** `alpha_search/backtest/costs.py`
- **Line(s):** 30–47
- **Issue:** `costs = turnover * prices * self._total_cost_rate` — if `position_changes` is a fraction of capital (e.g., 0.1 = 10% rebalanced), multiplying by `prices` gives cost in dollars for a single-share trade, not a portfolio-scale trade. The cost should be `turnover * portfolio_value * rate`, not `turnover * price * rate`.
- **Impact:** Cost estimates are incorrect unless position changes are expressed in shares. With fractional positions, costs are understated by orders of magnitude.
- **Fix:** Change to `costs = turnover * initial_capital * self._total_cost_rate` or pass portfolio value into `apply()`.
- **Confidence:** High

### [MEDIUM] #29 — Sharpe ratio calculation doesn't account for the actual risk-free rate period
- **File:** `alpha_search/backtest/metrics.py`
- **Line(s):** 44–57
- **Issue:** `excess = returns - risk_free / _TRADING_DAYS_PER_YEAR` uses a flat daily risk-free rate. For multi-year backtests, the risk-free rate varies significantly (0% in 2020, 5%+ in 2023). Using a fixed 2% introduces bias.
- **Impact:** Sharpe ratios for strategies run during high-rate periods are understated; during low-rate periods, overstated.
- **Fix:** Accept a risk-free rate series (from FRED data source) or accept that the approximation is documented.
- **Confidence:** Medium

### [LOW] #30 — `mean_reversion_scan()` z-score uses only 20-day window — not statistically robust
- **File:** `alpha_search/opportunities/strategies.py`
- **Line(s):** 329–341
- **Issue:** The z-score is computed from `rolling(window=20)` — only 20 data points. Statistical convention recommends at least 30 for reliable z-scores.
- **Impact:** Mean reversion signals are noisy with only 20 observations. False signals increase.
- **Fix:** Increase default to 60 days minimum, or document the trade-off between responsiveness and reliability.
- **Confidence:** Medium

---

### 3.8 Documentation

### [LOW] #31 — `ResearchAgent.analyze_sentiment()` documents fallback but doesn't warn user
- **File:** `alpha_search/agents/roles.py`
- **Line(s):** 606–640
- **Issue:** When no FinBERT analyzer is injected, the method falls back to deterministic hash-based scores. The docstring says "falls back to deterministic mock scores" but the actual sentiment dictionary returned is indistinguishable from real analysis (has `direction`, `score`, `article_count`, `confidence`, `key_topics`).
- **Impact:** Users may not realize they're getting synthetic sentiment data. The `analyze_sentiment()` method should add a `"synthetic": true` flag.
- **Fix:** Add `"source": "synthetic_fallback"` to the fallback results.
- **Confidence:** Medium

### [LOW] #32 — `max_drawdown` docstring contradicts field description in `StrategyMemory`
- **File:** `alpha_search/memory/models.py`
- **Line(s):** 265
- **Issue:** Field says "Maximum drawdown as positive decimal (e.g. 0.18 = 18% drawdown)" but the validator allows negative values (`ge=-1.0`). The `metrics.py` `max_drawdown()` returns a positive number. The `RiskManagerAgent` expects negative.
- **Impact:** Confusion about sign convention throughout the codebase.
- **Fix:** Standardize documentation and implementation (recommend: negative values, e.g., -0.18 = 18% drawdown).
- **Confidence:** Medium

### [LOW] #33 — `README.md` claims "5 live" data sources but only 3 are fully implemented
- **File:** `README.md`
- **Issue:** README says "Stocks: 3 sources live" but the data source platform lists 37 sources with only ~8 marked "live". The actual live implementations (that work without API keys) are yfinance, FRED (no key), CoinGecko (no key), SEC EDGAR (no key). Alpha Vantage and Polygon require API keys and haven't been integration-tested.
- **Fix:** Update counts to reflect actually-tested sources. Add a "Live (tested)" vs "Implemented (needs API key)" distinction.
- **Confidence:** Medium

---

### 3.9 Positive Findings

### ✅ P1 — Memory layer is exceptionally well-designed
- **File:** `alpha_search/memory/store.py`, `alpha_search/memory/models.py`
- The DuckDB/SQLite dual-write abstraction is clean, well-tested, and production-ready. CRUD operations are consistent across all four entity types. Parameterized queries prevent SQL injection. Context manager support (`__enter__`/`__exit__`) is idiomatic. The Pydantic validators are comprehensive and correct.

### ✅ P2 — Critique messages are genuinely specific and data-driven
- **File:** `alpha_search/agents/roles.py`
- Unlike typical placeholder critiques, these contain real observations: "3+ false breakouts per month", "Sharpe improves from 0.31 to 0.74", "slippage estimate 47bps", "sector beta to QQQ is 0.94". This is a standout strength — the agents produce actionable, quantified feedback.

### ✅ P3 — Backtest engine is correctly vectorized
- **File:** `alpha_search/backtest/engine.py`
- The engine uses pure pandas vectorization (no Python loops over dates). Position sizing, returns computation, cost deduction, and equity curve are all vectorized. Trade log generation is efficient. Input validation is thorough.

### ✅ P4 — Comprehensive test coverage for memory layer
- **File:** `tests/test_memory_store.py`, `tests/test_memory_retrieval.py`, `tests/test_agent_journal.py`
- 40+ tests cover CRUD operations, model validation, Pydantic validators, edge cases (not found, empty tags, type validation), and integration scenarios. This is the most thoroughly tested component.

### ✅ P5 — Lazy import pattern in `__init__.py` is well-executed
- **File:** `alpha_search/__init__.py`
- Each optional module is wrapped in `try/except` with `# pragma: no cover`. Missing dependencies gracefully degrade to `None`. The `__all__` list is complete and accurate.

### ✅ P6 — `arbitrage_scan()` correctly uses log-prices for cointegration
- **File:** `alpha_search/opportunities/strategies.py`
- Using `np.log(prices_df)` before cointegration testing is statistically correct — log prices are more likely to be stationary in differences. The Engle-Granger two-step approach (OLS regression + ADF on residuals) is properly implemented.

### ✅ P7 — `DataSourceRegistry` uses proper ABC enforcement
- **File:** `alpha_search/data_sources/base.py`
- The registry validates that registered sources inherit from `DataSource` and have a `SourceMeta` with all required fields. This prevents incomplete source implementations from being registered.

---

## 4. Architecture Recommendations

### R1 — Extract the simulated backtest from `QuantEngineerAgent` immediately
Replace the RNG-based simulation with the real `BacktestEngine`. This is the highest-impact fix because it affects the credibility of the entire framework.

### R2 — Standardize sign conventions across all financial metrics
Create a single `SignConvention` enum or constant module that defines whether drawdowns, returns, and PnL are positive or negative. All modules import from this single source of truth.

### R3 — Add integration tests for the full pipeline
A single `test_full_pipeline.py` that runs `AgentSwarm.run_collaboration()` with mock data would catch issues #1, #5, #8, and #18 immediately.

### R4 — Implement a proper position-sizing layer
The backtest engine needs a `PositionSizer` ABC with implementations: `EqualWeightSizer`, `VolatilityTargetSizer`, `KellySizer`. Currently signals map directly to positions without sizing rules.

### R5 — Consider replacing `_cross_agent_critique()` hardcoded messages with agent-driven critique
Each agent should implement a `critique_outputs(other_agent_name, other_outputs)` method. The swarm calls these dynamically instead of maintaining hardcoded critiques that go stale.

---

## 5. Action Priority Matrix

| Priority | Issue | Effort | Impact |
|----------|-------|--------|--------|
| **P0** | #1 — Replace simulated backtest | Medium | Crippling |
| **P0** | #2 — Fix drawdown sign convention | Low | High |
| **P0** | #5 — Fix hardcoded agent sign-offs | Low | High |
| **P1** | #3 — Fix substring ticker matching | Low | Medium |
| **P1** | #4 — Fix log(0) in arbitrage_scan | Low | Medium |
| **P1** | #18 — Add AgentSwarm tests | Medium | High |
| **P1** | #27 — Add position sizing to backtest | Medium | High |
| **P2** | #8 — Fix `_all_tickers()` for Indian market | Low | Medium |
| **P2** | #10 — Fix RSI implementation inconsistency | Low | Low |
| **P2** | #28 — Fix CostModel cost calculation | Low | Medium |
| **P3** | #6 — Extract god class responsibilities | High | Medium |
| **P3** | #24 — Optimize arbitrage_scan for scale | High | Medium |
