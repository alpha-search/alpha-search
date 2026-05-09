# Security Policy

This document outlines the security policy for Alpha Search, including supported versions, how to report vulnerabilities, and our disclosure timeline.

**Project:** Alpha Search — Algorithmic Trading & Quantitative Analysis Platform
**Contact:** security@alpha-search.io

---

## Supported Versions

The following versions of Alpha Search are currently supported with security updates:

| Version | Status | Supported Until |
|---------|--------|-----------------|
| 0.x (latest) | Active development | Next minor release + 30 days |
| < 0.1.0 | Pre-release | Best effort only |

> **Note:** Alpha Search is currently in active pre-release development. We strongly recommend always using the latest version from the `main` branch or the most recent release. No long-term support (LTS) releases are available at this stage.

### Python Version Support

Alpha Search supports the following Python versions. Security patches will be provided for supported Python versions only:

| Python | Status |
|--------|--------|
| 3.12 | Supported |
| 3.11 | Supported |
| 3.10 | Supported |
| < 3.10 | Not supported |

---

## Reporting a Vulnerability

If you discover a security vulnerability in Alpha Search, please report it responsibly.

### Reporting Channels

**Primary (preferred):** Email **security@alpha-search.io**

- Provide a detailed description of the vulnerability
- Include steps to reproduce the issue
- If applicable, provide a minimal proof-of-concept
- Include your assessment of severity (low, medium, high, critical)

**Alternative:** If you cannot use email, contact the maintainers via the [Security Advisory](https://github.com/alpha-search/alpha-search/security/advisories) feature on GitHub.

### What to Include

A good vulnerability report should include:

1. **Description**: Clear explanation of the vulnerability
2. **Affected versions**: Which Alpha Search versions are impacted
3. **Affected components**: Which modules or features are involved
4. **Reproduction steps**: Step-by-step instructions to reproduce
5. **Impact assessment**: What an attacker could achieve
6. **Suggested fix**: If you have a proposed remediation (optional)
7. **Your contact**: How to reach you for follow-up questions

### What Happens Next

| Timeframe | Action |
|-----------|--------|
| Within 24 hours | Acknowledgment of your report |
| Within 7 days | Initial assessment and severity classification |
| Within 14 days | Patch developed and tested |
| Within 21 days | Patch released and advisory published |

We will keep you informed throughout the process. If you prefer to remain anonymous, please let us know in your initial report.

---

## Disclosure Policy

Alpha Search follows a **responsible disclosure** model:

1. **Private resolution**: Once a report is received, we work privately with the reporter to understand and fix the issue.
2. **Patch before disclosure**: We release a patch before publicly disclosing the vulnerability.
3. **Credit**: Reporters who follow responsible disclosure will be publicly credited in the security advisory (unless they wish to remain anonymous).
4. **No legal action**: Alpha Search will not pursue legal action against security researchers who:
   - Report vulnerabilities in good faith
   - Do not exploit vulnerabilities beyond what is necessary for verification
   - Do not access, modify, or delete data belonging to others
   - Provide reasonable time for us to address the issue before public disclosure

---

## Security Considerations and Scope

### In Scope

The following are considered security-relevant issues for Alpha Search:

- **Credential exposure**: Hardcoded API keys, tokens, or passwords in source code
- **Data leakage**: Unintended exposure of user data, trading history, or portfolio information
- **Injection vulnerabilities**: SQL injection, command injection, or code execution risks
- **Dependency vulnerabilities**: Security issues in third-party dependencies that affect Alpha Search
- **Path traversal**: Unauthorized file system access through user input
- **Unsafe deserialization**: Pickle or JSON deserialization of untrusted data
- **SSRF**: Server-side request forgery through data provider configurations
- **DoS**: Denial of service through resource exhaustion or crash triggers

### Out of Scope

The following are **not** considered security vulnerabilities in Alpha Search:

- **User-configured API keys**: API keys stored in user-managed configuration files (`~/.alpha-search/config.yaml`) are the user's responsibility to protect
- **Self-hosted deployments**: Security of self-hosted instances (network configuration, firewall rules, OS-level security) is the operator's responsibility
- **Trading losses**: Alpha Search is an educational and research tool. Financial losses resulting from trading decisions, strategy performance, or market conditions are not security issues
- **Third-party data accuracy**: Incorrect or delayed data from external market data providers
- **Physical security**: Security of the machine running Alpha Search
- **Social engineering**: Attacks targeting users rather than the software

### Known Limitations

The following security limitations are known and accepted:

1. **No encryption at rest**: Local data files (SQLite databases, CSV exports) are not encrypted. Protect your file system.
2. **Local execution model**: Alpha Search is designed to run locally or on infrastructure you control. It does not include authentication or authorization mechanisms.
3. **API key storage**: API keys are stored in plain text in local configuration files. Use appropriate file permissions (`chmod 600`).
4. **No audit logging**: User actions within the application are not logged for security auditing.
5. **Network communications**: HTTPS is used for external API calls where supported by the data provider, but certificate verification can be disabled in configuration (not recommended).
6. **Pickle usage**: Some caching mechanisms may use `pickle` for serialization. Only load cache files you created.

---

## Security Best Practices for Users

1. **Keep Alpha Search updated**: Always use the latest version.
2. **Protect your config files**: Set restrictive permissions on `~/.alpha-search/`:
   ```bash
   chmod 700 ~/.alpha-search
   chmod 600 ~/.alpha-search/config.yaml
   ```
3. **Use environment variables** for API keys instead of hardcoding them.
4. **Validate data provider configurations**: Only use trusted data sources.
5. **Run in a virtual environment**: Isolate Alpha Search dependencies from system packages.
6. **Review code before running**: Especially for strategies and plugins from external sources.
7. **Backup your data**: Regularly back up local databases and configuration.

---

## Security Advisories

Published security advisories will be listed in the [GitHub Security Advisories](https://github.com/alpha-search/alpha-search/security/advisories) section and summarized below:

| Advisory | Severity | Affected Versions | Patched In | CVE (if assigned) |
|----------|----------|-------------------|------------|-------------------|
| None published | — | — | — | — |

---

## Contact

For security-related questions or concerns:

- **Email:** security@alpha-search.io
- **GPG Key:** Available upon request via email

For general inquiries, use **team@alpha-search.io**.

---

*Last updated: 2025-01*
