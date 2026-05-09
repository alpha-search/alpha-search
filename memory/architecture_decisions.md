# Architecture Decisions

Key architecture and design decisions with rationale and importance scores.

---

### [2025-01-10 08:15:00 UTC] Project Coordinator

**Decision:** Alpha Search positioned as global multi-asset, not India-only

**Rationale:** While the project started with Indian equity data (NIFTY), the
architecture is designed for global multi-asset from day one. Using YFinance
for global equities and Binance for crypto ensures we're not locked into a
single geography or asset class. Future providers (forex, commodities) can
be added via the `BaseDataProvider` interface.

**Importance:** 1.0/1.0

Tags: positioning, scope, global

---

### [2025-01-10 08:20:00 UTC] Project Coordinator

**Decision:** Stock Opportunity Agent renamed to Global Market Opportunity Agent

**Rationale:** The original name implied a narrow focus on stock picking. The
renamed agent scans across all supported asset classes (equities, crypto) and
strategy types (mean reversion, momentum, pairs). The name change better
reflects the broadened scope.

**Importance:** 0.7/1.0

Tags: naming, agents, scope

---

### [2025-01-10 08:30:00 UTC] Project Coordinator

**Decision:** MIT license chosen for hedge-fund friendliness

**Rationale:** The MIT license is the most permissive widely-used open-source
license. Proprietary hedge funds and quantitative trading shops can integrate
Alpha Search without disclosing their proprietary modifications. This maximizes
adoption in the target audience. Alternative (GPL) would create friction.

**Importance:** 0.8/1.0

Tags: licensing, legal, hedge-fund

---

### [2025-01-10 09:45:00 UTC] Architect

**Decision:** Vectorized backtesting over event-driven (performance)

**Rationale:** Event-driven backtesting is more flexible but significantly
slower. For a research-oriented platform where strategies need rapid
iteration, vectorized backtesting (NumPy/pandas) provides 100-1000x speedup.
The trade-off is acceptable because:

1. Primary use case is strategy research, not HFT simulation
2. Cost models can be layered on top of vectorized results
3. Walk-forward analysis is still supported for out-of-sample validation

**Importance:** 0.9/1.0

Tags: backtesting, performance, vectorized

---

### [2025-01-10 10:00:00 UTC] Architect

**Decision:** DuckDB for local-first data (no cloud dependency for MVP)

**Rationale:** DuckDB provides analytical query performance comparable to
cloud data warehouses but runs entirely locally with zero external
dependencies. This aligns with the local-first design principle:

- Data stays on the user's machine
- No API keys or cloud accounts required
- SQLite fallback ensures portability across all platforms
- File-based storage makes backup/versioning trivial (git-friendly)

**Importance:** 0.9/1.0

Tags: database, local-first, duckdb, data

---

*New entries are appended automatically as architecture decisions are logged.*
### [2026-05-08 23:59:56 UTC] architect

**Decision:** Use vectorized backtesting over event-driven

**Rationale:** 100-1000x speedup for strategy research iteration

**Importance:** 0.9/1.0

Tags: backtesting, performance
---

