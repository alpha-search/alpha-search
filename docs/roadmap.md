# Alpha Search Roadmap

This roadmap is organised into three 8-week phases. Milestones are tagged with target versions.

---

## Phase 1 — MVP: Core Engine (Weeks 1-8)

**Target release: v0.2.0**

### Data Layer
- [x] Yahoo Finance provider with OHLCV normalisation
- [x] Binance provider for crypto spot data
- [x] DuckDB cache manager with TTL
- [ ] Provider plugin API (3rd-party providers)
- [ ] Automatic retries with exponential backoff
- [ ] Multi-ticker batch download

### Signals
- [x] Momentum (rate-of-change)
- [x] MA crossover (golden/death cross)
- [x] Z-score mean-reversion
- [x] Ensemble (weighted combination)
- [x] Boolean composition (AND / OR)
- [ ] Bollinger Bands signal
- [ ] RSI signal
- [ ] MACD signal

### Backtest
- [x] Vectorised backtest engine
- [x] Transaction-cost model
- [x] Sharpe / return / drawdown metrics
- [ ] Slippage model (random + volume-based)
- [ ] Short-selling support
- [ ] Rebalancing schedules (daily, weekly, monthly)

### UI
- [x] Streamlit terminal launch
- [ ] Interactive signal builder
- [ ] Real-time price ticker panel
- [ ] Equity-curve and drawdown charts (Plotly)

---

## Phase 2 — Advanced: Alpha & Risk (Weeks 9-16)

**Target release: v0.4.0**

### Sentiment
- [ ] FinBERT integration (`pip install "alpha-search[sentiment]"`)
- [ ] Batch sentiment scoring for news feeds
- [ ] Composite sentiment aggregation (weighted multi-source)
- [ ] Sentiment signal generation (bullish/bearish/neutral)
- [ ] RSS / news-API ingestor

### Portfolio Optimization
- [ ] Mean-variance optimisation (Markowitz)
- [ ] Risk-parity allocation
- [ ] Hierarchical risk parity (HRP)
- [ ] Black-Litterman model
- [ ] Constraints: long-only, sector limits, max position size

### Walk-Forward Validation
- [x] Rolling-window train/test splits
- [x] IS/OOS degradation detection
- [ ] Multiple-comparison correction (Bonferroni, Benjamini-Hochberg)
- [ ] Monte-Carlo permutation tests

### Execution / Paper Trading
- [ ] Paper-trading broker (simulated fills against live feeds)
- [ ] Order types: market, limit, stop-loss
- [ ] Position tracking and P&L reporting
- [ ] Trade journal (entry/exit reasoning)

---

## Phase 3 — Production: Scale & Community (Weeks 17-24)

**Target release: v0.6.0**

### API & Deployment
- [ ] FastAPI REST server (`pip install "alpha-search[api]"`)
- [ ] OpenAPI documentation
- [ ] Docker image (`ghcr.io/alpha-search/alpha-search`)
- [ ] Docker Compose (Alpha Search + DuckDB + optional Redis)
- [ ] Helm chart for Kubernetes

### Community & Ecosystem
- [ ] Alpha Search Hub: shared strategy templates
- [ ] Plugin marketplace (3rd-party signal packs)
- [ ] Discord community server
- [ ] Monthly community calls
- [ ] Blog + tutorial series

### Documentation
- [ ] mkdocs site with API reference
- [ ] 10 end-to-end tutorial notebooks
- [ ] Video quickstart series
- [ ] Contributing guide and Code of Conduct

### Enterprise Features
- [ ] Multi-tenant support
- [ ] Role-based access control (RBAC)
- [ ] Audit logging
- [ ] SLAs and priority support

---

## Release Schedule

| Version | Phase | Target Date | Key Deliverable |
|---|---|---|---|
| v0.1.0 | — | Jan 2025 | Initial open-source release |
| v0.2.0 | Phase 1 | Mar 2025 | Stable data, signals, backtest, UI |
| v0.3.0 | Phase 1 | Apr 2025 | Provider plugins, batch ops |
| v0.4.0 | Phase 2 | May 2025 | Sentiment + portfolio optimisation |
| v0.5.0 | Phase 2 | Jun 2025 | Paper trading + execution |
| v0.6.0 | Phase 3 | Jul 2025 | API + Docker + community hub |
| v1.0.0 | — | Sep 2025 | Production-stable LTS release |

---

## How to Influence the Roadmap

- Open a [GitHub Discussion](https://github.com/alpha-search/alpha-search/discussions) to propose features
- Vote on existing issues with 👍 / 👎 reactions
- Join the community calls (announced on Discord)
- Sponsor development via [GitHub Sponsors](https://github.com/sponsors/alpha-search)
