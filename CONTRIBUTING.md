# Contributing to Alpha Search

Thank you for your interest in contributing to Alpha Search! This document provides guidelines and workflows for contributing to the project. Whether you're fixing a bug, adding a feature, improving documentation, or sharing a trading strategy, your contributions are valuable.

**Contact:** team@alpha-search.io

---

## Table of Contents

- [Getting Started](#getting-started)
- [Development Workflow](#development-workflow)
- [Code Style](#code-style)
- [Testing](#testing)
- [Pull Request Process](#pull-request-process)
- [Issue Reporting](#issue-reporting)
- [Code Review Checklist](#code-review-checklist)
- [Areas Needing Contributors](#areas-needing-contributors)

---

## Getting Started

### Prerequisites

- Python 3.10 or higher
- Git 2.30 or higher
- `make` (optional, for convenience commands)

### Clone and Install

```bash
# 1. Fork the repository on GitHub, then clone your fork
git clone https://github.com/YOUR_USERNAME/alpha-search.git
cd alpha-search

# 2. Create a virtual environment
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# .venv\Scripts\activate  # Windows

# 3. Install in development mode with all dependencies
pip install -e ".[dev]"

# 4. Verify the installation
pytest tests/ -q
python -m alpha_search --version
```

### Development Dependencies

The `[dev]` extra installs:

| Tool | Purpose |
|------|---------|
| `pytest` | Test framework |
| `pytest-cov` | Coverage reporting |
| `pytest-mock` | Mocking utilities |
| `pytest-asyncio` | Async test support |
| `black` | Code formatting |
| `ruff` | Linting and import sorting |
| `mypy` | Static type checking |
| `pre-commit` | Git hooks for quality checks |

### Set Up Pre-Commit Hooks

```bash
pre-commit install
```

This runs `black`, `ruff`, and `mypy` automatically before each commit.

---

## Development Workflow

### Branch Naming

All branches must follow this convention:

| Prefix | Purpose | Example |
|--------|---------|---------|
| `feat/` | New features | `feat/sentiment-pipeline` |
| `fix/` | Bug fixes | `fix/data-cache-race-condition` |
| `docs/` | Documentation | `docs/api-reference` |
| `refactor/` | Code refactoring | `refactor/engine-decoupling` |
| `test/` | Test additions/fixes | `test/backtest-coverage` |
| `chore/` | Maintenance tasks | `chore/dependency-update` |

### Commit Conventions

We follow [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <description>

[optional body]

[optional footer]
```

**Types:**

| Type | Description |
|------|-------------|
| `feat` | New feature |
| `fix` | Bug fix |
| `docs` | Documentation only |
| `style` | Formatting, semicolons, etc. |
| `refactor` | Code change that neither fixes a bug nor adds a feature |
| `perf` | Performance improvement |
| `test` | Adding or correcting tests |
| `chore` | Build process, dependencies, tooling |

**Scopes (examples):**

- `engine`, `scanner`, `data`, `strategy`, `ui`, `api`, `docs`, `deps`

**Examples:**

```
feat(scanner): add RSI divergence detection

Implement RSI-based divergence detection in the opportunity scanner.
Supports bullish and bearish divergences with configurable lookback.

Closes #142
```

```
fix(data): handle rate-limiting for Yahoo Finance provider

Add exponential backoff retry logic for 429 responses.
Default: 3 retries with 1s, 2s, 4s delay.
```

### Development Cycle

1. **Create a branch** from `main`:
   ```bash
   git checkout main
   git pull upstream main
   git checkout -b feat/your-feature-name
   ```

2. **Make changes** with focused, atomic commits.

3. **Run quality checks locally**:
   ```bash
   make lint        # ruff check
   make format      # black + ruff format
   make typecheck   # mypy
   make test        # pytest
   make check       # all of the above
   ```

4. **Push and open a Pull Request**.

---

## Code Style

### Formatting with Black

- Line length: 88 characters
- Target Python version: 3.10+
- Configuration in `pyproject.toml`:

```toml
[tool.black]
line-length = 88
target-version = ['py310', 'py311', 'py312']
include = '\.pyi?$'
extend-exclude = '''
/(
  # directories
  \.eggs
  | \.git
  | \.hg
  | \.mypy_cache
  | \.tox
  | \.venv
  | build
  | dist
)/
'''
```

### Linting with Ruff

Ruff replaces `flake8`, `isort`, `pydocstyle`, and `pyupgrade`. Key rules:

- **E, W**: pycodestyle errors and warnings
- **F**: Pyflakes
- **I**: Import sorting (isort-compatible)
- **N**: PEP 8 naming conventions
- **W**: Pydocstyle conventions
- **UP**: pyupgrade checks
- **B**: flake8-bugbear
- **C4**: flake8-comprehensions
- **SIM**: flake8-simplify

Run: `ruff check .` and `ruff format .`

### Type Hints with mypy

All new code must include type hints. Run `mypy alpha_search/`.

**Requirements:**

- All function parameters must have type annotations
- All function return types must be annotated
- Use `Optional[X]` or `X | None` for nullable values (Python 3.10+)
- Use `from __future__ import annotations` for forward references where needed

**Example:**

```python
from __future__ import annotations

from typing import Sequence
from pathlib import Path

import pandas as pd

from alpha_search.data import MarketData
from alpha_search.models import Signal


def generate_signals(
    data: MarketData,
    symbols: Sequence[str],
    lookback_days: int = 30,
    output_dir: Path | None = None,
) -> list[Signal]:
    """Generate trading signals for the given symbols.

    Parameters
    ----------
    data : MarketData
        Market data provider instance.
    symbols : Sequence[str]
        List of stock symbols to analyze.
    lookback_days : int, default 30
        Number of days of historical data to use.
    output_dir : Path | None
        If provided, save signals to this directory.

    Returns
    -------
    list[Signal]
        Generated trading signals sorted by confidence.
    """
    ...
```

### Docstrings

Use [Google-style docstrings](https://google.github.io/styleguide/pyguide.html#383-functions-and-methods) for all public modules, classes, and functions.

---

## Testing

### Test Framework

We use `pytest` with the following plugins:

| Plugin | Purpose |
|--------|---------|
| `pytest-cov` | Coverage reporting (minimum 70%) |
| `pytest-mock` | `unittest.mock` integration |
| `pytest-asyncio` | Async/await test support |

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage report
pytest --cov=alpha_search --cov-report=term-missing

# Run specific test file
pytest tests/test_scanner.py

# Run specific test
pytest tests/test_scanner.py::test_rsi_divergence

# Run with verbose output
pytest -v

# Run only unit tests (fast)
pytest -m "not integration"

# Run only integration tests
pytest -m integration
```

### Test Organization

```
tests/
├── conftest.py              # Shared fixtures
├── unit/
│   ├── test_engine.py
│   ├── test_scanner.py
│   ├── test_data_providers.py
│   └── test_strategies.py
├── integration/
│   ├── test_live_data.py
│   └── test_end_to_end.py
└── fixtures/
    ├── sample_data.csv
    └── mock_responses/
```

### Writing Tests

- Name tests descriptively: `test_<function>_<scenario>_<expected>`
- Use fixtures in `conftest.py` for shared setup
- Mock external API calls; never hit real services in unit tests
- Use `tmp_path` fixture for file system operations
- Tag slow/integration tests with `@pytest.mark.integration`

**Example:**

```python
import pytest
from unittest.mock import Mock, patch

from alpha_search.scanner import OpportunityScanner
from alpha_search.models import Signal, SignalType


@pytest.fixture
def scanner() -> OpportunityScanner:
    return OpportunityScanner(lookback_days=30)


def test_scanner_detects_bullish_divergence(scanner: OpportunityScanner) -> None:
    """Scanner should detect bullish RSI divergence in uptrend."""
    mock_data = Mock()
    mock_data.get_ohlc.return_value = _load_fixture("bullish_divergence")

    signals = scanner.scan(mock_data, symbols=["RELIANCE.NS"])

    assert len(signals) == 1
    assert signals[0].type == SignalType.BULLISH_DIVERGENCE
    assert signals[0].confidence > 0.7


@pytest.mark.integration
def test_scanner_with_live_data(scanner: OpportunityScanner) -> None:
    """Integration test with real market data (slow)."""
    ...
```

### Coverage Requirements

- **Minimum overall coverage: 70%**
- New code should aim for 80%+ coverage
- Critical paths (engine, risk calculations) should have 90%+
- Coverage is checked in CI; PRs that decrease coverage will be flagged

---

## Pull Request Process

### Before Submitting

1. **Sync with upstream:**
   ```bash
   git fetch upstream
   git rebase upstream/main
   ```

2. **Run the full check suite:**
   ```bash
   make check
   ```

3. **Update documentation** if your change affects user-facing behavior.

4. **Add a changelog entry** under `docs/changelog/` if applicable.

### PR Description

Use the [Pull Request Template](.github/PULL_REQUEST_TEMPLATE.md). A good PR description includes:

- **What** changed and **why**
- Link to related issue(s): `Closes #123`
- **Testing performed** (commands run, scenarios tested)
- **Screenshots** for UI changes
- **Breaking changes** with migration notes

### Review Process

1. All PRs require **at least one review** from a maintainer.
2. CI checks must pass (lint, typecheck, test, coverage).
3. Reviewers will respond within **3 business days**.
4. Address review feedback with additional commits (do not force-push after review starts).
5. Once approved, a maintainer will merge.

### After Merge

- Your contribution will be included in the next release.
- You will be added to the contributors list.

---

## Issue Reporting

### Bug Reports

Use the [Bug Report Template](.github/ISSUE_TEMPLATE/bug_report.md). A good bug report includes:

- **Alpha Search version** (`python -m alpha_search --version`)
- **Python version** and **operating system**
- **Steps to reproduce** the issue
- **Expected behavior** vs **actual behavior**
- **Error messages** and **stack traces** (formatted in code blocks)
- **Minimal reproducible example** (the shorter, the better)

### Feature Requests

Use the [Feature Request Template](.github/ISSUE_TEMPLATE/feature_request.md). Describe:

- The **problem** you're trying to solve
- Your **proposed solution** and how it fits the project
- **Alternative approaches** you've considered
- Whether you're **willing to contribute** the implementation

### Questions and Discussions

For questions, ideas, and general discussion, use [GitHub Discussions](https://github.com/alpha-search/alpha-search/discussions) instead of issues.

---

## Code Review Checklist

Reviewers and contributors should verify:

### Correctness

- [ ] Logic is correct and handles edge cases
- [ ] Error handling is appropriate (no bare `except:`)
- [ ] No security vulnerabilities (no hardcoded secrets, SQL injection risks, etc.)

### Code Quality

- [ ] Code follows the style guide (black, ruff, mypy pass)
- [ ] Functions are focused and reasonably sized
- [ ] Naming is clear and descriptive
- [ ] No unnecessary complexity or duplication

### Testing

- [ ] Tests cover the new functionality
- [ ] Edge cases and error paths are tested
- [ ] Mocking is used appropriately for external dependencies
- [ ] Coverage does not decrease

### Documentation

- [ ] Docstrings are present and accurate
- [ ] README or docs are updated if needed
- [ ] Type hints are complete
- [ ] Changelog entry is added for user-facing changes

### Performance

- [ ] No unnecessary computations or memory allocations
- [ ] DataFrame operations are vectorized where possible
- [ ] No blocking I/O in async contexts

---

## Areas Needing Contributors

We actively welcome contributions in the following areas:

### Data Providers

- **Indian markets**: NSE/BSE real-time data connectors
- **International**: Alpaca, Interactive Brokers, Polygon.io adapters
- **Crypto**: Binance, CoinGecko integrations
- **Alternative data**: News feeds, social sentiment, economic calendars

### Trading Strategies

- Mean reversion and statistical arbitrage strategies
- Momentum and trend-following systems
- Options strategies (spreads, iron condors, etc.)
- Machine learning models (regime detection, signal generation)

### User Interface

- Streamlit dashboard enhancements
- Real-time portfolio visualization
- Risk metric charts and heatmaps
- Mobile-responsive layouts

### Documentation

- Tutorial notebooks for beginners
- API reference documentation
- Strategy development guides
- Video tutorials and walkthroughs

### Core Platform

- Performance optimizations for large universes
- Additional technical indicators
- Risk management modules
- Paper trading execution engine

### Infrastructure

- Docker and Docker Compose setup
- CI/CD pipeline improvements
- Deployment guides for cloud platforms
- Monitoring and observability

---

## Recognition

All contributors will be:

- Listed in the project's `CONTRIBUTORS.md` file
- Mentioned in release notes for significant contributions
- Eligible for maintainer status after sustained contributions (see [GOVERNANCE.md](GOVERNANCE.md))

---

## License

By contributing to Alpha Search, you agree that your contributions will be licensed under the [Apache License 2.0](LICENSE).

---

**Questions?** Reach out at team@alpha-search.io or open a [Discussion](https://github.com/alpha-search/alpha-search/discussions).
