# Alpha Search GitHub Organization Structure

This document describes the recommended multi-repository structure for the Alpha Search project on GitHub.

**Organization:** `https://github.com/alpha-search`
**Contact:** team@alpha-search.io

---

## Overview

The Alpha Search project is organized into **6 repositories** to promote modularity, separation of concerns, and independent release cycles. Each repository has a clear purpose, ownership boundary, and contribution workflow.

```
alpha-search/                          GitHub Organization
├── alpha-search/                      Main product repository
├── alpha-search-docs/                 Documentation site
├── alpha-search-strategy-lab/         Example strategies and research notebooks
├── alpha-search-market-data/          Data provider extensions
├── alpha-search-agents/               AI agent definitions and skills
└── alpha-search-examples/             Community examples and integrations
```

---

## 1. `alpha-search` — Main Product Repository

**Purpose:** Core engine, scanners, UI, API, and CLI. This is the primary repository that users install.

**URL:** `github.com/alpha-search/alpha-search`

**PyPI Package:** `alpha-search`

### README Outline

```markdown
# Alpha Search

> Algorithmic Trading & Quantitative Analysis Platform

## What is Alpha Search?

Alpha Search is an open-source Python platform for algorithmic trading, 
quantitative analysis, and AI-powered market research. It combines 
technical indicators, sentiment analysis, and multi-agent systems 
into a unified, extensible framework.

## Features

- Multi-strategy backtesting engine
- Real-time opportunity scanner
- Sentiment analysis pipeline
- AI agent orchestration
- Streamlit-based trading dashboard
- Indian and US market support

## Quick Start

pip install alpha-search
alpha-search --init
alpha-search scan --universe NIFTY50

## Documentation

Full docs: https://docs.alpha-search.io

## Contributing

See CONTRIBUTING.md

## License

Apache 2.0
```

### Directory Structure

```
alpha-search/
├── .github/
│   ├── workflows/           # CI/CD (test, lint, typecheck, release)
│   ├── ISSUE_TEMPLATE/      # Issue templates
│   └── PULL_REQUEST_TEMPLATE.md
├── alpha_search/                # Main package
│   ├── __init__.py
│   ├── __main__.py          # CLI entry point
│   ├── cli.py               # Command-line interface
│   ├── config.py            # Configuration management
│   ├── constants.py         # Constants and enums
│   ├── exceptions.py        # Custom exceptions
│   ├── engine/              # Backtesting engine
│   │   ├── __init__.py
│   │   ├── core.py
│   │   ├── portfolio.py
│   │   └── execution.py
│   ├── scanner/             # Opportunity scanner
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── technical.py
│   │   └── divergence.py
│   ├── data/                # Data providers (core)
│   │   ├── __init__.py
│   │   ├── base.py          # Abstract data provider
│   │   ├── cache.py         # Local caching
│   │   └── yahoo.py         # Yahoo Finance provider
│   ├── strategies/          # Built-in strategies
│   │   ├── __init__.py
│   │   ├── base.py          # Strategy base class
│   │   ├── mean_reversion/
│   │   ├── momentum/
│   │   └── options/
│   ├── indicators/          # Technical indicators
│   │   ├── __init__.py
│   │   ├── trend.py
│   │   ├── momentum.py
│   │   ├── volatility.py
│   │   └── volume.py
│   ├── sentiment/           # Sentiment analysis
│   │   ├── __init__.py
│   │   ├── base.py
│   │   └── pipeline.py
│   ├── agents/              # Agent framework (core)
│   │   ├── __init__.py
│   │   ├── base.py
│   │   └── orchestrator.py
│   ├── risk/                # Risk management
│   │   ├── __init__.py
│   │   ├── position_sizing.py
│   │   └── metrics.py
│   ├── ui/                  # Streamlit UI components
│   │   ├── __init__.py
│   │   ├── app.py           # Main app entry
│   │   ├── dashboard.py
│   │   └── components/
│   ├── api/                 # REST API (future)
│   │   ├── __init__.py
│   │   └── routes.py
│   └── utils/               # Shared utilities
│       ├── __init__.py
│       ├── logging.py
│       └── validators.py
├── tests/                   # Test suite
│   ├── conftest.py
│   ├── unit/
│   └── integration/
├── docs/                    # Documentation source
├── scripts/                 # Development scripts
├── pyproject.toml           # Project metadata, deps, tool config
├── CONTRIBUTING.md
├── CODE_OF_CONDUCT.md
├── SECURITY.md
├── GOVERNANCE.md
├── LICENSE
└── README.md
```

### Branch Strategy

