# Alpha Search Naming Decisions

> **Single Source of Truth** — All naming and branding decisions for the Alpha Search project.
>
> This document is authoritative. All project assets (code, docs, domains, emails) must align with these decisions.
>
> *Version: 1.0* | *Effective: 2025-01-15* | *Owner: Kalyan Dinavahi*

---

## Executive Summary

| Decision | Value | Status |
|----------|-------|--------|
| GitHub Organization | `alpha-search` | **FINAL** |
| Primary Domain | `alpha-search.io` | **FINAL** |
| PyPI Package | `alpha-search` | **FINAL** (pre-existing decision) |
| Python Import | `alpha_search` | **FINAL** (pre-existing decision) |
| CLI Command | `alpha-search` | **FINAL** (pre-existing decision) |
| Positioning | Open-source quantitative research toolkit | **FINAL** |

---

## 1. GitHub Organization

**Name:** `alpha-search`

```
https://github.com/alpha-search
```

**Rationale:**
- Exact match to the PyPI package name — zero cognitive overhead
- Descriptive and discoverable — developers find it by searching "quant os"
- Hyphenated naming follows OSS convention (eslint, rust-lang, prettier)
- No brand collisions or existing usage
- Verbal clarity: "quant dash OS" is unambiguous

**Alternatives considered:** `quantos` (rejected: brand collision), `vector-alpha` (rejected: disconnected), `axiom-alpha` (rejected: sounds proprietary), `openquant-labs` (rejected: signals experimental/hobbyist)

---

## 2. Repository Structure

| Repo | URL | Purpose |
|------|-----|---------|
| Main package | `github.com/alpha-search/alpha-search` | Core Python package — `pip install alpha-search` |
| Documentation | `github.com/alpha-search/docs` | Docs site source — published to alpha-search.io/docs |
| Examples | `github.com/alpha-search/examples` | Jupyter notebooks, tutorials, cookbook |
| Agent framework | `github.com/alpha-search/agent-skills` | AI agent integration layer |
| Strategy research | `github.com/alpha-search/strategy-lab` | Research templates, backtesting notebooks |
| Community (optional) | `github.com/alpha-search/community` | GitHub Discussions, Q&A |

---

## 3. Domain

**Primary:** `alpha-search.io`

```
https://alpha-search.io           # Main site
https://www.alpha-search.io       # Redirects to apex
https://alpha-search.io/docs      # Documentation
```

**Registrar:** Porkbun (lowest cost, free WHOIS privacy)
**DNS:** Cloudflare (free plan)
**Hosting:** GitHub Pages (free)

**Rationale:**
- `.io` is the established TLD for open-source developer tools
- Exact match to GitHub org and PyPI package — one name everywhere
- Moderate cost (~$35/year for `.io`)
- Trusted and expected by developer audience

**Secondary domains (optional, acquire if budget allows):**
| Domain | Purpose | Priority |
|--------|---------|----------|
| `quantos.ai` | Redirect to primary; future AI landing page | Nice-to-have |
| `quantos.dev` | Redirect to primary | Optional |

