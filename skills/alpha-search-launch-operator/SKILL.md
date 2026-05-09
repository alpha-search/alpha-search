---
name: alpha-search-launch-operator
description: Execute Alpha Search launch — GitHub setup, PyPI release, marketing, community building, growth tracking.
---

# Alpha Search Launch Operator

## When to Use This Skill

Use this skill when preparing for and executing the public launch of Alpha Search. This includes GitHub repository setup, PyPI package publishing, marketing content creation, community engagement across platforms, documentation deployment, and growth tracking against targets. Activate this skill at the start of Week 6 (launch week), when preparing release artifacts, when posting to marketing channels, or when tracking community growth metrics.

## Agent Role

You are the Launch Operator for Alpha Search. You own the entire go-to-market execution: repository setup, package publishing, marketing launches, community building, and growth tracking. You coordinate between the technical team (who built the product) and the world (who needs to discover it). Your success is measured in GitHub stars, PyPI downloads, community engagement, and meaningful adoption by quant researchers and developers.

## Core Concepts

### GitHub Repository Setup

```python
# scripts/setup_github_repo.py — Repository initialization
import subprocess
import json
from pathlib import Path


def setup_github_repo(
    repo_name: str = "alpha-search",
    org: str = "alpha-search",
    description: str = "Open quantitative analysis and trading platform",
):
    """Set up the Alpha Search GitHub repository with best practices.

    Steps:
        1. Create repository (via GitHub CLI or API)
        2. Add branch protection rules
        3. Configure issue templates
        4. Set up discussion categories
        5. Add repository topics and description
        6. Enable GitHub Pages
    """
    steps = [
        # Create repo
        ["gh", "repo", "create", f"{org}/{repo_name}",
         "--public", "--description", description,
         "--add-readme", "--license", "MIT"],

        # Clone and set up
        ["gh", "repo", "clone", f"{org}/{repo_name}"],
    ]

    for step in steps:
        subprocess.run(step, check=True)

    # Create directory structure
    repo_path = Path(repo_name)
    directories = [
        "alpha_search", "alpha_search/core", "alpha_search/data",
        "alpha_search/research", "alpha_search/signals", "alpha_search/backtest",
        "alpha_search/execution", "alpha_search/execution/adapters",
        "alpha_search/portfolio", "alpha_search/ui", "alpha_search/ui/pages",
        "alpha_search/ui/components",
        "tests", "tests/unit", "tests/integration",
        "docs", "scripts", ".github/workflows",
    ]
    for d in directories:
        (repo_path / d).mkdir(parents=True, exist_ok=True)

    # Create essential files
    files = {
        "README.md": generate_readme(),
        "CONTRIBUTING.md": generate_contributing(),
        "CODE_OF_CONDUCT.md": generate_code_of_conduct(),
        "SECURITY.md": generate_security(),
        ".github/ISSUE_TEMPLATE/bug_report.md": generate_bug_template(),
        ".github/ISSUE_TEMPLATE/feature_request.md": generate_feature_template(),
        ".github/PULL_REQUEST_TEMPLATE.md": generate_pr_template(),
    }

    for filepath, content in files.items():
        path = repo_path / filepath
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)

    print(f"Repository {org}/{repo_name} set up successfully")
    return repo_path


def generate_readme() -> str:
    return '''# Alpha Search

[![CI](https://github.com/alpha-search/alpha-search/actions/workflows/ci.yml/badge.svg)](https://github.com/alpha-search/alpha-search/actions)
[![PyPI version](https://badge.fury.io/py/alpha-search.svg)](https://pypi.org/project/alpha-search/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)

**Open quantitative analysis and trading platform.**

Alpha Search is the intelligence layer for financial research. It generates trading
signals, runs vectorized backtests, analyzes sentiment with FinBERT, optimizes
portfolios, and simulates execution — all in pure Python with an MIT license.

## Quick Start

```bash
pip install alpha-search
alpha-search launch  # Start the Streamlit terminal
```

## Features

- **Signal Framework** — Compose technical and sentiment signals with `&`, `|`, `~`
- **Vectorized Backtesting** — 100x faster than event-driven engines
- **Walk-Forward Validation** — Prevent overfitting with out-of-sample testing
- **FinBERT Sentiment** — Multi-source sentiment analysis (news, social, earnings)
- **Portfolio Optimization** — Mean-variance and risk-parity allocation
- **Paper Trading** — Risk-free strategy validation with realistic simulation
- **Streamlit Terminal** — Web-based research dashboard

## Architecture

```
Data (YFinance, Binance) → Signals → Backtest → Execution → UI
```

## Documentation

Full documentation: [https://alpha-search.github.io/alpha-search](https://alpha-search.github.io/alpha-search)

## License

MIT. Free for commercial and non-commercial use.

## Community

- [GitHub Discussions](https://github.com/alpha-search/alpha-search/discussions)
- [Discord](https://discord.gg/quantos) *(create when ready)*
'''


def generate_contributing() -> str:
    return '''# Contributing to Alpha Search

Thank you for your interest in contributing! This project welcomes:

- Bug reports and feature requests (via GitHub Issues)
- Code contributions (via Pull Requests)
- Documentation improvements
- Community support in Discussions

## Development Setup

```bash
git clone https://github.com/alpha-search/alpha-search.git
cd alpha-search
pip install -e ".[dev]"
pytest
```

## Pull Request Process

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes with tests
4. Ensure CI passes (`pytest && ruff check . && mypy alpha_search/`)
5. Submit a PR with a clear description

All PRs require review from at least one maintainer.
'''


def generate_bug_template() -> str:
    return '''---
name: Bug report
about: Create a report to help us improve
---

**Describe the bug**
A clear description of the bug.

**To Reproduce**
Steps to reproduce the behavior.

**Expected behavior**
What you expected to happen.

**Environment:**
- OS: [e.g., macOS 14]
- Python version: [e.g., 3.11]
- Alpha Search version: [e.g., 1.0.0]
'''


def generate_pr_template() -> str:
    return '''## Description
Brief description of the changes.

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Documentation update

## Testing
- [ ] Tests pass locally
- [ ] New tests added for new functionality
- [ ] Coverage remains above 70%

## Checklist
- [ ] Code follows project style guidelines
- [ ] Self-review completed
- [ ] Comments added for complex logic
'''
```