| Branch | Purpose | Protection |
|--------|---------|------------|
| `main` | Production-ready code | Require PR + 1 review + CI pass |
| `develop` | Integration branch for next release | Require PR + CI pass |
| `release/vX.Y.Z` | Release preparation | Restricted to maintainers |
| `feat/*` | Feature branches | Delete after merge |
| `fix/*` | Bug fix branches | Delete after merge |

---

## 2. `alpha-search-docs` — Documentation Site

**Purpose:** Comprehensive documentation, tutorials, API reference, and blog. Built with MkDocs/Material.

**URL:** `github.com/alpha-search/alpha-search-docs`

**Published at:** `https://docs.alpha-search.io`

### README Outline

```markdown
# Alpha Search Documentation

This repository contains the source for the Alpha Search documentation site.

## Local Development

pip install mkdocs-material
mkdocs serve

## Contributing

See the main repo's CONTRIBUTING.md. Documentation improvements are welcome!
```

### Directory Structure

```
alpha-search-docs/
├── docs/
│   ├── index.md                    # Landing page
│   ├── getting-started/
│   │   ├── installation.md
│   │   ├── quickstart.md
│   │   └── configuration.md
│   ├── user-guide/
│   │   ├── engine.md
│   │   ├── scanner.md
│   │   ├── strategies.md
│   │   ├── data-providers.md
│   │   ├── sentiment.md
│   │   ├── risk-management.md
│   │   └── dashboard.md
│   ├── tutorials/
│   │   ├── first-strategy.md
│   │   ├── backtesting.md
│   │   ├── scanning-nifty50.md
│   │   └── sentiment-analysis.md
│   ├── api-reference/              # Auto-generated
│   ├── strategies/
│   │   ├── mean-reversion.md
│   │   ├── momentum.md
│   │   └── options.md
│   ├── development/
│   │   ├── contributing.md
│   │   ├── architecture.md
│   │   └── changelog.md
│   ├── blog/                       # Release notes, community highlights
│   └── assets/
│       ├── images/
│       └── diagrams/
├── mkdocs.yml                      # MkDocs configuration
├── requirements.txt
├── .github/workflows/publish.yml   # Auto-deploy to GitHub Pages
├── README.md
└── LICENSE
```

### Branch Strategy

| Branch | Purpose |
|--------|---------|
| `main` | Live documentation |
| `draft/*` | Work-in-progress pages |

### Deployment

- Every push to `main` triggers deployment to `docs.alpha-search.io`
- API reference is auto-generated from `alpha-search` source code

---

## 3. `alpha-search-strategy-lab` — Example Strategies and Notebooks

**Purpose:** Curated collection of trading strategies, research notebooks, and educational materials. Community members share and discuss strategies here.

**URL:** `github.com/alpha-search/alpha-search-strategy-lab`

### README Outline

```markdown
# Alpha Search Strategy Lab

A collection of example trading strategies, research notebooks, and 
educational materials for Alpha Search.

## Strategies

| Strategy | Type | Market | Status |
|----------|------|--------|--------|
| RSI Mean Reversion | Mean Reversion | NSE | Tested |
| MACD Momentum | Momentum | NSE/US | Tested |
| Iron Condor Screener | Options | NSE | Experimental |

## Quick Start

pip install alpha-search
jupyter lab

## Contributing Strategies

See CONTRIBUTING.md for submission guidelines.
```

### Directory Structure

```
alpha-search-strategy-lab/
├── strategies/
│   ├── mean_reversion/
│   │   ├── rsi_mean_reversion/
│   │   │   ├── strategy.py          # Strategy implementation
│   │   │   ├── config.yaml          # Strategy configuration
│   │   │   ├── backtest.ipynb       # Backtest notebook
│   │   │   ├── results/             # Backtest results
│   │   │   └── README.md            # Strategy documentation
│   │   └── bollinger_bands/
│   ├── momentum/
│   │   ├── macd_crossover/
│   │   └── trend_following/
│   ├── options/
│   │   ├── iron_condor/
│   │   └── straddle_screener/
│   ├── statistical_arbitrage/
│   │   └── pair_trading/
│   └── ml_based/
│       └── regime_detection/
├── research/
│   ├── notebooks/                   # Educational notebooks
│   │   ├── 01_introduction.ipynb
│   │   ├── 02_technical_indicators.ipynb
│   │   ├── 03_backtesting.ipynb
│   │   ├── 04_sentiment_analysis.ipynb
│   │   └── 05_risk_management.ipynb
│   └── papers/                      # Relevant research papers
├── data_samples/                    # Small sample datasets for demos
├── utils/
│   └── notebook_helpers.py
├── requirements.txt
├── CONTRIBUTING.md
├── README.md
└── LICENSE
```