**Alternatives considered:** `quantos.ai` (rejected: `.ai` too expensive, slight name mismatch), `quantos.dev` (rejected: `.dev` feels generic), `openquantlabs.ai` (rejected: too long, doesn't match product)

---

## 4. Package Names

| Context | Name | Example Usage |
|---------|------|---------------|
| PyPI install | `alpha-search` | `pip install alpha-search` |
| Python import | `alpha_search` | `import alpha_search` |
| CLI command | `alpha-search` | `alpha-search --version` |

**Rationale:**
- PyPI package uses hyphen (`alpha-search`) — standard for Python packages
- Python import uses underscore (`alpha_search`) — PEP 8 requirement
- CLI matches package name — consistent user experience
- Pre-existing decisions, confirmed correct, not to be changed

---

## 5. Email Addresses

All email forwards to: `your-email@example.com`

| Address | Purpose | Routing |
|---------|---------|---------|
| `hello@alpha-search.io` | General inquiries, partnerships, press | ImprovMX → Gmail |
| `research@alpha-search.io` | Research collaborations, academic inquiries | ImprovMX → Gmail |
| `support@alpha-search.io` | Technical support, bug reports | ImprovMX → Gmail |
| `team@alpha-search.io` | Team-wide distribution | ImprovMX → Gmail |
| `kalyan@alpha-search.io` | Founder direct address | ImprovMX → Gmail |
| `security@alpha-search.io` | Security disclosures | ImprovMX → Gmail |
| `*@alpha-search.io` | Catch-all — any address reaches inbox | ImprovMX → Gmail |

**Send-as configured in Gmail:** `hello@alpha-search.io`, `research@alpha-search.io`

**Infrastructure:**
- Receiving: ImprovMX (free tier) + Cloudflare Email Routing (backup)
- Sending: ImprovMX SMTP credentials configured in Gmail
- SPF, DKIM, DMARC: Configured for deliverability

---

## 6. Visual Identity

| Element | Decision |
|---------|----------|
| Primary color | Deep Navy `#0A1628` |
| Accent color | Cobalt Blue `#2563EB` |
| Heading font | Inter (600-700 weight) |
| Body font | Inter (400-500 weight) |
| Code font | JetBrains Mono (400 weight) |
| Design feel | Institutional, modern, minimal — NOT retail, NOT gamified |
| Logo direction | Geometric monogram or typographic wordmark |

---

## 7. Positioning Statement

**What Alpha Search is:**
- An open-source quantitative research toolkit for Python
- Institutional-quality software, freely licensed
- Research-first: backtesting, data analysis, strategy development
- AI-native: built for agent-assisted research workflows

**What Alpha Search is NOT:**
- A hedge fund or investment advisory service
- A trading bot or automated trading system
- Financial advice or a get-rich-quick tool
- A commercial product (the core is and always will be open-source)

**Target audience:** Quantitative researchers, academic finance, data scientists, serious individual researchers who write Python.

---

## 8. Cost Summary

| Item | Monthly | Annual |
|------|---------|--------|
| Domain (`alpha-search.io`) | ~$3 | ~$35 |
| DNS (Cloudflare) | FREE | FREE |
| Email (ImprovMX) | FREE | FREE |
| Hosting (GitHub Pages) | FREE | FREE |
| SSL (Cloudflare) | FREE | FREE |
| **Total** | **~$3** | **~$35** |

---

## 9. Decision Log

| Date | Decision | Reason | Decided By |
|------|----------|--------|------------|
| Pre-2025 | PyPI: `alpha-search`, import: `alpha_search`, CLI: `alpha-search` | Technical correctness, PEP 8 | Kalyan Dinavahi |
| 2025-01-15 | GitHub org: `alpha-search` | Exact product match, discoverability | Kalyan Dinavahi |
| 2025-01-15 | Domain: `alpha-search.io` | OSS convention, exact match, trust | Kalyan Dinavahi |
| 2025-01-15 | Email: ImprovMX + Cloudflare | Free, professional, reliable | Kalyan Dinavahi |
| 2025-01-15 | Color: Deep Navy + Cobalt | Institutional, not retail | Kalyan Dinavahi |
| 2025-01-15 | Font: Inter + JetBrains Mono | Modern, free, developer-standard | Kalyan Dinavahi |

---

## 10. Change Process

Naming decisions in this document require explicit approval to change.

**Can change freely:**
- Secondary domains (redirects)
- Additional email aliases
- Color shade variations (within palette)

**Requires discussion:**
- Primary domain change
- GitHub org rename (highly disruptive, avoid if possible)
- Package name changes (highly disruptive, avoid if possible)

**Will not change:**
- PyPI package name: `alpha-search`
- Python import name: `alpha_search`
- CLI command: `alpha-search`
- Positioning as research toolkit (not hedge fund)

---

## 11. Quick Reference Card

```
GitHub:     https://github.com/alpha-search
Website:    https://alpha-search.io
Docs:       https://alpha-search.io/docs
PyPI:       https://pypi.org/project/alpha-search/
Email:      hello@alpha-search.io

Install:    pip install alpha-search
Import:     import alpha_search
CLI:        alpha-search --help
```

---

*This document is the single source of truth for all Alpha Search naming and branding decisions. When in doubt, reference this document.*

*For implementation details, see:*
- `branding.md` — Full branding analysis and visual identity guidelines
- `domain-email-setup.md` — Step-by-step domain and email configuration
