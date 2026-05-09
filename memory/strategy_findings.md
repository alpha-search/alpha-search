# Strategy Findings

Backtest results and evaluation verdicts for all strategies tested.

---

### [2025-01-10 15:30:00 UTC] NIFTY Bank Pair Mean Reversion

**Verdict:** ❌ rejected
**Type:** pairs

**Rationale:** Strategy rejected due to maximum drawdown exceeding the
acceptable threshold. While the cointegration test showed a strong
statistical relationship between the selected banking pairs, the walk-forward
analysis revealed that drawdowns during market stress periods were too severe
for the risk appetite of the target portfolio.

**Metrics:**
- sharpe: -0.2341
- max_drawdown: -0.1835
- win_rate: 0.4231
- avg_trade: -0.0082
- total_return: -0.1243

**Parameters:**
- lookback_window: 20
- entry_zscore: 2.0
- exit_zscore: 0.5
- stop_loss_zscore: 3.5

**Tags:** nifty, banking, mean-reversion, rejected

---

*New entries are appended automatically as strategies are evaluated.*
### [2026-05-08 23:59:56 UTC] NIFTY Bank Pair Mean Reversion

**Verdict:** ❌ rejected
**Type:** mean_reversion | **Market:** global | **Asset:** equity

**Hypothesis:** Banking pairs revert to mean after deviation
**Result Summary:** Drawdown exceeded threshold during stress periods

**Metrics:**
- sharpe: -0.2300
- max_drawdown: -18.00%
- total_return: -0.1200
- win_rate: 0.4200

**Rejection Reason:** Maximum drawdown exceeds acceptable threshold

**Lessons Learned:** Avoid NIFTY banking pairs during high volatility

---

### [2026-05-09 02:47:29 UTC] Momentum Strategy

**Verdict:** ❌ rejected
**Type:** momentum | **Market:** Global (US, India, Crypto) | **Asset:** multi_asset

**Hypothesis:** Stocks with strong recent price momentum will continue trending in the same direction over the next 1–4 weeks.
**Result Summary:** Average return: 3.50%, Sharpe: 0.02, Max DD: 10.62%

**Metrics:**
- sharpe: 0.0249
- max_drawdown: 10.62%
- total_return: 0.0350

**Rejection Reason:** Average Sharpe too low (0.02) for live deployment.

**Lessons Learned:** Synthetic data results. Need validation on real data before any deployment.

---

### [2026-05-09 02:47:29 UTC] Mean Reversion Strategy

**Verdict:** ❌ rejected
**Type:** mean_reversion | **Market:** Global (US, India, Crypto) | **Asset:** multi_asset

**Hypothesis:** Stocks that deviate significantly from their rolling mean will revert toward the mean over the short term.
**Result Summary:** Average return: -10.07%, Sharpe: -1.51, Max DD: 13.89%

**Metrics:**
- sharpe: -1.5087
- max_drawdown: 13.89%
- total_return: -0.1007

**Rejection Reason:** Average Sharpe too low (-1.51) for live deployment.

**Lessons Learned:** Synthetic data results. Need validation on real data before any deployment.

---

### [2026-05-09 02:47:29 UTC] Arbitrage Strategy

**Verdict:** ❌ rejected
**Type:** arbitrage | **Market:** Global (US, India, Crypto) | **Asset:** multi_asset

**Hypothesis:** Cointegrated / highly-correlated pairs will maintain a stationary spread, allowing profitable mean-reversion trades when the spread deviates from its equilibrium.
**Result Summary:** Average return: 0.15%, Sharpe: -0.11, Max DD: 12.48%

**Metrics:**
- sharpe: -0.1111
- max_drawdown: 12.48%
- total_return: 0.0015

**Rejection Reason:** Average Sharpe too low (-0.11) for live deployment.

**Lessons Learned:** Synthetic data results. Need validation on real data before any deployment.

---

