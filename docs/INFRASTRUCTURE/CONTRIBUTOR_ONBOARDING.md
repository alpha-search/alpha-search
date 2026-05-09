# Contributor Onboarding Guide

> **Welcome to Alpha Search!** This guide will take you from zero to your first contribution in under 30 minutes.
> **Target audience:** New contributors, first-time open-source participants, experienced devs joining the project

---

## Table of Contents

1. [Quick Start (5 minutes)](#quick-start)
2. [First Contribution Walkthrough](#first-contribution)
3. [Development Environment Setup](#development-setup)
4. [Code Review Process](#code-review)
5. [Contribution Types](#contribution-types)
6. [Coding Standards](#coding-standards)
7. [Testing Requirements](#testing)
8. [Pull Request Template](#pr-template)
9. [Common Issues & Solutions](#common-issues)
10. [Community Guidelines](#community-guidelines)
11. [Recognition & Rewards](#recognition)

---

## Quick Start (5 minutes)

### Prerequisites

| Tool | Version | Check |
|---|---|---|
| Python | 3.10+ | `python --version` |
| Git | 2.30+ | `git --version` |
| pip | 23+ | `pip --version` |

### One-Command Setup

```bash
# 1. Fork the repo on GitHub (click "Fork" button)
# 2. Clone your fork
git clone https://github.com/YOUR_USERNAME/alpha-search.git
cd alpha-search

# 3. Create virtual environment
python -m venv .venv
source .venv/.bin/activate  # Linux/Mac
# .venv\Scripts\activate     # Windows

# 4. Install in development mode
pip install -e ".[dev]"

# 5. Run tests to verify setup
pytest tests/ -q

# 6. You're ready to contribute!
```

**Expected output after `pytest`:**
```
..............................
========== X passed in Y.YYs ==========
```

If you see this, your setup is correct. If not, see [Common Issues](#common-issues).

---

## First Contribution Walkthrough

### Example: Fix a Typo in Documentation

This is the fastest way to make your first contribution and learn the workflow.

#### Step 1: Find a Typo

Look for a typo in any `.md` file. Alternatively, pick an issue labeled [`good first issue`](https://github.com/alpha-search/alpha-search/labels/good%20first%20issue).

#### Step 2: Create a Branch

```bash
# Make sure you're on main and it's up to date
git checkout main
git pull upstream main

# Create a feature branch
git checkout -b fix-typo-in-readme
```

**Branch naming conventions:**
| Type | Pattern | Example |
|---|---|---|
| Bug fix | `fix-*` | `fix-typo-in-readme` |
| Feature | `feat-*` | `feat-add-bollinger-strategy` |
| Documentation | `docs-*` | `docs-update-quickstart` |
| Refactor | `refactor-*` | `refactor-data-loader` |
| Test | `test-*` | `test-backtest-edge-cases` |

#### Step 3: Make the Change

```bash
# Edit the file
nano README.md  # or use your favorite editor

# Stage the change
git add README.md

# Commit with a clear message
git commit -m "docs: fix typo in README introduction

Fixed 'reaserch' -> 'research' in the project description."
```

**Commit message format:**
```
<type>: <short description>

<body (optional)>

<footer (optional)>
```

**Types:**
| Type | Use for |
|---|---|
| `feat` | New feature |
| `fix` | Bug fix |
| `docs` | Documentation only |
| `test` | Adding or updating tests |
| `refactor` | Code change that neither fixes a bug nor adds a feature |
| `perf` | Performance improvement |
| `chore` | Build process, dependencies, tooling |
| `security` | Security-related change |

#### Step 4: Push and Create PR

```bash
# Push to your fork
git push origin fix-typo-in-readme

# Then open a Pull Request on GitHub
# GitHub will show a "Compare & pull request" button
```

#### Step 5: Fill Out the PR Template

See [Pull Request Template](#pr-template) below.

#### Step 6: Wait for Review

A maintainer will review your PR within 48 hours (usually faster). They may:
- Approve and merge it
- Request small changes
- Ask clarifying questions

**Respond to feedback promptly.** Even a simple "Done, thanks for the review!" helps keep things moving.

---

## Development Environment Setup

### Full Setup (for significant contributions)

```bash
# 1. Fork and clone
git clone https://github.com/YOUR_USERNAME/alpha-search.git
cd alpha-search

# 2. Add upstream remote
git remote add upstream https://github.com/alpha-search/alpha-search.git

# 3. Create virtual environment
python -m venv .venv
source .venv/bin/activate

# 4. Install with all dev dependencies
pip install -e ".[dev]"

# 5. Install pre-commit hooks
pre-commit install

# 6. Verify everything works
pytest tests/          # All tests pass
mypy alpha_search/         # Type checking passes
ruff check alpha_search/   # Linting passes
black --check alpha_search/  # Formatting is correct

# 7. Optional: Install documentation dependencies
pip install -e ".[docs]"
```

### Project Structure

```
alpha-search/
  alpha_search/                 # Main package
    __init__.py
    core/                   # Engine, data structures
      engine.py
      portfolio.py
      types.py
    strategies/             # Built-in strategies
      momentum.py
      mean_reversion.py
      pair_trading.py
      base.py
    backtest/               # Backtesting engine
      backtest.py
      metrics.py
      report.py
    data/                   # Data loaders
      yahoo.py
      zerodha.py
      csv_loader.py
      base.py
    agents/                 # Multi-agent framework
      agent.py
      memory.py
      orchestrator.py
    analysis/               # Analytics and reporting
      statistics.py
      visualization.py
    config/                 # Configuration
      defaults.py
      security.py
    auth/                   # Authentication (Phase 3)
      jwt_handler.py
      oauth.py
      rate_limit.py
    utils/                  # Utilities
      logging.py
      validation.py
  tests/                    # Test suite
    unit/                   # Unit tests
    integration/            # Integration tests
    fixtures/               # Test data
  docs/                     # Documentation
    quickstart.md
    installation.md
    strategies.md
    backtesting.md
    data-sources.md
    agents.md
    INFRASTRUCTURE/         # Ops and infra docs
  examples/                 # Jupyter notebooks
    01_momentum.ipynb
    02_mean_reversion.ipynb
    03_pair_trading.ipynb
    04_indian_markets.ipynb
  scripts/                  # Utility scripts
    rotate-keys.sh
  .github/                  # GitHub configuration
    workflows/              # CI/CD
    ISSUE_TEMPLATE/         # Issue templates
  pyproject.toml            # Project metadata
  .env.example              # Environment template
  .pre-commit-config.yaml   # Pre-commit hooks
  .gitignore
  LICENSE
  README.md
  CHANGELOG.md
  CONTRIBUTING.md
  CODE_OF_CONDUCT.md
  SECURITY.md
```

### Useful Development Commands

```bash
# Run specific test file
pytest tests/unit/test_momentum.py -v

# Run tests with coverage
pytest tests/ --cov=alpha_search --cov-report=html

# Run only fast tests
pytest tests/ -m "not slow"

# Run tests matching a pattern
pytest tests/ -k "momentum"

# Auto-format code
black alpha_search/ tests/
ruff check --fix alpha_search/ tests/

# Type check
mypy alpha_search/

# Run all checks (same as CI)
ruff check alpha_search/ tests/
black --check alpha_search/ tests/
mypy alpha_search/
pytest tests/

# Build documentation
cd docs && make html

# Build package
python -m build

# Check package
twine check dist/*
```

---

## Code Review Process

### For Contributors

```
1. Open PR --> 2. Automated checks run --> 3. Maintainer review
                                              |
                                    +---------+---------+
                                    |                   |
                              Approve & merge    Request changes
                                    |                   |
                                    v                   v
                              Merged to main      You update PR
                                                        |
                                              Return to step 3
```

**What reviewers look for:**

| Check | Why It Matters |
|---|---|
| Tests pass | Code must not break existing functionality |
| New tests added | New code must be tested |
| Type hints | All functions must be typed |
| Docstrings | Public functions must be documented |
| Code style | Consistent with project standards |
| No secrets | No API keys or passwords in code |
| Clear commit messages | History must be readable |

**Responding to review feedback:**

```bash
# Make requested changes
git add <changed-files>
git commit -m "address review feedback: use dict comprehension

Reviewer suggestion: https://github.com/alpha-search/alpha-search/pull/XXX#discussion_rYYY"
git push origin your-branch
```

### For Maintainers

**Review checklist:**
- [ ] Code solves the stated problem
- [ ] Tests cover new functionality
- [ ] No security issues (secrets, injection risks)
- [ ] Documentation updated (if needed)
- [ ] CHANGELOG.md updated (if user-facing change)
- [ ] Backwards compatible (or properly versioned)
- [ ] Performance acceptable

**Review etiquette:**
- Be kind and constructive
- Explain the "why" behind suggestions
- Approve promptly when ready
- Thank contributors for their time

---

## Contribution Types

### Code Contributions

| Type | Examples | Skills Needed |
|---|---|---|
| **Bug fixes** | Fix backtest calculation errors | Python, finance domain |
| **New strategies** | Add Bollinger Bands, MACD strategy | Python, quantitative finance |
| **Data sources** | Add Alpaca, Interactive Brokers | Python, API integration |
| **Performance** | Vectorize slow functions | Python, NumPy, Numba |
| **Features** | Add walk-forward optimization | Python, statistics |
| **Tests** | Add missing test coverage | Python, pytest |

### Non-Code Contributions

| Type | Examples | Skills Needed |
|---|---|---|
| **Documentation** | Fix typos, write tutorials | Writing, Markdown |
| **Translations** | Translate docs to other languages | Bilingual |
| **Design** | Create logos, diagrams | Graphic design |
| **Community** | Answer questions, moderate | Communication |
| **Bug reports** | Report issues with reproduction steps | Attention to detail |
| **Feature requests** | Suggest improvements | Domain knowledge |

### Finding Something to Work On

```bash
# Good first issues (beginner-friendly)
# https://github.com/alpha-search/alpha-search/labels/good%20first%20issue

# Help wanted (maintainers need help)
# https://github.com/alpha-search/alpha-search/labels/help%20wanted

# Bug fixes
# https://github.com/alpha-search/alpha-search/labels/bug

# Feature requests
# https://github.com/alpha-search/alpha-search/labels/enhancement
```

**Pro tip:** Comment on an issue before starting work:
> "I'd like to work on this. I'll submit a PR within 3 days."

This prevents duplicate work and lets maintainers provide guidance.

---

## Coding Standards

### Python Style Guide

We follow [PEP 8](https://peps.python.org/pep-0008/) with these project-specific additions:

```python
# Line length: 100 characters (not 79)
# Use double quotes for strings (black default)

# Imports: stdlib, third-party, local -- each group alphabetized
import os
from datetime import datetime
from typing import Optional

import numpy as np
import pandas as pd
from numba import jit

from alpha_search.core.portfolio import Portfolio
from alpha_search.utils.logging import get_logger

# Type hints required for all public functions
def calculate_returns(
    prices: pd.Series,
    method: str = "simple",
) -> pd.Series:
    """Calculate returns from a price series.

    Args:
        prices: Series of price values, indexed by date.
        method: Return calculation method. One of "simple", "log", "total".

    Returns:
        Series of returns with the same index as prices.

    Raises:
        ValueError: If method is not one of the supported values.

    Example:
        >>> prices = pd.Series([100, 110, 105], index=pd.date_range("2024-01-01", periods=3))
        >>> calculate_returns(prices)
        2024-01-01         NaN
        2024-01-02    0.100000
        2024-01-03   -0.045455
        dtype: float64
    """
    if method not in ("simple", "log", "total"):
        raise ValueError(f"Unknown method: {method}")
    # ... implementation
```

### Docstring Format

Use [Google-style docstrings](https://sphinxcontrib-napoleon.readthedocs.io/en/latest/example_google.html):

```python
def function_name(param1: type, param2: type = default) -> return_type:
    """Short description (one line).

    Longer description if needed. Can span multiple paragraphs.

    Args:
        param1: Description of param1.
        param2: Description of param2. Defaults to X.

    Returns:
        Description of return value.

    Raises:
        ErrorType: When this error occurs.

    Example:
        >>> function_name(1, 2)
        3
    """
```

### Naming Conventions

| Element | Convention | Example |
|---|---|---|
| Packages | lowercase | `alpha_search` |
| Modules | lowercase | `momentum.py` |
| Classes | PascalCase | `MomentumStrategy` |
| Functions | snake_case | `calculate_returns` |
| Constants | UPPER_SNAKE | `MAX_LOOKBACK_DAYS` |
| Private | leading underscore | `_internal_helper` |
| Type variables | PascalCase, descriptive | `PriceSeries`, `SignalArray` |

---

## Testing Requirements

### Test Structure

```python
# tests/unit/test_momentum.py
"""Tests for momentum strategy module."""

import numpy as np
import pandas as pd
import pytest

from alpha_search.strategies.momentum import MomentumStrategy


class TestMomentumStrategy:
    """Test suite for MomentumStrategy."""

    def test_basic_signal_generation(self):
        """Strategy should generate positive signals for upward trends."""
        prices = pd.Series([100, 110, 120, 130, 140])
        strategy = MomentumStrategy(lookback=2)
        signals = strategy.generate_signals(prices)

        assert len(signals) == len(prices)
        assert signals.iloc[-1] == 1  # Positive momentum

    def test_lookback_validation(self):
        """Strategy should reject invalid lookback periods."""
        with pytest.raises(ValueError, match="lookback must be positive"):
            MomentumStrategy(lookback=0)

        with pytest.raises(ValueError, match="lookback must be positive"):
            MomentumStrategy(lookback=-1)

    @pytest.mark.parametrize("lookback,expected", [
        (5, 0.05),
        (10, 0.03),
        (20, 0.01),
    ])
    def test_different_lookbacks(self, lookback, expected):
        """Strategy should work with various lookback periods."""
        # ... test implementation

    @pytest.mark.slow
    def test_large_dataset_performance(self):
        """Strategy should handle 1M+ rows efficiently."""
        prices = pd.Series(np.random.randn(1_000_000).cumsum() + 100)
        strategy = MomentumStrategy(lookback=20)

        import time
        start = time.time()
        signals = strategy.generate_signals(prices)
        elapsed = time.time() - start

        assert elapsed < 1.0  # Should complete in under 1 second
```

### Test Requirements by Contribution Type

| Contribution Type | Test Requirement |
|---|---|
| Bug fix | Add test that reproduces the bug |
| New feature | Full test coverage for new code |
| Performance fix | Add benchmark test |
| Documentation | No tests needed |
| Refactor | Ensure existing tests still pass |

### Running Tests

```bash
# All tests
pytest tests/

# With verbose output
pytest tests/ -v

# With coverage report
pytest tests/ --cov=alpha_search --cov-report=term-missing

# Specific file
pytest tests/unit/test_momentum.py

# Specific test
pytest tests/unit/test_momentum.py::TestMomentumStrategy::test_basic_signal_generation

# Slow tests only
pytest tests/ -m slow

# Exclude slow tests
pytest tests/ -m "not slow"
```

---

## Pull Request Template

When opening a PR, fill out this template (shown automatically):

```markdown
## Description
<!-- Describe your changes in 1-2 sentences -->

## Related Issue
<!-- Link to the issue this PR addresses -->
Fixes #123

## Type of Change
<!-- Check the relevant boxes -->
- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Documentation update
- [ ] Performance improvement
- [ ] Refactoring

## Testing
<!-- Describe how you tested your changes -->
- [ ] All existing tests pass
- [ ] New tests added for new functionality
- [ ] Tested manually (describe steps)

## Checklist
- [ ] Code follows project style guidelines
- [ ] Self-review completed
- [ ] Comments added for complex code
- [ ] Documentation updated (if needed)
- [ ] CHANGELOG.md updated (if user-facing change)
- [ ] No secrets or API keys in code

## Screenshots (if applicable)
<!-- Add screenshots for UI changes -->
```

---

## Common Issues & Solutions

### Issue: `pip install -e ".[dev]"` fails

```bash
# Solution 1: Update pip
pip install --upgrade pip setuptools wheel

# Solution 2: Install build dependencies first
pip install numpy pandas  # Install heavy deps first
pip install -e ".[dev]"

# Solution 3: Use no-build-isolation
pip install -e ".[dev]" --no-build-isolation
```

### Issue: Tests fail with import errors

```bash
# Make sure you installed in development mode
pip install -e ".[dev]"

# Check that alpha_search is importable
python -c "import alpha_search; print(alpha_search.__version__)"

# If not, check your virtual environment is activated
which python  # Should point to .venv/bin/python
```

### Issue: Pre-commit hooks fail

```bash
# Install hooks
pre-commit install

# Run hooks manually to see detailed errors
pre-commit run --all-files

# Auto-fix formatting issues
black alpha_search/ tests/
ruff check --fix alpha_search/ tests/

# Skip hooks in emergency (not recommended for PRs)
git commit --no-verify
```

### Issue: Type checking fails with mypy

```bash
# Check specific file
mypy alpha_search/strategies/momentum.py

# Common fixes:
# - Add type hints to function signatures
# - Use Optional[Type] for nullable values
# - Use from __future__ import annotations for forward references
```

### Issue: Merge conflicts

```bash
# Update your main branch
git checkout main
git pull upstream main

# Rebase your feature branch
git checkout your-feature-branch
git rebase main

# Fix conflicts (edit files, then)
git add <resolved-files>
git rebase --continue

# Force push (safe on feature branches)
git push origin your-feature-branch --force-with-lease
```

---

## Community Guidelines

### Communication Channels

| Channel | Purpose | Link |
|---|---|---|
| GitHub Issues | Bug reports, feature requests | https://github.com/alpha-search/alpha-search/issues |
| GitHub Discussions | General questions, ideas | https://github.com/alpha-search/alpha-search/discussions |
| Discord | Real-time chat | [Invitation link] |
| Stack Overflow | How-to questions (tag `alpha-search`) | https://stackoverflow.com/questions/tagged/alpha-search |

### Code of Conduct

We follow the [Contributor Covenant](https://www.contributor-covenant.org/version/2/1/code_of_conduct/):

- **Be respectful:** Treat everyone with respect, regardless of experience level
- **Be constructive:** Criticize ideas, not people
- **Be inclusive:** Welcome newcomers and help them learn
- **Be patient:** Maintainers are volunteers with day jobs
- **Be professional:** No harassment, discrimination, or trolling

**Reporting violations:** Contact conduct@alpha-search.dev (responses within 24 hours)

### Asking Questions

Before asking:
1. Search existing issues and discussions
2. Check the documentation
3. Try the examples

When asking:
- Provide context (what you're trying to achieve)
- Include error messages and stack traces
- Share minimal code to reproduce the issue
- Mention your environment (OS, Python version, Alpha Search version)

---

## Recognition & Rewards

### Contributor Levels

| Level | Criteria | Recognition |
|---|---|---|
| **First Timer** | 1 merged PR | Welcome message, "first contribution" badge |
| **Contributor** | 3 merged PRs | Listed in CONTRIBUTORS.md |
| **Regular** | 10 merged PRs | "Regular Contributor" badge, early access to features |
| **Core** | 25+ merged PRs | Invitation to core team, maintainer privileges |
| **Sustainer** | 50+ merged PRs | Named in release notes, conference co-presentation |

### All Contributors

We use the [All Contributors](https://allcontributors.org/) specification to recognize all types of contributions:

```
@all-contributors please add @username for code, docs, tests
```

Contribution types: `code`, `doc`, `test`, `bug`, `ideas`, `design`, `financial`, `infra`, `tutorial`, `talk`, `video`, `blog`, `promotion`

### Financial Support

If you benefit from Alpha Search professionally:
- [GitHub Sponsors](https://github.com/sponsors/alpha-search)
- [Open Collective](https://opencollective.com/alpha-search)

Sponsors are recognized in:
- README.md (logo + link)
- Documentation site
- Release notes
- Conference presentations

---

## Appendix: Git Workflow Cheat Sheet

```bash
# Start new work
git checkout main
git pull upstream main
git checkout -b feat-my-feature

# Work on code
# ... edit files ...

# Check what's changed
git status
git diff

# Stage changes
git add -p  # Review each change individually (recommended)
# or
git add <specific-file>

# Commit
git commit -m "feat: add bollinger bands strategy

Implements Bollinger Bands mean reversion strategy with:
- Configurable window and standard deviation multiplier
- Position sizing based on z-score
- Unit tests with 95% coverage

Closes #456"

# Keep your branch updated
git fetch upstream
git rebase upstream/main

# Push
git push origin feat-my-feature

# After PR is merged, clean up
git checkout main
git pull upstream main
git branch -d feat-my-feature
git push origin --delete feat-my-feature
```

---

## Questions?

- **Quick question:** [GitHub Discussions](https://github.com/alpha-search/alpha-search/discussions)
- **Bug report:** [GitHub Issues](https://github.com/alpha-search/alpha-search/issues/new?template=bug_report.md)
- **Feature request:** [GitHub Issues](https://github.com/alpha-search/alpha-search/issues/new?template=feature_request.md)
- **Private inquiry:** conduct@alpha-search.dev

**We're thrilled you're here. Let's build something amazing together.**

---

*This document is version-controlled. Last updated: v0.1.0*