### PyPI Publishing Steps

```python
# scripts/publish_to_pypi.py — PyPI release automation
import subprocess
import sys
from pathlib import Path


def publish_to_pypi(version: str, test: bool = True):
    """Publish Alpha Search to PyPI.

    Args:
        version: Semantic version string (e.g., "1.0.0")
        test: If True, publish to TestPyPI first
    """
    # 1. Clean build artifacts
    subprocess.run(["rm", "-rf", "dist/", "build/", "*.egg-info"], check=False)

    # 2. Verify version in pyproject.toml
    pyproject = Path("pyproject.toml")
    content = pyproject.read_text()
    if f'version = "{version}"' not in content:
        print(f"ERROR: Version {version} not found in pyproject.toml")
        sys.exit(1)

    # 3. Run tests
    result = subprocess.run(["pytest", "-q"], capture_output=True, text=True)
    if result.returncode != 0:
        print("Tests failed:")
        print(result.stdout)
        print(result.stderr)
        sys.exit(1)

    # 4. Build distribution
    subprocess.run(["python", "-m", "build"], check=True)

    # 5. Verify distribution
    subprocess.run(["twine", "check", "dist/*"], check=True)

    # 6. Publish (TestPyPI first, then production)
    if test:
        print("Publishing to TestPyPI...")
        subprocess.run([
            "twine", "upload", "--repository", "testpypi", "dist/*"
        ], check=True)
        print(f"Test release successful: pip install -i https://test.pypi.org/simple/ alpha-search=={version}")

        confirm = input("Promote to production PyPI? [y/N]: ")
        if confirm.lower() != "y":
            print("Aborted. Test release remains on TestPyPI.")
            return

    print("Publishing to PyPI...")
    subprocess.run(["twine", "upload", "dist/*"], check=True)

    # 7. Create git tag
    subprocess.run(["git", "add", "-A"], check=True)
    subprocess.run(["git", "commit", "-m", f"Release v{version}"], check=True)
    subprocess.run(["git", "tag", f"v{version}"], check=True)
    subprocess.run(["git", "push", "origin", "main", "--tags"], check=True)

    print(f"Successfully published alpha-search v{version} to PyPI")
    print(f"Install: pip install alpha-search=={version}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/publish_to_pypi.py <version> [--production]")
        sys.exit(1)
    version = sys.argv[1]
    test = "--production" not in sys.argv
    publish_to_pypi(version, test=test)
```

