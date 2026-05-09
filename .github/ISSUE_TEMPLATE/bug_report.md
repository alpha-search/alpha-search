---
name: Bug Report
about: Report a bug or unexpected behavior in Alpha Search
title: "[BUG] "
labels: ["bug", "triage"]
assignees: []
---

## Bug Description

A clear and concise description of what the bug is.

## Environment

| Component | Version |
|-----------|---------|
| Alpha Search | `python -m alpha_search --version` |
| Python | `python --version` |
| OS | e.g. Ubuntu 22.04, macOS 14, Windows 11 |
| Installation method | `pip`, `pip install -e .`, Docker |

## Steps to Reproduce

1. Run command '...'
2. With configuration '...'
3. See error

```python
# Minimal reproducible example
from alpha_search import Engine

engine = Engine()
engine.scan(symbols=["RELIANCE.NS"])
```

## Expected Behavior

A clear description of what you expected to happen.

## Actual Behavior

A clear description of what actually happened.

## Logs / Error Messages

```
Paste full error messages, stack traces, or relevant logs here.
Do not truncate or summarize — include the complete output.
```

## Additional Context

- Does the issue happen consistently or intermittently?
- Does it happen with specific symbols or all symbols?
- Have you tried with a fresh virtual environment?
- Any recent changes to your system or Alpha Search configuration?

## Possible Fix

If you have an idea of what might be causing the issue or how to fix it, describe it here.
