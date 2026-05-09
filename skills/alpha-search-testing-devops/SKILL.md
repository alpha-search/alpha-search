---
name: alpha-search-testing-devops
description: Set up testing, CI/CD, packaging, and deployment — pytest, GitHub Actions, PyPI, Docker, docs.
---

# Alpha Search Testing & DevOps

## When to Use This Skill

Use this skill when establishing or maintaining the testing infrastructure, continuous integration, packaging, and deployment pipeline for Alpha Search. This includes writing pytest suites with fixtures and mocks, configuring GitHub Actions workflows, setting up PyPI publishing, configuring code quality tools (ruff, black, mypy), and deploying documentation. Activate this skill when new tests are needed, when CI workflows break, when preparing a release, or when code quality standards need enforcement.

## Agent Role

You are the Testing & DevOps specialist for Alpha Search. You ensure every line of production code is tested, every PR passes quality gates, and every release is automated and reproducible. You own the test suite, CI pipeline, packaging configuration, and deployment infrastructure. Your work gives the team confidence that changes don't break existing functionality and that releases are predictable.

## Core Concepts

### pytest Setup with Fixtures and Mocks

The test suite uses pytest with shared fixtures in conftest.py:

```python
# tests/conftest.py — Shared test infrastructure
import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, date
from unittest.mock import MagicMock, patch

from alpha_search.data.provider import OHLCV
from alpha_search.core.types import Ticker


@pytest.fixture
def sample_ohlcv() -> OHLCV:
    """Generate sample OHLCV data for testing."""
    dates = pd.date_range(start="2023-01-01", periods=100, freq="D")
    np.random.seed(42)
    base_price = 100.0
    returns = np.random.normal(0.0005, 0.02, 100)
    prices = base_price * (1 + returns).cumprod()

    return OHLCV(
        ticker="AAPL",
        timestamp=pd.DatetimeIndex(dates),
        open=prices * (1 + np.random.normal(0, 0.001, 100)),
        high=prices * (1 + abs(np.random.normal(0, 0.01, 100))),
        low=prices * (1 - abs(np.random.normal(0, 0.01, 100))),
        close=prices,
        volume=np.random.randint(1_000_000, 10_000_000, 100).astype(float),
    )


@pytest.fixture
def trending_ohlcv() -> OHLCV:
    """Generate strongly trending OHLCV data (uptrend)."""
    dates = pd.date_range(start="2023-01-01", periods=60, freq="D")
    prices = np.linspace(100, 150, 60)  # Steady uptrend
    return OHLCV(
        ticker="AAPL",
        timestamp=pd.DatetimeIndex(dates),
        open=prices - 0.5,
        high=prices + 1.0,
        low=prices - 1.0,
        close=prices,
        volume=np.full(60, 5_000_000.0),
    )


@pytest.fixture
def flat_ohlcv() -> OHLCV:
    """Generate flat OHLCV data (no trend)."""
    dates = pd.date_range(start="2023-01-01", periods=60, freq="D")
    prices = np.full(60, 100.0)
    return OHLCV(
        ticker="FLAT",
        timestamp=pd.DatetimeIndex(dates),
        open=prices,
        high=prices + 0.5,
        low=prices - 0.5,
        close=prices,
        volume=np.full(60, 1_000_000.0),
    )


@pytest.fixture
def mock_yfinance_response():
    """Mock yfinance Ticker response for unit tests."""
    mock_ticker = MagicMock()
    mock_ticker.info = {"regularMarketPrice": 150.0}

    dates = pd.date_range(start="2023-01-01", periods=30, freq="D")
    prices = np.linspace(100, 110, 30)
    mock_df = pd.DataFrame({
        "Open": prices - 0.5,
        "High": prices + 1.0,
        "Low": prices - 1.0,
        "Close": prices,
        "Volume": np.full(30, 5_000_000.0),
    }, index=dates)
    mock_ticker.history.return_value = mock_df

    return mock_ticker


@pytest.fixture
def mock_http_client():
    """Mock httpx client for API-dependent tests."""
    client = MagicMock()
    response = MagicMock()
    response.json.return_value = []
    response.raise_for_status.return_value = None
    client.get.return_value = response
    return client
```