### Hacker News Launch Post

```markdown
# Hacker News Launch Post Template

Title: Show HN: Alpha Search — Open-source quantitative analysis platform

Hi HN,

We built Alpha Search because we wanted an open-source, MIT-licensed platform
for quantitative research that goes beyond data visualization.

What it does:
- Generates trading signals from technical indicators and sentiment (FinBERT)
- Vectorized backtesting 100x faster than event-driven engines
- Walk-forward validation to prevent overfitting
- Paper trading with realistic cost simulation
- Multi-source sentiment: news, Twitter, Reddit, earnings
- Streamlit-based research terminal

The signal framework is the part we're most proud of. You can compose
signals with logical operators:

```python
from alpha_search.signals.technical import MomentumSignal, MACrossoverSignal
from alpha_search.backtest.engine import BacktestEngine

signal = MomentumSignal(lookback=20) & MACrossoverSignal(fast=20, slow=50)
engine = BacktestEngine()
result = engine.run(data, signal)
print(f"Sharpe: {result.metrics['sharpe_ratio']:.2f}")
```

MIT licensed. Free for commercial use.

GitHub: https://github.com/alpha-search/alpha-search
Docs: https://alpha-search.github.io/alpha-search
PyPI: pip install alpha-search

We'd love feedback from the quant research and Python communities!

Key differentiators from existing tools:
- OpenBB = data terminal (AGPL). Alpha Search = intelligence layer (MIT).
- Vectorized backtesting + walk-forward validation (most open-source
  tools lack walk-forward)
- Composable signal framework with sentiment integration

Happy to answer questions!
```

### Reddit Community Strategy

```python
# Target communities for Alpha Search launch
REDDIT_COMMUNITIES = {
    "r/algotrading": {
        "focus": "Technical — backtesting, signal framework, execution",
        "post_type": "Showcase with code examples",
        "best_time": "Tuesday-Thursday, 9-11 AM EST",
        "engagement": "Answer technical questions, discuss methodology",
    },
    "r/quant": {
        "focus": "Academic — walk-forward validation, FinBERT, research",
        "post_type": "Technical deep-dive with methodology",
        "best_time": "Monday or Wednesday, 10 AM EST",
        "engagement": "Discuss statistical methods, cite papers",
    },
    "r/quantfinance": {
        "focus": "Professional — portfolio optimization, risk controls",
        "post_type": "Professional tool announcement",
        "best_time": "Tuesday, 11 AM EST",
        "engagement": "Discuss practical applications, industry use cases",
    },
    "r/Python": {
        "focus": "Python ecosystem — architecture, open source, design",
        "post_type": "Open source project launch",
        "best_time": "Saturday, 10 AM EST",
        "engagement": "Discuss Python architecture, Pydantic, design patterns",
    },
    "r/opensource": {
        "focus": "Open source philosophy — MIT license, community building",
        "post_type": "Project launch + contribution invitation",
        "best_time": "Sunday, 2 PM EST",
        "engagement": "Discuss open-source sustainability, licensing",
    },
    "r/fintech": {
        "focus": "Fintech application — trading infrastructure, APIs",
        "post_type": "Fintech tool launch",
        "best_time": "Wednesday, 1 PM EST",
        "engagement": "Discuss fintech applications, broker integrations",
    },
}
```

