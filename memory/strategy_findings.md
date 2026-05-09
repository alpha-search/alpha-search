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