Example test files using these fixtures:

```python
# tests/signals/test_technical.py
import pytest
import numpy as np
from alpha_search.signals.technical import MomentumSignal, MACrossoverSignal, ZScoreSignal, RSISignal


class TestMomentumSignal:
    def test_uptrend_generates_positive_signal(self, trending_ohlcv):
        signal = MomentumSignal(lookback=20, threshold=0.05)
        result = signal.generate(trending_ohlcv)
        # In a strong uptrend, the most recent signal should be positive
        assert result.signal.iloc[-1] > 0

    def test_flat_market_generates_neutral_signal(self, flat_ohlcv):
        signal = MomentumSignal(lookback=10)
        result = signal.generate(flat_ohlcv)
        # Flat market should produce near-zero signals after lookback
        assert abs(result.signal.iloc[-1]) < 0.5

    def test_signal_is_within_bounds(self, sample_ohlcv):
        signal = MomentumSignal()
        result = signal.generate(sample_ohlcv)
        assert result.signal.min() >= -1.0
        assert result.signal.max() <= 1.0


class TestMACrossoverSignal:
    def test_fast_above_slow_is_bullish(self, trending_ohlcv):
        signal = MACrossoverSignal(fast=5, slow=20)
        result = signal.generate(trending_ohlcv)
        # After enough data, fast MA > slow MA in uptrend
        assert result.signal.iloc[-1] > 0

    def test_invalid_periods_raises_error(self):
        with pytest.raises(ValueError, match="fast period must be less"):
            MACrossoverSignal(fast=50, slow=20)


class TestZScoreSignal:
    def test_price_below_mean_is_bullish(self, sample_ohlcv):
        signal = ZScoreSignal(lookback=20)
        result = signal.generate(sample_ohlcv)
        # Z-score signal is inverted: below mean -> positive (buy the dip)
        # Above mean -> negative (sell the rip)
        assert result.signal.min() >= -1.0
        assert result.signal.max() <= 1.0


class TestRSISignal:
    def test_oversold_is_bullish(self):
        """RSI < 30 should produce positive (bullish) signal."""
        import pandas as pd
        from alpha_search.data.provider import OHLCV

        # Create declining prices to push RSI low
        prices = 100 * (0.95 ** np.arange(30))
        ohlcv = OHLCV(
            ticker="TEST",
            timestamp=pd.DatetimeIndex(pd.date_range("2023-01-01", periods=30, freq="D")),
            open=prices, high=prices * 1.01, low=prices * 0.99,
            close=prices, volume=np.full(30, 1e6),
        )
        signal = RSISignal(period=14)
        result = signal.generate(ohlcv)
        # RSI should be low after sustained decline -> bullish signal
        assert result.signal.iloc[-1] > 0

    def test_overbought_is_bearish(self):
        """RSI > 70 should produce negative (bearish) signal."""
        import pandas as pd
        from alpha_search.data.provider import OHLCV

        prices = 100 * (1.05 ** np.arange(30))
        ohlcv = OHLCV(
            ticker="TEST",
            timestamp=pd.DatetimeIndex(pd.date_range("2023-01-01", periods=30, freq="D")),
            open=prices, high=prices * 1.01, low=prices * 0.99,
            close=prices, volume=np.full(30, 1e6),
        )
        signal = RSISignal(period=14)
        result = signal.generate(ohlcv)
        assert result.signal.iloc[-1] < 0
```

### GitHub Actions Workflow