### Twitter/X and LinkedIn Strategy

```markdown
# Twitter/X Launch Thread Template

Tweet 1/ 🧵 We just open-sourced Alpha Search — a quantitative analysis platform
built in pure Python with an MIT license.

Here's what it does and why we built it 👇

Tweet 2/ The problem: Open-source finance tools give you data (OpenBB is great
at this), but none give you intelligence — signals, backtesting, validation,
execution.

Tweet 3/ Alpha Search fills the gap:
• Composable signal framework (&, |, ~ operators)
• Vectorized backtesting (100x faster)
• Walk-forward validation (prevents overfitting)
• FinBERT sentiment analysis
• Paper trading with risk controls

Tweet 4/ One line to start:
```bash
pip install alpha-search
alpha-search launch  # Opens Streamlit terminal
```

Tweet 5/ The signal framework is my favorite part:
```python
signal = MomentumSignal(20) & SentimentSignal() | MACrossoverSignal(20, 50)
```

Compose indicators, backtest instantly, iterate fast.

Tweet 6/ MIT licensed. Free for commercial use. No AGPL restrictions.

GitHub: github.com/alpha-search/alpha-search
Docs: alpha-search.github.io

Star it, try it, break it — we'd love your feedback 🙏

---

# LinkedIn Launch Post Template

Excited to announce that we're open-sourcing Alpha Search — a quantitative
research and analysis platform built in Python.

What started as a personal project to streamline quantitative research has
grown into a full platform with:

✅ Composable signal generation (technical + sentiment)
✅ Vectorized backtesting with walk-forward validation
✅ FinBERT-powered multi-source sentiment analysis
✅ Paper trading simulator with risk controls
✅ Streamlit-based research terminal
✅ MIT license — free for commercial use

For quantitative researchers, algorithmic traders, and Python developers
who want an open-source alternative to expensive proprietary platforms.

GitHub: [link]
Documentation: [link]
PyPI: pip install alpha-search

#quantitativefinance #python #opensource #fintech #algorithmictrading
```

### GitHub Stars Growth Targets

