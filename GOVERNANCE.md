# Alpha Search Governance Model

This document describes the governance structure for Alpha Search, a community-driven open-source quantitative trading and analysis platform.

**Project:** Alpha Search
**License:** Apache 2.0
**Contact:** team@alpha-search.io

---

## Table of Contents

- [Project Structure](#project-structure)
- [Decision Making](#decision-making)
- [Release Cycle](#release-cycle)
- [Conflict Resolution](#conflict-resolution)
- [Adding Maintainers](#adding-maintainers)
- [Deprecation Policy](#deprecation-policy)

---

## Project Structure

Alpha Search follows a **maintainer-led, community-driven** governance model. The project has three levels of participation:

### 1. Community Contributors

Anyone who uses or contributes to Alpha Search.

- Submit issues, feature requests, and bug reports
- Open pull requests
- Participate in discussions
- Help answer questions from other users
- Improve documentation

**No formal requirements.** All contributions are welcome.

### 2. Core Contributors

Regular contributors who have demonstrated commitment and technical competence.

**Privileges:**
- Issue and PR triage (labeling, assignment)
- Review pull requests
- Merge documentation and minor fix PRs
- Approve workflows for first-time contributors

**Requirements:**
- At least 5 merged, non-trivial pull requests
- Consistent contribution activity over at least 2 months
- Good understanding of the codebase
- Constructive participation in code reviews and discussions

**Process:** Existing maintainers nominate and vote (simple majority).

### 3. Maintainers

Project stewards responsible for strategic direction, releases, and governance decisions.

**Current Maintainers:**

| Name | GitHub | Role | Since |
|------|--------|------|-------|
| TBD | @maintainer-1 | Lead Maintainer | 2025 |

**Privileges:**
- All core contributor privileges
- Merge any pull request (including major features)
- Create releases and tags
- Manage repository settings and CI/CD
- Make architectural decisions
- Add or remove core contributors and maintainers
- Update governance documents

**Responsibilities:**
- Review significant PRs within 3 business days
- Triage issues and set milestones
- Ensure CI/CD and quality standards are maintained
- Communicate roadmap and decisions to the community
- Mentor new contributors
- Resolve conflicts per [Conflict Resolution](#conflict-resolution)

---

## Decision Making

### Types of Decisions

| Category | Examples | Decision Maker | Process |
|----------|----------|----------------|---------|
| **Trivial** | Typo fixes, linting, dependency patches | Any maintainer | Direct merge |
| **Minor** | Bug fixes, small features, docs updates | PR review approval | 1 maintainer approval |
| **Major** | New modules, API changes, dependency additions | Maintainers consensus | 2+ maintainer approvals |
| **Strategic** | Architecture changes, governance changes, roadmap | All maintainers vote | 2/3 majority |

### Consensus Seeking

For most decisions, we follow a **consensus-seeking** approach:

1. A proposal is made (in an issue, PR, or discussion).
2. Community members provide feedback during a **7-day comment period** (14 days for strategic decisions).
3. Maintainers synthesize feedback and make a decision.
4. If consensus cannot be reached, maintainers vote (see below).

### Voting

- **Eligible voters:** Current maintainers
- **Quorum:** At least 60% of maintainers must participate
- **Threshold:**
  - Major decisions: Simple majority (50% + 1)
  - Strategic decisions: 2/3 majority
- **Method:** GitHub comment reactions (+1 / -1) or dedicated discussion thread
- **Duration:** 7 days for major, 14 days for strategic
- **Tie-breaking:** Lead maintainer casts the deciding vote

---

## Release Cycle

Alpha Search follows [Semantic Versioning 2.0.0](https://semver.org/):

```
MAJOR.MINOR.PATCH
```

| Component | When Incremented |
|-----------|-----------------|
| **MAJOR** | Breaking API changes, incompatible strategy format changes |
| **MINOR** | New features, new data providers, new indicators (backward-compatible) |
| **PATCH** | Bug fixes, performance improvements, documentation updates |

### Release Schedule

| Release Type | Frequency | Trigger |
|-------------|-----------|---------|
| **Patch** | As needed | Critical bugs, security fixes |
| **Minor** | Monthly (target) | Feature completion, accumulated improvements |
| **Major** | As needed | Breaking changes or significant milestones |

### Release Process

1. **Prepare**: A maintainer creates a release branch (`release/vX.Y.Z`) from `main`.
2. **Version bump**: Update version in `pyproject.toml` and `alpha_search/__init__.py`.
3. **Changelog**: Update `CHANGELOG.md` with all changes since the last release.
4. **QA**: Run the full test suite and integration tests.
5. **Tag**: Create an annotated Git tag: `git tag -a vX.Y.Z -m "Release vX.Y.Z"`.
6. **Publish**: Push the tag. CI will build and publish to PyPI.
7. **Announce**: Post release notes on GitHub Discussions.

### Pre-Releases

Alpha and beta versions may be published:

- Alpha (`a`): `v0.2.0a1` — Early testing, unstable
- Beta (`b`): `v0.2.0b1` — Feature-complete, testing phase
- Release candidate (`rc`): `v0.2.0rc1` — Final testing before stable

Install pre-releases with: `pip install --pre alpha-search`

---

## Conflict Resolution

We strive to resolve disagreements constructively and transparently.

### Process

1. **Direct discussion**: The involved parties discuss the issue in the relevant PR, issue, or discussion thread.
2. **Mediation**: If direct discussion stalls, a neutral maintainer mediates.
3. **Maintainer vote**: If mediation does not resolve the issue within 14 days, maintainers vote per the [Decision Making](#decision-making) process.
4. **Escalation**: In exceptional cases, the lead maintainer makes a final decision.

### Principles

- **Assume good intent**: All participants are working toward the project's success.
- **Focus on technical merit**: Decisions are based on technical arguments, not personal preferences.
- **Respectful communication**: Follow the [Code of Conduct](CODE_OF_CONDUCT.md) at all times.
- **Document decisions**: Rationale for decisions is recorded in the issue or PR thread.

### Code of Conduct Enforcement

Violations of the Code of Conduct are handled separately from technical disagreements. See [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) for the enforcement process.

---

## Adding Maintainers

New maintainers are added through a nomination and voting process.

### Nomination Criteria

A nominee should:

- Be an active core contributor for at least 3 months
- Demonstrate technical competence and good judgment
- Show commitment to the project's values and code of conduct
- Have a history of constructive collaboration
- Understand the project's architecture and roadmap

### Process

1. **Nomination**: An existing maintainer opens a private discussion with other maintainers proposing the candidate.
2. **Candidate consent**: The nominee must accept the nomination.
3. **Vote**: Maintainers vote (2/3 majority required).
4. **Onboarding**: The new maintainer is added to the repository and relevant services.
5. **Announcement**: The addition is announced to the community.

### Maintainer Removal

Maintainers may be removed if they:

- Violate the Code of Conduct
- Are inactive for 6+ months without notice
- Consistently fail to fulfill maintainer responsibilities

Removal requires a 2/3 vote by other maintainers. The affected maintainer will be notified privately and given an opportunity to respond.

---

## Deprecation Policy

To balance innovation with stability:

1. **Deprecation warnings**: Features marked for removal will emit warnings for at least **2 minor releases** before removal.
2. **Migration guide**: A migration path will be documented in the release notes.
3. **Emergency exceptions**: Security-critical deprecations may be expedited with maintainer approval.

---

## Governance Changes

This document may be amended through the strategic decision process (2/3 maintainer vote, 14-day comment period).

Changes are tracked in the [governance changelog](#changelog) below.

### Changelog

| Date | Change | Author |
|------|--------|--------|
| 2025-01 | Initial governance document | Maintainers |

---

## Contact

For governance-related questions:

- **Email:** team@alpha-search.io
- **Discussions:** [GitHub Discussions](https://github.com/alpha-search/alpha-search/discussions)

---

*This document is licensed under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).*