```yaml
# .github/workflows/ci.yml
name: CI

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.10", "3.11", "3.12"]

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python ${{ matrix.python-version }}
        uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -e ".[dev]"

      - name: Lint with ruff
        run: ruff check alpha_search/ tests/

      - name: Format check with black
        run: black --check alpha_search/ tests/

      - name: Type check with mypy
        run: mypy alpha_search/ --ignore-missing-imports

      - name: Run tests with coverage
        run: pytest --cov=alpha_search --cov-report=xml --cov-report=term-missing

      - name: Upload coverage
        uses: codecov/codecov-action@v4
        with:
          file: ./coverage.xml
          fail_ci_if_error: false

      - name: Check coverage threshold
        run: |
          coverage_pct=$(python -c "import xml.etree.ElementTree as ET; tree=ET.parse('coverage.xml'); print(tree.getroot().get('line-rate'))")
          if (( $(echo "$coverage_pct < 0.70" | bc -l) )); then
            echo "Coverage $coverage_pct is below 70% threshold"
            exit 1
          fi
```

### pyproject.toml Configuration

```toml
# pyproject.toml — Project configuration, dependencies, and tool settings
[build-system]
requires = ["setuptools>=68", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "alpha-search"
version = "1.0.0"
description = "Open quantitative analysis and trading platform"
readme = "README.md"
license = {text = "MIT"}
authors = [
    {name = "Alpha Search Team", email = "team@quantos.dev"},
]
classifiers = [
    "Development Status :: 4 - Beta",
    "Intended Audience :: Financial and Insurance Industry",
    "License :: OSI Approved :: MIT License",
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.10",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
    "Topic :: Office/Business :: Financial :: Investment",
]
requires-python = ">=3.10"
dependencies = [
    "pandas>=2.0.0",
    "numpy>=1.24.0",
    "duckdb>=0.9.0",
    "pydantic>=2.0.0",
    "pydantic-settings>=2.0.0",
    "httpx>=0.25.0",
    "yfinance>=0.2.0",
    "transformers>=4.35.0",
    "torch>=2.0.0",
    "streamlit>=1.28.0",
    "plotly>=5.18.0",
    "typer>=0.9.0",
    "python-dotenv>=1.0.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.4.0",
    "pytest-cov>=4.1.0",
    "pytest-asyncio>=0.21.0",
    "ruff>=0.1.0",
    "black>=23.0.0",
    "mypy>=1.6.0",
    "hypothesis>=6.88.0",
]
docs = [
    "mkdocs>=1.5.0",
    "mkdocs-material>=9.4.0",
]

[project.scripts]
alpha-search = "alpha_search.cli:app"

[project.urls]
Homepage = "https://github.com/alpha-search/alpha-search"
Documentation = "https://alpha-search.github.io/alpha-search"
Repository = "https://github.com/alpha-search/alpha-search"

# Ruff configuration
[tool.ruff]
target-version = "py310"
line-length = 100
select = [
    "E",   # pycodestyle errors
    "F",   # Pyflakes
    "I",   # isort
    "N",   # pep8-naming
    "W",   # pycodestyle warnings
    "UP",  # pyupgrade
    "B",   # flake8-bugbear
    "C4",  # flake8-comprehensions
    "SIM", # flake8-simplify
]
ignore = ["E501"]  # Line length handled by black

[tool.ruff.pydocstyle]
convention = "google"

# Black configuration
[tool.black]
line-length = 100
target-version = ["py310", "py311", "py312"]

# mypy configuration
[tool.mypy]
python_version = "3.10"
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = true
disallow_incomplete_defs = true
check_untyped_defs = true
ignore_missing_imports = true

# pytest configuration
[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]
addopts = "-v --tb=short"
markers = [
    "slow: marks tests as slow (deselect with '-m \"not slow\"')",
    "integration: marks tests as integration tests",
    "unit: marks tests as unit tests",
]

# Coverage configuration
[tool.coverage.run]
source = ["alpha_search"]
omit = ["*/tests/*", "*/ui/*"]

[tool.coverage.report]
exclude_lines = [
    "pragma: no cover",
    "def __repr__",
    "raise AssertionError",
    "raise NotImplementedError",
    "if __name__ == .__main__.:",
    "if TYPE_CHECKING:",
]
fail_under = 70
```