### Branch Strategy

| Branch | Purpose |
|--------|---------|
| `main` | Reviewed, tested strategies |
| `contrib/*` | Community-submitted strategies under review |

---

## 4. `alpha-search-market-data` — Data Provider Extensions

**Purpose:** Additional data provider implementations beyond the core Yahoo Finance support. Community members add exchanges, data vendors, and alternative data sources.

**URL:** `github.com/alpha-search/alpha-search-market-data`

**PyPI Package:** `alpha-search-market-data`

### README Outline

```markdown
# Alpha Search Market Data Providers

Extended data provider integrations for Alpha Search.

## Available Providers

| Provider | Markets | Real-time | Status |
|----------|---------|-----------|--------|
| NSE India | NSE | No | Stable |
| Alpaca | US | Yes | Beta |
| Binance | Crypto | Yes | Beta |
| Polygon.io | US | Yes | Alpha |

## Installation

pip install alpha-search-market-data

## Contributing a Provider

See CONTRIBUTING.md for the provider interface specification.
```

### Directory Structure

```
alpha-search-market-data/
├── alpha_search_market_data/
│   ├── __init__.py
│   ├── nse/                     # NSE India official data
│   │   ├── __init__.py
│   │   ├── provider.py
│   │   └── utils.py
│   ├── alphavantage/            # Alpha Vantage API
│   │   ├── __init__.py
│   │   └── provider.py
│   ├── alpaca/                  # Alpaca Markets
│   │   ├── __init__.py
│   │   ├── provider.py
│   │   └── websocket.py
│   ├── binance/                 # Binance (crypto)
│   │   ├── __init__.py
│   │   ├── provider.py
│   │   └── websocket.py
│   ├── polygon/                 # Polygon.io
│   │   ├── __init__.py
│   │   └── provider.py
│   └── base.py                  # Shared provider utilities
├── tests/
│   ├── conftest.py
│   └── providers/
├── examples/                    # Usage examples per provider
├── docs/
│   └── provider-interface.md    # Spec for implementing new providers
├── pyproject.toml
├── requirements.txt
├── CONTRIBUTING.md
├── README.md
└── LICENSE
```

### Branch Strategy

Same as main repo: `main` + feature/fix branches.

---

## 5. `alpha-search-agents` — AI Agent Definitions and Skills

**Purpose:** AI agent definitions, skill modules, prompts, and orchestration recipes. Separated so agent development can iterate independently from the core platform.

**URL:** `github.com/alpha-search/alpha-search-agents`

**PyPI Package:** `alpha-search-agents`

### README Outline

```markdown
# Alpha Search Agents

AI agent definitions, skills, and orchestration recipes for Alpha Search.

## Available Agents

| Agent | Purpose | Status |
|-------|---------|--------|
| TechnicalAnalyst | Pattern recognition and signal scoring | Stable |
| SentimentAnalyzer | News and social sentiment analysis | Beta |
| RiskManager | Position sizing and risk assessment | Beta |
| PortfolioOptimizer | Portfolio construction and rebalancing | Alpha |

## Installation

pip install alpha-search-agents

## Quick Start

from alpha_search_agents import TechnicalAnalyst

agent = TechnicalAnalyst()
signals = agent.analyze(symbols=["RELIANCE.NS"])
```

### Directory Structure

```
alpha-search-agents/
├── alpha_search_agents/
│   ├── __init__.py
│   ├── agents/                  # Agent implementations
│   │   ├── __init__.py
│   │   ├── technical_analyst.py
│   │   ├── sentiment_analyzer.py
│   │   ├── risk_manager.py
│   │   ├── portfolio_optimizer.py
│   │   └── market_researcher.py
│   ├── skills/                  # Reusable skill modules
│   │   ├── __init__.py
│   │   ├── data_retrieval.py
│   │   ├── indicator_calculation.py
│   │   ├── sentiment_scoring.py
│   │   └── risk_assessment.py
│   ├── prompts/                 # LLM prompt templates
│   │   ├── __init__.py
│   │   ├── analysis.j2
│   │   ├── recommendation.j2
│   │   └── risk_evaluation.j2
│   ├── memory/                  # Vector memory implementations
│   │   ├── __init__.py
│   │   ├── base.py
│   │   └── chroma.py
│   ├── orchestration/           # Multi-agent workflows
│   │   ├── __init__.py
│   │   ├── sequential.py        # Sequential agent chains
│   │   ├── parallel.py          # Parallel agent execution
│   │   └── consensus.py         # Multi-agent consensus
│   └── utils/
│       └── __init__.py
├── tests/
├── notebooks/                   # Agent tutorials and demos
│   ├── 01_single_agent.ipynb
│   ├── 02_multi_agent.ipynb
│   └── 03_custom_agent.ipynb
├── docs/
│   └── agent-development.md
├── pyproject.toml
├── requirements.txt
├── CONTRIBUTING.md
├── README.md
└── LICENSE
```