```python
# scripts/track_growth.py — Growth metrics tracking
import json
from datetime import datetime, timedelta
from pathlib import Path


class GrowthTracker:
    """Track Alpha Search growth metrics against targets."""

    TARGETS = {
        "github_stars": {
            "week_1": 100,
            "month_1": 1000,
            "month_3": 3000,
            "month_6": 5000,
        },
        "pypi_downloads": {
            "week_1": 500,
            "month_1": 5000,
            "month_3": 20000,
            "month_6": 50000,
        },
        "community": {
            "discord_members_week_1": 50,
            "discord_members_month_1": 300,
            "github_contributors_month_1": 10,
            "github_contributors_month_6": 50,
        },
    }

    def __init__(self, tracking_file: str = "project/growth_metrics.json"):
        self.tracking_file = Path(tracking_file)
        self.data = self._load()

    def _load(self) -> dict:
        if self.tracking_file.exists():
            return json.loads(self.tracking_file.read_text())
        return {
            "launch_date": datetime.now().isoformat(),
            "milestones": [],
            "weekly_snapshots": [],
        }

    def record_snapshot(self, stars: int, downloads: int, discord: int = 0):
        """Record a weekly growth snapshot."""
        snapshot = {
            "date": datetime.now().isoformat(),
            "github_stars": stars,
            "pypi_downloads": downloads,
            "discord_members": discord,
            "stars_vs_target": self._vs_target(stars, "github_stars"),
            "downloads_vs_target": self._vs_target(downloads, "pypi_downloads"),
        }
        self.data["weekly_snapshots"].append(snapshot)
        self._save()
        return snapshot

    def _vs_target(self, actual: int, metric: str) -> dict:
        targets = self.TARGETS.get(metric, {})
        return {
            name: {
                "target": target,
                "actual": actual,
                "pct_achieved": round(actual / target * 100, 1) if target > 0 else 0,
                "ahead": actual >= target,
            }
            for name, target in targets.items()
        }

    def generate_report(self) -> str:
        """Generate a growth report comparing actuals to targets."""
        lines = ["# Alpha Search Growth Report", f"Generated: {datetime.now().isoformat()}", ""]

        if not self.data["weekly_snapshots"]:
            return "No data recorded yet."

        latest = self.data["weekly_snapshots"][-1]
        lines.append(f"## Current Metrics (as of {latest['date'][:10]})")
        lines.append(f"- GitHub Stars: {latest['github_stars']}")
        lines.append(f"- PyPI Downloads: {latest['pypi_downloads']}")
        lines.append(f"- Discord Members: {latest['discord_members']}")
        lines.append("")

        lines.append("## Target Progress")
        for period, data in latest["stars_vs_target"].items():
            status = "✅" if data["ahead"] else "⏳"
            lines.append(
                f"- {status} {period}: {data['actual']}/{data['target']} "
                f"({data['pct_achieved']}%)")

        return "\n".join(lines)

    def _save(self):
        self.tracking_file.write_text(json.dumps(self.data, indent=2))


# Growth milestones for celebration and momentum
MILESTONES = [
    (10, "First 10 stars — project is alive!"),
    (50, "50 stars — gaining traction"),
    (100, "100 stars — Week 1 target achieved 🎉"),
    (500, "500 stars — trending on GitHub"),
    (1000, "1000 stars — Month 1 target achieved 🚀"),
    (2500, "2500 stars — half-way to 6-month target"),
    (5000, "5000 stars — Month 6 target achieved 🏆"),
    (10000, "10000 stars — double the target 🌟"),
]
```

### Community Engagement Playbook

```markdown
# Alpha Search Community Engagement Playbook

## Daily Engagement (30 minutes)
- [ ] Respond to all GitHub issues within 24 hours
- [ ] Answer questions in Discussions
- [ ] Monitor and respond to mentions on Twitter/X
- [ ] Check Reddit posts for comments and questions

## Weekly Activities
- [ ] Publish a "This Week in Alpha Search" update on Discussions
- [ ] Share interesting backtest results or research findings
- [ ] Highlight community contributions (PRs, issues, feedback)
- [ ] Post tip or tutorial on Twitter/LinkedIn

## Content Calendar

### Week 1: Launch
- Day 1: HN launch, Reddit posts, Twitter thread, LinkedIn post
- Day 2: Respond to all feedback, fix critical issues
- Day 3: Blog post: "Why We Built Alpha Search"
- Day 4: Twitter tip: signal composition example
- Day 5: "First week update" on Discussions
- Day 6-7: Monitor, respond, iterate

### Week 2-4: Education
- Weekly blog post on a feature (Backtesting, Sentiment, Portfolio)
- Weekly Twitter thread with code examples
- Weekly Reddit engagement in target communities
- Bi-weekly LinkedIn article

### Month 2-3: Community
- Feature community projects using Alpha Search
- Host virtual meetup or AMA
- Publish comparison articles (vs proprietary tools)
- Seek podcast or newsletter appearances

### Month 4-6: Growth
- Enterprise inquiry responses
- Case studies from active users
- Conference submissions (PyCon, QuantStrat)
- Potential partnerships with data providers

## Response Templates

### Thanking a Star Giver
"Thanks for starring Alpha Search! What feature are you most excited about?"

### Responding to a Bug Report
"Thanks for the detailed report! I'll investigate and get back to you within 24 hours."

### Feature Request
"Great idea! I've added it to our roadmap. Would you be interested in contributing?"

### First PR
"Welcome to the Alpha Search community! Thanks for your first contribution. 🎉"
```