### PyPI Publishing Steps

```python
# scripts/publish.py — Release automation
import subprocess
import sys
from pathlib import Path


def run(cmd: list[str], check: bool = True):
    """Run a shell command."""
    print(f">>> {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.stdout:
        print(result.stdout)
    if result.stderr:
        print(result.stderr, file=sys.stderr)
    if check and result.returncode != 0:
        sys.exit(result.returncode)
    return result


def publish(version: str):
    """Publish a new version to PyPI.

    Steps:
        1. Update version in pyproject.toml
        2. Run full test suite
        3. Build distribution
        4. Upload to PyPI
        5. Create git tag
    """
    pyproject = Path("pyproject.toml")
    content = pyproject.read_text()

    # Update version
    content = content.replace(
        f'version = "{version}"',
        f'version = "{version}"',
    )
    pyproject.write_text(content)

    # Run tests
    run(["pytest", "--cov=alpha_search", "--cov-report=term-missing"])

    # Build
    run(["rm", "-rf", "dist/", "build/", "*.egg-info"])
    run(["python", "-m", "build"])

    # Verify package
    run(["twine", "check", "dist/*"])

    # Upload to PyPI (production)
    run(["twine", "upload", "dist/*"])

    # Git tag
    run(["git", "add", "pyproject.toml"])
    run(["git", "commit", "-m", f"Release v{version}"])
    run(["git", "tag", f"v{version}"])
    run(["git", "push", "origin", "main", "--tags"])

    print(f"Successfully published alpha-search v{version} to PyPI")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python scripts/publish.py <version>")
        sys.exit(1)
    publish(sys.argv[1])
```

### Docker Configuration

```dockerfile
# Dockerfile — Container for deployment
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY pyproject.toml .
RUN pip install --no-cache-dir -e ".[dev]"

# Copy source code
COPY alpha_search/ ./alpha_search/
COPY tests/ ./tests/

# Run tests as validation
RUN pytest tests/ --tb=short -q

# Default: run Streamlit app
EXPOSE 8501
CMD ["streamlit", "run", "alpha_search/ui/app.py", "--server.port=8501", "--server.address=0.0.0.0"]
```

### Documentation Hosting

```yaml
# .github/workflows/docs.yml
name: Deploy Documentation

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install docs dependencies
        run: pip install mkdocs mkdocs-material

      - name: Build docs
        run: mkdocs build

      - name: Deploy to GitHub Pages
        uses: peaceiris/actions-gh-pages@v3
        with:
          github_token: ${{ secrets.GITHUB_TOKEN }}
          publish_dir: ./site
```

```yaml
# mkdocs.yml
site_name: Alpha Search Documentation
theme:
  name: material
  features:
    - navigation.tabs
    - navigation.sections
    - search.highlight

nav:
  - Home: index.md
  - Architecture: architecture.md
  - User Guide: user_guide.md
  - API Reference: api_reference.md
  - Deployment: deployment.md

plugins:
  - search

markdown_extensions:
  - pymdownx.highlight
  - pymdownx.superfences
  - admonition
```

## Responsibilities

1. Write comprehensive pytest suites with shared fixtures in conftest.py
2. Mock all external API calls (yfinance, Binance, NewsAPI) in unit tests
3. Configure GitHub Actions CI workflow (lint/test/type-check/coverage)
4. Maintain pyproject.toml with correct dependencies and tool configurations
5. Enforce code coverage threshold of 70%+ with pytest-cov
6. Configure ruff for linting, black for formatting, mypy for type checking
7. Set up automated PyPI publishing with version tagging
8. Maintain Dockerfile for containerized deployment
9. Configure MkDocs + GitHub Pages for documentation hosting
10. Mark slow/integration tests so they can be excluded from fast CI runs

## Inputs

