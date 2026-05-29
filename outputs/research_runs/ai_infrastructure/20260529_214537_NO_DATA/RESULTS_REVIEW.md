# Alpha Search — AI Infrastructure Research Results Review

> **STATUS: NO RESULTS — DATA FETCH BLOCKED IN THIS ENVIRONMENT**
>
> This run could not produce strategy results because the execution
> environment blocks outbound requests to Yahoo Finance
> (`HTTP Error 403: Host not in allowlist`). Per the pipeline's integrity
> rules, **no synthetic data was substituted and no metrics were fabricated.**
> There is therefore nothing to optimize, tune, or report as alpha.

---

## 1. Run Configuration

| Setting | Value |
|---|---|
| Command | `python scripts/run_ai_infra_research.py --period 5y --interval 1d --cost-bps 10 --slippage-bps 10 --top-n 5 --json-summary` |
| Period | 5y |
| Interval | 1d |
| Commission | 10 bps one-way |
| Slippage | 10 bps one-way |
| top_n | 5 |
| long_only | False |
| Primary benchmark | SOXX |
| rf | 0.0 (no FRED) |
| Run timestamp (UTC) | 2026-05-29T21:45:37Z |
| Exit code | 1 (clean failure) |

## 2. Universe Tested (requested)

With `--top-n 5`, the requested tradable universe was the first 5 symbols:
`NVDA, AMD, AVGO, TSM, QCOM`
plus 4 benchmarks: `SOXX, SMH, QQQ, SPY`.

**0 of these were actually retrieved** (see §4).

## 3. Data Source

Yahoo Finance (`yfinance` 1.3.0), real OHLCV only. No synthetic fallback,
no FRED price data. This is by design.

## 4. Skipped / Failed Symbols

**All 9 requested tickers failed to download.** yfinance reported, for every host:

```
HTTP Error 403: Host not in allowlist
Failed to get ticker '<SYM>' reason: Expecting value: line 1 column 1 (char 0)
9 Failed downloads:
['NVDA','SMH','SPY','SOXX','QQQ','TSM','AVGO']: AttributeError("'Response' object has no attribute 'get'")
['QCOM','AMD']: TypeError("argument of type 'NoneType' is not iterable")
```

Root cause: the sandbox network proxy does not allow Yahoo Finance data
endpoints (`query1/query2.finance.yahoo.com`). A raw TCP handshake to the host
succeeds, but the HTTP layer returns 403, so yfinance receives empty/None
responses. The validator then correctly saw **0 valid bars** for every symbol
and refused to continue.

Pipeline behaviour was correct:
- Each failure was logged individually.
- No data was fabricated to fill the gap.
- The run aborted with `"No valid symbols after data validation"`.

## 5. Strategy Results Table

**None.** No strategy was backtested because no price data was available.
No `strategy_results_summary.csv` was written (`output_dir: null`).

| Strategy | Net Sharpe | Max DD | Ann. Return | Verdict |
|---|---|---|---|---|
| Cross-sectional momentum (primary) | — (no data) | — | — | no_results |
| Trend following | — (no data) | — | — | no_results |
| Mean reversion | — (no data) | — | — | no_results |
| Donchian breakout | — (no data) | — | — | no_results |

## 6. Benchmark Comparison

**None.** SOXX / SMH / QQQ / SPY could not be downloaded either.
No benchmark Sharpe, return, or drawdown can be reported.

## 7. Best Strategy

Undetermined — no strategy executed.

## 8. Did Any Strategy Reach Sharpe 2 After Costs?

**No.** Sharpe 2 was **not** achieved — and could not even be evaluated,
because zero strategies ran. This is reported honestly: there is no evidence
of any alpha from this run, positive or negative.

## 9. Agent Review Summary

The agent review layer was not reached. The pipeline aborts at the
data-validation gate (before the QuantEngineer/RiskManager/Research stages)
when no symbol has valid bars. No `agent_review.md` was produced.

## 10. Research Conclusion

This is an **infrastructure/environment outcome, not a research finding.**

- The code is correct and validated (compile clean; 104 unit tests pass on
  deterministic fixtures with no network).
- The pipeline honoured every integrity rule under failure: real-data-only,
  no fabrication, explicit per-symbol failure logging, clean abort.
- **No claim about AI-infra/semiconductor alpha can be made from this run.**
  To get real results, the pipeline must run somewhere Yahoo Finance is
  reachable (e.g. Google Colab, or a local machine with open egress).

## 11. Limitations

- **Hard limitation here:** no market-data egress → zero real data.
- Even when data is available, the design carries known caveats:
  survivorship bias (only symbols with full history enter tercile selection),
  rf = 0 (overstates long-only Sharpe in a high-rate regime), no market-impact
  model beyond linear bps costs, single historical period, adjusted-close
  reconstruction risk.

## 12. Recommended Next Experiment

1. **Re-run where Yahoo Finance is reachable.** Use the Colab notebook
   `notebooks/02_ai_infrastructure_alpha_research_colab.ipynb`, or run the CLI
   on a host with open egress:
   ```
   python scripts/run_ai_infra_research.py --period 5y --interval 1d \
     --cost-bps 10 --slippage-bps 10 --top-n 5 --json-summary
   ```
2. **Or supply local OHLCV** (offline path) so the pipeline can run air-gapped
   — feed pre-downloaded CSVs instead of live yfinance.
3. Only after a successful **real-data** run should strategy parameters,
   walk-forward validation, or regime filters be considered. Do not tune
   anything until there is real output to evaluate.

---

_Research only. Not investment advice. This document records a run that
produced no tradable data; it intentionally reports no performance numbers._