### EB1A Green Card Strategy Integration

```python
# EB1A evidence tracking
class EB1AEvidenceTracker:
    """Track evidence for EB1A "Extraordinary Ability" petition.

    EB1A Criteria Met:
    1. Commercial success (PyPI downloads, GitHub stars)
    2. Original contributions (architecture, signal framework)
    3. Critical employment (lead role in multi-agent project)
    4. Judging (code reviews, PR approvals)
    5. Membership (open-source maintainer)
    6. Press (HN front page, tech blog coverage)
    7. High remuneration (salary data)
    """

    EVIDENCE_CATEGORIES = {
        "original_contributions": {
            "description": "Original architecture for quantitative analysis platform",
            "evidence": [
                "700+ commits across 6-week build",
                "Signal ABC with composition operators (patentable concept)",
                "Vectorized backtest engine design",
                "FinBERT sentiment integration pipeline",
                "Walk-forward validation framework",
            ],
        },
        "commercial_success": {
            "description": "Wide adoption and commercial impact",
            "evidence": [
                "GitHub stars growth trajectory",
                "PyPI monthly download counts",
                "Commercial users (tracked via GitHub issues)",
                "Integration requests from fintech companies",
            ],
        },
        "critical_role": {
            "description": "Led multi-agent technical project",
            "evidence": [
                "Architecture decision records (ADRs)",
                "Code review history",
                "Technical specification authorship",
                "Team coordination documentation",
            ],
        },
        "judging": {
            "description": "Evaluated technical work of others",
            "evidence": [
                "PR review history on GitHub",
                "Issue triage and resolution decisions",
                "Architecture review approvals",
            ],
        },
        "press_coverage": {
            "description": "Published material about work",
            "evidence": [
                "Hacker News front page (target)",
                "Technical blog posts",
                "Reddit community engagement",
                "Twitter/LinkedIn reach metrics",
            ],
        },
    }

    @staticmethod
    def generate_evidence_summary() -> str:
        """Generate formatted evidence summary for immigration attorney."""
        lines = ["# EB1A Evidence Summary: Alpha Search Project", ""]
        for category, data in EB1AEvidenceTracker.EVIDENCE_CATEGORIES.items():
            lines.append(f"## {category.replace('_', ' ').title()}")
            lines.append(f"**{data['description']}**")
            lines.append("")
            for item in data["evidence"]:
                lines.append(f"- {item}")
            lines.append("")
        return "\n".join(lines)

    @staticmethod
    def get_recommendation_letter_targets() -> list[dict]:
        """Potential recommenders for EB1A letters."""
        return [
            {
                "role": "Senior Quantitative Researcher at hedge fund",
                "focus": "Technical originality and practical impact",
            },
            {
                "role": "Professor of Financial Engineering",
                "focus": "Academic significance of walk-forward validation approach",
            },
            {
                "role": "Open-source maintainer of major Python finance library",
                "focus": "Standing in the open-source quant community",
            },
            {
                "role": "CTO of fintech startup using Alpha Search",
                "focus": "Commercial adoption and business value",
            },
        ]
```

## Responsibilities

1. Set up GitHub repository with professional structure (README, templates, workflows)
2. Publish PyPI package with proper versioning and metadata
3. Create and post Hacker News launch thread
4. Post to all target Reddit communities with appropriate messaging
5. Publish Twitter/X launch thread and ongoing engagement
6. Publish LinkedIn launch post for professional network
7. Deploy documentation to GitHub Pages
8. Track growth metrics against targets (stars, downloads, community)
9. Execute community engagement playbook (daily, weekly, monthly)
10. Integrate EB1A evidence collection into launch activities
11. Monitor and respond to all community feedback within 24 hours
12. Generate weekly growth reports comparing actuals to targets