### Branch Strategy

Same as main repo: `main` + feature/fix branches.

---

## 6. `alpha-search-examples` — Community Examples and Integrations

**Purpose:** Community-contributed examples, integrations, tutorials, and use-case demonstrations. Lower barrier to entry than strategy-lab; accepts broader contributions.

**URL:** `github.com/alpha-search/alpha-search-examples`

### README Outline

```markdown
# Alpha Search Community Examples

Real-world examples, integrations, and use cases from the Alpha Search community.

## Categories

- **Brokers**: Integration with Zerodha, Angel One, Upstox
- **Notifications**: Slack, Telegram, email alerts
- **Scheduling**: Cron, systemd, cloud schedulers
- **Cloud**: AWS, GCP, Azure deployment examples
- **Dashboards**: Custom Streamlit and Gradio dashboards

## Contributing

Share your Alpha Search setup! See CONTRIBUTING.md.
```

### Directory Structure

```
alpha-search-examples/
├── integrations/
│   ├── brokers/
│   │   ├── zerodha/               # Kite Connect integration
│   │   ├── angel_one/
│   │   ├── upstox/
│   │   └── icici_direct/
│   ├── notifications/
│   │   ├── telegram_bot/
│   │   ├── slack_webhook/
│   │   └── email_alerts/
│   ├── cloud/
│   │   ├── aws/                   # EC2, Lambda deployment
│   │   ├── gcp/
│   │   └── azure/
│   └── storage/
│       ├── postgresql/
│       └── s3/
├── dashboards/
│   ├── advanced_scanner/          # Custom scanner UI
│   ├── portfolio_tracker/
│   └── options_analyzer/
├── scheduling/
│   ├── cron/                      # Cron job examples
│   ├── systemd/                   # Linux service setup
│   └── docker/                    # Container scheduling
├── tutorials/
│   ├── retail_investor_guide.md
│   ├── smallcase_integration.md
│   └── mutual_fund_screener.md
├── community/
│   └── showcases/                 # Community member showcases
├── README.md
├── CONTRIBUTING.md
└── LICENSE
```

### Branch Strategy

| Branch | Purpose |
|--------|---------|
| `main` | Approved examples |
| Direct PRs accepted for simple additions |

---

## Repository Comparison

| Repository | Language | Tests | PyPI | Auto-deploy |
|------------|----------|-------|------|-------------|
| `alpha-search` | Python | Full suite | Yes | PyPI on tag |
| `alpha-search-docs` | Markdown | Link check | No | GitHub Pages |
| `alpha-search-strategy-lab` | Python/Notebook | Smoke tests | No | — |
| `alpha-search-market-data` | Python | Per-provider | Yes | PyPI on tag |
| `alpha-search-agents` | Python | Unit + integration | Yes | PyPI on tag |
| `alpha-search-examples` | Mixed | None | No | — |

## Cross-Repository Workflow

### Dependent Changes

When a change spans multiple repositories:

1. Open PRs in each repository with cross-references:
   ```
   Depends on: alpha-search/alpha-search-market-data#42
   ```
2. Merge dependencies first (bottom-up order):
   - `alpha-search-market-data` → `alpha-search-agents` → `alpha-search`
3. Update version pins in dependent repositories

### Issue Routing

| Issue Topic | Repository |
|-------------|------------|
| Engine bug, scanner error, UI issue | `alpha-search` |
| Missing data provider, data accuracy | `alpha-search-market-data` |
| Agent behavior, LLM prompt | `alpha-search-agents` |
| Strategy logic, backtest result | `alpha-search-strategy-lab` |
| Documentation typo, unclear guide | `alpha-search-docs` |
| Broker integration, deployment help | `alpha-search-examples` |

### Release Coordination

Major releases that require coordinated updates across repositories use a GitHub Discussion in the `alpha-search` repository to track the release checklist.

---

## Contact

For questions about the organization structure:

- **Email:** team@alpha-search.io
- **Discussions:** [github.com/alpha-search/alpha-search/discussions](https://github.com/alpha-search/alpha-search/discussions)