- Source code from all implementation agents
- PR diffs that need quality gate enforcement
- Test requirements from specification
- Version numbers for releases

## Outputs

- pytest test suite with fixtures and mocks
- GitHub Actions CI/CD workflow files
- pyproject.toml with complete configuration
- Coverage reports (XML and terminal)
- Docker image for deployment
- Documentation site on GitHub Pages
- PyPI package releases

## Required Files to Create or Modify

- `pyproject.toml` — project config, dependencies, tool settings (create)
- `tests/conftest.py` — shared fixtures (create)
- `tests/unit/` — unit test modules mirroring source structure (create)
- `tests/integration/` — integration tests (create)
- `.github/workflows/ci.yml` — CI workflow (create)
- `.github/workflows/docs.yml` — docs deployment (create)
- `.github/workflows/release.yml` — release automation (create)
- `Dockerfile` — container definition (create)
- `mkdocs.yml` — documentation site config (create)
- `scripts/publish.py` — release script (create)
- `.gitignore` — Python/artifact exclusions (create)
- `MANIFEST.in` — package file inclusions (create)

## Implementation Checklist

- [ ] Create pyproject.toml with all dependencies and tool configs
- [ ] Write tests/conftest.py with OHLCV fixtures and mocks
- [ ] Write unit tests for DataProvider ABC compliance
- [ ] Write unit tests for all signal classes
- [ ] Write unit tests for BacktestEngine
- [ ] Write unit tests for PaperTrader
- [ ] Write unit tests for RiskController
- [ ] Write unit tests for SentimentPipeline
- [ ] Write unit tests for CacheManager
- [ ] Configure GitHub Actions CI (lint + test + type-check + coverage)
- [ ] Set up ruff, black, mypy configurations in pyproject.toml
- [ ] Configure coverage threshold at 70% in CI
- [ ] Create Dockerfile for containerized deployment
- [ ] Set up MkDocs with material theme
- [ ] Configure GitHub Pages deployment workflow
- [ ] Create release automation workflow
- [ ] Write publish.py script for manual PyPI releases
- [ ] Verify `pip install -e ".[dev]"` works in clean environment

## Testing Checklist

- [ ] `pytest` runs successfully with all tests passing
- [ ] Coverage report shows >=70% line coverage
- [ ] All external API calls are mocked (no network in unit tests)
- [ ] ruff check passes with zero errors
- [ ] black --check passes with zero formatting issues
- [ ] mypy passes with zero type errors on alpha_search/
- [ ] CI workflow passes on Python 3.10, 3.11, 3.12
- [ ] Docker image builds successfully
- [ ] `docker run` starts Streamlit app on port 8501
- [ ] Documentation site builds with mkdocs build
- [ ] Slow tests are marked and can be excluded with `-m "not slow"`
- [ ] Test fixtures produce deterministic results (seeded random)
- [ ] conftest.py fixtures are used by multiple test modules

## Definition of Done

- Full pytest suite runs successfully with all tests passing
- Code coverage is 70% or higher across the alpha_search/ package
- CI pipeline passes on every PR (lint + test + type-check)
- ruff, black, and mypy configurations are active and passing
- pyproject.toml correctly specifies all dependencies
- Dockerfile builds and runs the Streamlit application
- Documentation is deployed to GitHub Pages
- PyPI package can be installed with `pip install alpha-search`
- Release process is automated via GitHub Actions
- All external dependencies are mocked in unit tests

## Example Prompt

> You are the Alpha Search Testing & DevOps agent. Set up the complete testing and CI infrastructure: create pyproject.toml with all dependencies and tool configs (ruff, black, mypy, pytest), write tests/conftest.py with OHLCV fixtures and mocked external APIs, write unit tests for Signal classes and BacktestEngine, configure GitHub Actions CI with lint/test/type-check/coverage gates at 70%, create a Dockerfile for containerized deployment, and set up MkDocs documentation hosting on GitHub Pages.