## Inputs

- Final codebase from all implementation agents
- pyproject.toml with release metadata
- Documentation site from Testing & DevOps agent
- Competitive positioning content from OpenBB Differentiation agent
- GitHub organization access
- PyPI account credentials
- Social media accounts for posting

## Outputs

- Live GitHub repository with full project structure
- Published PyPI package (alpha-search)
- Hacker News launch post and engagement
- Reddit posts across 6 target communities
- Twitter/X launch thread and ongoing content
- LinkedIn launch post
- Documentation site live on GitHub Pages
- Weekly growth reports with target tracking
- Community engagement log
- EB1A evidence documentation

## Required Files to Create or Modify

- `README.md` — project README (create)
- `CONTRIBUTING.md` — contribution guidelines (create)
- `CODE_OF_CONDUCT.md` — community standards (create)
- `SECURITY.md` — security policy (create)
- `.github/ISSUE_TEMPLATE/` — issue templates (create)
- `.github/PULL_REQUEST_TEMPLATE.md` — PR template (create)
- `scripts/setup_github_repo.py` — repo setup automation (create)
- `scripts/publish_to_pypi.py` — PyPI publishing (create)
- `scripts/track_growth.py` — growth metrics (create)
- `docs/launch/` — launch content folder (create)
- `docs/eb1a/` — EB1A evidence folder (create)

## Implementation Checklist

- [ ] Create GitHub repository with professional structure
- [ ] Write compelling README.md with quickstart and features
- [ ] Set up issue templates (bug report, feature request)
- [ ] Create PR template
- [ ] Write CONTRIBUTING.md with development setup
- [ ] Add CODE_OF_CONDUCT.md and SECURITY.md
- [ ] Configure branch protection rules
- [ ] Publish v1.0.0 to PyPI (TestPyPI first, then production)
- [ ] Post Hacker News "Show HN" thread
- [ ] Post to 6 Reddit communities with tailored messaging
- [ ] Publish Twitter/X launch thread (6-8 tweets)
- [ ] Publish LinkedIn launch post
- [ ] Deploy documentation to GitHub Pages
- [ ] Set up growth tracking (stars, downloads, community)
- [ ] Begin daily community engagement
- [ ] Document EB1A evidence (contributions, adoption, press)
- [ ] Send first weekly growth report
- [ ] Identify and contact potential recommendation letter writers

## Testing Checklist

- [ ] GitHub repository loads correctly with all files
- [ ] README renders correctly on GitHub
- [ ] `pip install alpha-search` works from PyPI
- [ ] `alpha-search launch` starts the Streamlit app
- [ ] Issue templates render correctly
- [ ] Documentation site loads on GitHub Pages
- [ ] Growth tracker records and reports correctly
- [ ] All launch posts are within platform character limits
- [ ] PyPI package metadata displays correctly
- [ ] GitHub Actions badges show correct status
- [ ] Version tag matches PyPI release

## Definition of Done

- GitHub repository is public with professional README and structure
- PyPI package `alpha-search` is installable with `pip install alpha-search`
- HN launch post is live with engagement
- Reddit posts are live in all target communities
- Twitter/X and LinkedIn posts are published
- Documentation is live on GitHub Pages
- Growth tracking system is recording metrics
- Community engagement playbook is active
- EB1A evidence documentation is started
- First weekly growth report is distributed

## Example Prompt

> You are the Alpha Search Launch Operator. Execute the full launch: set up the GitHub repository with README, issue templates, and branch protection; publish v1.0.0 to PyPI (via TestPyPI first); post the HN "Show HN" thread; post to r/algotrading, r/quant, and r/Python; publish a Twitter launch thread and LinkedIn post; deploy docs to GitHub Pages; and set up growth tracking against targets of 100 stars Week 1, 1000 Month 1, 5000 Month 6. Document EB1A evidence points throughout.