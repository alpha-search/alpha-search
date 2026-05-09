# Project Memory

High-level project direction and strategic positioning decisions.

---

### Project Positioning

- **Alpha Search** is positioned as a **global multi-asset** quantitative trading
  platform — not India-only. Initial data providers include Yahoo Finance
  (global equities) and Binance (crypto), with the architecture designed to
  support additional asset classes and regions.

- The **Stock Opportunity Agent** was renamed to the **Global Market
  Opportunity Agent** to reflect the expanded scope beyond Indian equities.

### Licensing

- **MIT license** chosen for hedge-fund friendliness. Proprietary funds can
  use, modify, and integrate the code without disclosure obligations.

### Technology Decisions

| Decision | Rationale |
|----------|-----------|
| Vectorized backtesting | Performance — NumPy/pandas vectorized operations over event-driven loop; enables rapid strategy iteration |
| DuckDB for local-first data | No cloud dependency for MVP — everything runs locally, data stays on user's machine |
| Modular design with ABC interfaces | Clean separation between data providers, signals, backtest engines, and execution — swap implementations without rewriting callers |
| Pydantic models throughout | Type safety + validation at boundaries; models serve as both runtime containers and documentation |
| YFinance + Binance as initial providers | Free tier, no API keys required for basic usage; broad market coverage (equities + crypto) |

### Architecture Principles

1. **Local-first** — no cloud dependency for the MVP
2. **Pluggable** — ABC interfaces for all major components
3. **Fast iteration** — vectorized backtesting for rapid strategy evaluation
4. **Type-safe** — Pydantic models at all boundaries
5. **Dual-write memory** — structured DB + human-readable Markdown for every log entry

---

*This file is maintained by the project coordinator agent and updated as
strategic direction evolves.*
