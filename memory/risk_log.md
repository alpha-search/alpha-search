# Risk Log

Risk decisions, flags, and blocks recorded by the risk controller.

---

### [2025-01-10 17:00:00 UTC] 🟡 Release Auditor

**Decision:** 🚩 FLAG
**Object:** `deployment` — `docker-compose`
**Severity:** medium

**Reason:** Docker Compose build has not been verified in a clean environment.
The compose file exists and references correct service definitions, but it has
not been tested on a fresh machine without pre-existing images or volumes.
Risk of environment-specific issues when new contributors clone the repo.

**Recommended Action:** Run `docker compose build --no-cache` and verify
all services start correctly in a clean checkout.

---

### [2025-01-10 17:05:00 UTC] 🟡 Release Auditor

**Decision:** 🚩 FLAG
**Object:** `testing` — `pytest-clean-venv`
**Severity:** medium

**Reason:** Full pytest suite has not been executed in a clean virtual
environment. Tests pass in the development environment, but dependency
resolution or version conflicts may exist in a fresh install. This is a
standard release readiness gap.

**Recommended Action:** Create a fresh venv, install from `requirements.txt`,
and run the full test suite (`pytest tests/ -v`).

---

### [2025-01-10 17:10:00 UTC] 🟡 Release Auditor

**Decision:** 🚩 FLAG
**Object:** `deployment` — `streamlit-live`
**Severity:** medium

**Reason:** Streamlit dashboard has not been tested with live data feeds.
The UI renders correctly with sample data, but live data integration
(path: data → signals → portfolio → UI) has only been tested in mock mode.
Risk of runtime errors when real data providers are connected.

**Recommended Action:** Run `streamlit run alpha_search/ui/streamlit_app.py` with
live YFinance data and verify all dashboard components render correctly.

---

*New entries are appended automatically as risk decisions are logged.*
### [2026-05-08 23:59:56 UTC] 🟡 release_auditor

**Decision:** 🚩 FLAGGED
**Object:** `deployment` — `streamlit-dashboard`
**Severity:** medium

**Reason:** Streamlit dashboard not tested with live data feeds
---

