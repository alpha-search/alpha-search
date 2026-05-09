# Security Best Practices for Alpha Search

> **Classification:** Operational Security Guide
> **Applies to:** Contributors, maintainers, self-hosted users
> **Last updated:** v0.1.0

---

## Table of Contents

1. [Principles](#principles)
2. [API Key Management](#api-key-management)
3. [Zerodha Token Handling (Indian Markets)](#zerodha-token-handling)
4. [GitHub Secrets](#github-secrets)
5. [Environment Variables](#environment-variables)
6. [Docker Security](#docker-security)
7. [User Authentication (Phase 3)](#user-authentication)
8. [Incident Response](#incident-response)
9. [Security Checklist](#security-checklist)

---

## Principles

All security decisions in the Alpha Search project follow these principles:

| Principle | Description |
|---|---|
| **Defense in depth** | Multiple layers of security, no single point of failure |
| **Least privilege** | Access only what is necessary, for the minimum time required |
| **Fail secure** | If something breaks, it fails to a secure state |
| **Never trust input** | Validate all external data: prices, API responses, user input |
| **Security by default** | Secure configurations out of the box, no opt-in required |
| **Transparency** | Security issues disclosed promptly and honestly |

---

## API Key Management

### Rule 1: Environment Variables Only

**NEVER** hardcode API keys, secrets, or tokens in source code, notebooks, or configuration files.

**Correct:**
```python
import os

api_key = os.environ["BINANCE_API_KEY"]
api_secret = os.environ["BINANCE_SECRET"]
```

**Incorrect (will be rejected in code review):**
```python
api_key = "abc123xyz789"  # NEVER DO THIS
api_secret = "super_secret"  # NEVER DO THIS
```

### Rule 2: .env File (Local Development Only)

For local development, use a `.env` file that is **never committed to git**:

```bash
# .env (this file is in .gitignore)
BINANCE_API_KEY=your_actual_key_here
BINANCE_SECRET=your_actual_secret_here
```

```python
from dotenv import load_dotenv
import os

load_dotenv()  # Loads .env file
api_key = os.environ["BINANCE_API_KEY"]
```

The repository includes `.env.example` (template) which IS committed to git:

```bash
# .env.example (committed to git -- NO REAL VALUES)
BINANCE_API_KEY=your_key_here
BINANCE_SECRET=your_secret_here
```

### Rule 3: Pre-Commit Hook for Secret Detection

Install the pre-commit hook to prevent accidental commits of secrets:

```bash
# Install pre-commit hooks
pre-commit install

# The following hooks are configured:
# - detect-private-key: Detects private keys in committed files
# - detect-aws-credentials: Detects AWS credentials
# - git-secrets: Pattern-based secret detection
```

`.pre-commit-config.yaml`:
```yaml
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.5.0
    hooks:
      - id: detect-private-key
      - id: detect-aws-credentials
        args: ["--allow-missing-credentials"]

  - repo: https://github.com/awslabs/git-secrets
    rev: 1.3.0
    hooks:
      - id: git-secrets
```

### Rule 4: Key Rotation Schedule

| Key Type | Rotation Frequency | Process |
|---|---|---|
| Exchange API keys (trading) | Every 90 days | Generate new key, update env, revoke old |
| Exchange API keys (read-only) | Every 180 days | Generate new key, update env, revoke old |
| News API keys | Every 180 days | Regenerate in provider dashboard |
| GitHub tokens | Every 90 days | Regenerate in GitHub settings |
| Database credentials | Every 180 days | Rotate via infrastructure automation |
| JWT signing keys | Every 90 days | Rotate with zero-downtime key rollover |

**Rotation reminder script:**
```bash
#!/bin/bash
# scripts/rotate-keys.sh
# Add this to your cron: 0 9 1 */3 * /path/to/scripts/rotate-keys.sh

echo "Key rotation reminder: $(date)"
echo "Next actions:"
echo "1. Log into each exchange dashboard"
echo "2. Generate new API key pair"
echo "3. Update environment variables"
echo "4. Test connectivity"
echo "5. Revoke old key pair"
echo "6. Update key rotation log: docs/security/key-rotation-log.md"
```

### Rule 5: Principle of Least Privilege for API Keys

When creating API keys on exchanges:

| Permission | When to Use |
|---|---|
| **Read-only** | Default for all Alpha Search deployments |
| **Spot trading** | Only if running live trading (not research) |
| **Withdrawal** | **NEVER** -- Alpha Search never needs withdrawal permission |
| **Futures/Options** | Only if specifically trading derivatives |

**Recommended exchange key settings:**
```
Binance:
  - Enable Reading: YES
  - Enable Spot & Margin Trading: NO (use paper trading)
  - Enable Withdrawal: NO
  - IP restriction: YES (whitelist your server IP)

Zerodha (Kite):
  - Order placement: NO (unless live trading)
  - Holdings/Margins read: YES
  - IP restriction: YES
```

---

## Zerodha Token Handling

### Architecture

Alpha Search integrates with Zerodha Kite for Indian market data. The token management follows this flow:

```
User Login via Kite Connect
       |
       v
+--------------+     +-------------+     +-------------+
|  Auth Code   | --> |  Token Gen  | --> |   Redis     |
|  (one-time)  |     |  (server)   |     |  (TTL: 1d)  |
+--------------+     +-------------+     +-------------+
                                                |
                                         +-------------+
                                         |  Encrypted  |
                                         |   at Rest   |
                                         +-------------+
```

### Implementation

```python
# alpha_search/data/zerodha_auth.py
"""Zerodha token management with secure storage."""

import os
import redis
import hashlib
import logging
from datetime import datetime, timedelta
from cryptography.fernet import Fernet
from kiteconnect import KiteConnect

logger = logging.getLogger(__name__)

# Encryption key from environment (must be set)
_ENCRYPTION_KEY = os.environ.get("ZERODHA_ENCRYPTION_KEY")
if not _ENCRYPTION_KEY:
    raise RuntimeError(
        "ZERODHA_ENCRYPTION_KEY environment variable must be set. "
        "Generate one with: python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'"
    )

_fernet = Fernet(_ENCRYPTION_KEY.encode())
_redis = redis.Redis(
    host=os.environ.get("REDIS_HOST", "localhost"),
    port=int(os.environ.get("REDIS_PORT", 6379)),
    password=os.environ.get("REDIS_PASSWORD"),
    decode_responses=False,  # We store encrypted bytes
)


def store_tokens(access_token: str, refresh_token: str, user_id: str) -> None:
    """Store tokens in Redis with encryption and TTL.

    Tokens are:
    1. Encrypted at rest using Fernet symmetric encryption
    2. Stored in Redis with 24-hour TTL
    3. Never logged (only a hash prefix is logged for debugging)
    """
    token_hash = hashlib.sha256(access_token.encode()).hexdigest()[:8]
    logger.info(f"Storing tokens for user {user_id} (token hash: {token_hash}...)")

    encrypted_access = _fernet.encrypt(access_token.encode())
    encrypted_refresh = _fernet.encrypt(refresh_token.encode())

    key_prefix = f"zerodha:tokens:{user_id}"
    pipe = _redis.pipeline()
    pipe.setex(f"{key_prefix}:access", timedelta(days=1), encrypted_access)
    pipe.setex(f"{key_prefix}:refresh", timedelta(days=7), encrypted_refresh)
    pipe.execute()


def retrieve_access_token(user_id: str) -> str | None:
    """Retrieve decrypted access token from Redis."""
    key = f"zerodha:tokens:{user_id}:access"
    encrypted = _redis.get(key)
    if encrypted is None:
        return None
    return _fernet.decrypt(encrypted).decode()


def refresh_access_token(user_id: str) -> str:
    """Refresh the access token using the stored refresh token.

    This is called automatically when the access token expires.
    """
    refresh_key = f"zerodha:tokens:{user_id}:refresh"
    encrypted_refresh = _redis.get(refresh_key)

    if encrypted_refresh is None:
        raise TokenExpiredError(
            "Refresh token expired. User must re-authenticate."
        )

    refresh_token = _fernet.decrypt(encrypted_refresh).decode()

    # Never log the actual token
    logger.info(f"Refreshing access token for user {user_id}")

    kite = KiteConnect(api_key=os.environ["ZERODHA_API_KEY"])
    data = kite.generate_session(
        request_token=refresh_token,
        api_secret=os.environ["ZERODHA_SECRET"]
    )

    new_access = data["access_token"]
    new_refresh = data.get("refresh_token", refresh_token)

    store_tokens(new_access, new_refresh, user_id)
    return new_access


class TokenExpiredError(Exception):
    """Raised when both access and refresh tokens have expired."""


def clear_all_tokens(user_id: str) -> None:
    """Securely clear all tokens for a user (e.g., on logout)."""
    key_prefix = f"zerodha:tokens:{user_id}"
    keys = _redis.keys(f"{key_prefix}:*")
    if keys:
        _redis.delete(*keys)
    logger.info(f"Cleared all tokens for user {user_id}")
```

### Security Measures

| Measure | Implementation |
|---|---|
| Encryption at rest | Fernet (AES-128-CBC + HMAC) |
| TTL on access token | 24 hours |
| TTL on refresh token | 7 days |
| Token logging | Only SHA-256 prefix (first 8 chars) |
| Network transport | Redis over TLS (rediss://) in production |
| Key isolation | Separate encryption key per deployment |
| Auto-refresh | Background task refreshes before expiry |

### Required Environment Variables

```bash
# Zerodha configuration
ZERODHA_API_KEY=your_zerodha_api_key
ZERODHA_SECRET=your_zerodha_secret
ZERODHA_ENCRYPTION_KEY=base64_fernet_key  # Generate with Fernet.generate_key()

# Redis configuration (for token storage)
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=your_redis_password  # Required in production
REDIS_SSL=true  # Required in production
```

---

## GitHub Secrets

### Required Repository Secrets

Configure these in **Settings > Secrets and variables > Actions**:

| Secret | Required | Description |
|---|---|---|
| `PYPI_API_TOKEN` | Yes | PyPI API token for automated publishing |
| `DOCKER_USERNAME` | If using Docker | Docker Hub username |
| `DOCKER_PASSWORD` | If using Docker | Docker Hub access token (not password) |
| `VPS_HOST` | If deploying to VPS | Deployment server IP/hostname |
| `VPS_USER` | If deploying to VPS | SSH username for deployment |
| `SSH_PRIVATE_KEY` | If deploying to VPS | SSH private key for deployment |
| `VPS_SSH_PORT` | No | SSH port (default: 22) |

### Optional Secrets

| Secret | Purpose |
|---|---|
| `BINANCE_API_KEY` | For integration tests (paper trading only) |
| `BINANCE_SECRET` | For integration tests (paper trading only) |
| `ALPACA_API_KEY` | For integration tests (paper trading only) |
| `ALPACA_SECRET` | For integration tests (paper trading only) |
| `NEWSAPI_KEY` | For news sentiment feature tests |
| `CODECOV_TOKEN` | For test coverage reporting |

### Environment Secrets (per environment)

For projects using GitHub Environments:

```
Environments:
  test:
    - BINANCE_API_KEY (paper trading)
    - BINANCE_SECRET (paper trading)
  production:
    - DOCKER_USERNAME
    - DOCKER_PASSWORD
    - VPS_HOST
    - VPS_USER
    - SSH_PRIVATE_KEY
```

### Secret Naming Conventions

```bash
# Good
BINANCE_API_KEY
BINANCE_SECRET
ZERODHA_API_KEY
NEWSAPI_KEY

# Bad (too generic, ambiguous)
API_KEY
SECRET
KEY
PASSWORD
TOKEN
```

### Rotating GitHub Secrets

```bash
# 1. Generate new value at the provider
echo "New secret value: $(openssl rand -hex 32)"

# 2. Update in GitHub: Settings > Secrets > Update

# 3. Verify CI still passes
gh workflow run ci.yml --repo alpha-search/alpha-search

# 4. Revoke old value at the provider
```

---

## Environment Variables

### Complete Configuration Reference

See `.env.example` in the repository root for the full template.

### Security-Specific Variables

```bash
# Core security settings
QUANT_OS_ENV=development  # Options: development, staging, production
LOG_LEVEL=INFO            # Options: DEBUG, INFO, WARNING, ERROR
LOG_SENSITIVE=false       # When true, masks all sensitive values in logs

# Cache and storage
CACHE_DIR=~/.alpha_search/cache
CACHE_ENCRYPTION=true     # Encrypt cached market data at rest
CACHE_TTL_DAYS=30         # Auto-expire cached data

# Rate limiting (API protection)
RATE_LIMIT_ENABLED=true
RATE_LIMIT_REQUESTS_PER_MINUTE=60
RATE_LIMIT_BURST=10

# CORS settings (for web API)
CORS_ALLOWED_ORIGINS=http://localhost:3000,https://alpha-search.dev
CORS_ALLOWED_METHODS=GET,POST

# Security headers
SECURITY_HEADERS_ENABLED=true
HSTS_MAX_AGE=31536000
CONTENT_SECURITY_POLICY=default-src 'self'

# Audit logging
AUDIT_LOG_ENABLED=true
AUDIT_LOG_PATH=~/.alpha_search/logs/audit.log
AUDIT_LOG_RETENTION_DAYS=90
```

### Environment-Specific Defaults

```python
# alpha_search/config/security.py
import os

ENV = os.environ.get("QUANT_OS_ENV", "development")

SECURITY_DEFAULTS = {
    "development": {
        "cache_encryption": False,
        "rate_limit_enabled": False,
        "audit_log_enabled": True,
        "cors_allowed_origins": ["*"],
        "require_https": False,
    },
    "staging": {
        "cache_encryption": True,
        "rate_limit_enabled": True,
        "audit_log_enabled": True,
        "cors_allowed_origins": ["https://staging.alpha-search.dev"],
        "require_https": True,
    },
    "production": {
        "cache_encryption": True,
        "rate_limit_enabled": True,
        "audit_log_enabled": True,
        "cors_allowed_origins": ["https://alpha-search.dev"],
        "require_https": True,
    },
}
```

---

## Docker Security

### Dockerfile Best Practices

```dockerfile
# Multi-stage build for security and size
FROM python:3.11-slim AS builder

# Build dependencies
WORKDIR /build
COPY pyproject.toml .
RUN pip install --no-cache-dir build

COPY . .
RUN python -m build

# --- Production stage ---
FROM python:3.11-slim AS production

# Security: Create non-root user
RUN groupadd -r quantos && useradd -r -g quantos -s /bin/false quantos

# Security: Install security updates
RUN apt-get update && \
    apt-get upgrade -y && \
    apt-get install -y --no-install-recommends \
        ca-certificates \
        && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install the built package
COPY --from=builder /build/dist/*.whl .
RUN pip install --no-cache-dir *.whl && rm *.whl

# Security: Read-only filesystem where possible
RUN mkdir -p /tmp/alpha_search && chown quantos:quantos /tmp/alpha_search

# Security: Drop to non-root user
USER quantos

# Security: Expose only necessary port
EXPOSE 8000

# Security: Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import alpha_search; print(alpha_search.__version__)" || exit 1

# Security: No shell access
ENTRYPOINT ["python", "-m", "alpha_search.server"]
```

### docker-compose.yml Security

```yaml
version: "3.8"

services:
  alpha-search:
    build:
      context: .
      dockerfile: Dockerfile
      target: production
    read_only: true  # Read-only root filesystem
    tmpfs:
      - /tmp:noexec,nosuid,size=100m
    security_opt:
      - no-new-privileges:true
    cap_drop:
      - ALL  # Drop all capabilities
    cap_add:
      - NET_BIND_SERVICE  # Only if binding to port < 1024
    user: "999:999"  # quantos user
    environment:
      - QUANT_OS_ENV=production
    env_file:
      - .env
    secrets:
      - zerodha_api_key
      - zerodha_secret
      - redis_password
    networks:
      - alpha-search-net
    restart: unless-stopped

  redis:
    image: redis:7-alpine
    command: redis-server --requirepass ${REDIS_PASSWORD}
    volumes:
      - redis-data:/data
    networks:
      - alpha-search-net
    restart: unless-stopped

  # Monitoring
  prometheus:
    image: prom/prometheus:latest
    volumes:
      - ./monitoring/prometheus.yml:/etc/prometheus/prometheus.yml:ro
    networks:
      - alpha-search-net

volumes:
  redis-data:
    driver: local

networks:
  alpha-search-net:
    driver: bridge
    internal: false

# Docker secrets (use docker secret create in Swarm mode)
secrets:
  zerodha_api_key:
    external: true
  zerodha_secret:
    external: true
  redis_password:
    external: true
```

### Docker Security Checklist

| Check | Command/Config |
|---|---|
| Running as non-root | `USER quantos` in Dockerfile |
| No new privileges | `security_opt: no-new-privileges:true` |
| Dropped capabilities | `cap_drop: ALL` |
| Read-only filesystem | `read_only: true` |
| Resource limits | `deploy.resources.limits` |
| No sensitive env vars | Use Docker secrets |
| No SSH daemon | Base image: `python:slim` |
| Minimal image size | Multi-stage build |
| Security updates | `apt-get upgrade` in build |
| Health check defined | `HEALTHCHECK` instruction |

---

## User Authentication

> **Status:** Planned for Phase 3 (v0.5.0+)
> **Current:** Alpha Search is a research library, not a web service. Authentication applies when running the web dashboard or API server.

### Planned Architecture

```
User Request
    |
    v
+-----------+     +-----------+     +-----------+
|  API      | --> |  JWT      | --> |  Rate     |
|  Gateway  |     |  Auth     |     |  Limiter  |
+-----------+     +-----------+     +-----------+
    |                                      |
    v                                      v
+-----------+                      +-----------+
|  OAuth2   |                      |  Audit    |
|  (GitHub, |                      |  Logger   |
|  Google)  |                      |           |
+-----------+                      +-----------+
```

### JWT Authentication

```python
# alpha_search/auth/jwt_handler.py
"""JWT-based authentication for Alpha Search API."""

import os
import jwt
import hashlib
from datetime import datetime, timedelta
from typing import Optional
from fastapi import HTTPException, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

SECRET_KEY = os.environ["JWT_SECRET_KEY"]
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
REFRESH_TOKEN_EXPIRE_DAYS = 7

security = HTTPBearer()


def create_access_token(data: dict) -> str:
    """Create a JWT access token."""
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire, "type": "access"})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def create_refresh_token(data: dict) -> str:
    """Create a JWT refresh token with longer expiry."""
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "type": "refresh"})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def verify_token(credentials: HTTPAuthorizationCredentials = Security(security)) -> dict:
    """Verify JWT token from Authorization header."""
    token = credentials.credentials
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("type") != "access":
            raise HTTPException(status_code=401, detail="Invalid token type")
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


def hash_token_for_log(token: str) -> str:
    """Create a safe hash of a token for logging purposes."""
    return hashlib.sha256(token.encode()).hexdigest()[:12]
```

### OAuth 2.0 Integration

```python
# alpha_search/auth/oauth.py
"""OAuth 2.0 integration with GitHub and Google."""

from fastapi import HTTPException
from authlib.integrations.starlette_client import OAuth

oauth = OAuth()

# GitHub OAuth
oauth.register(
    name="github",
    client_id=os.environ["GITHUB_OAUTH_CLIENT_ID"],
    client_secret=os.environ["GITHUB_OAUTH_CLIENT_SECRET"],
    authorize_url="https://github.com/login/oauth/authorize",
    access_token_url="https://github.com/login/oauth/access_token",
    api_base_url="https://api.github.com/",
    client_kwargs={"scope": "read:user"},
)

# Google OAuth
oauth.register(
    name="google",
    client_id=os.environ["GOOGLE_OAUTH_CLIENT_ID"],
    client_secret=os.environ["GOOGLE_OAUTH_CLIENT_SECRET"],
    authorize_url="https://accounts.google.com/o/oauth2/auth",
    access_token_url="https://accounts.google.com/o/oauth2/token",
    api_base_url="https://www.googleapis.com/oauth2/v1/",
    client_kwargs={"scope": "openid email profile"},
)
```

### Rate Limiting

```python
# alpha_search/auth/rate_limit.py
"""Rate limiting for API endpoints."""

import redis
from fastapi import HTTPException, Request
from functools import wraps
import time

redis_client = redis.Redis(host=os.environ.get("REDIS_HOST", "localhost"))

RATE_LIMITS = {
    "default": {"requests": 60, "window": 60},      # 60/minute
    "auth": {"requests": 5, "window": 60},           # 5 login attempts/minute
    "backtest": {"requests": 10, "window": 60},      # 10 backtests/minute
    "data": {"requests": 100, "window": 60},         # 100 data requests/minute
}


def rate_limit(tier: str = "default"):
    """Decorator to apply rate limiting to an endpoint."""
    def decorator(func):
        @wraps(func)
        async def wrapper(request: Request, *args, **kwargs):
            client_ip = request.client.host
            limit = RATE_LIMITS.get(tier, RATE_LIMITS["default"])
            key = f"ratelimit:{tier}:{client_ip}"

            current = redis_client.get(key)
            if current and int(current) >= limit["requests"]:
                raise HTTPException(
                    status_code=429,
                    detail=f"Rate limit exceeded. Try again in {limit['window']} seconds."
                )

            pipe = redis_client.pipeline()
            pipe.incr(key)
            pipe.expire(key, limit["window"])
            pipe.execute()

            return await func(request, *args, **kwargs)
        return wrapper
    return decorator
```

### Audit Logging

```python
# alpha_search/auth/audit.py
"""Audit logging for security-sensitive operations."""

import json
import logging
from datetime import datetime
from pathlib import Path

AUDIT_LOG_PATH = Path(os.environ.get("AUDIT_LOG_PATH", "~/.alpha_search/logs/audit.log")).expanduser()
AUDIT_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

audit_logger = logging.getLogger("alpha_search.audit")
audit_logger.setLevel(logging.INFO)

handler = logging.FileHandler(AUDIT_LOG_PATH)
handler.setFormatter(logging.Formatter("%(asctime)s | %(message)s"))
audit_logger.addHandler(handler)


def log_auth_event(user_id: str, event: str, success: bool, details: dict = None):
    """Log an authentication event."""
    entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "user_id": user_id,
        "event": event,
        "success": success,
        "ip_address": details.get("ip_address") if details else None,
        "user_agent": details.get("user_agent") if details else None,
    }
    audit_logger.info(json.dumps(entry))


def log_data_access(user_id: str, data_source: str, symbol: str, action: str):
    """Log data access for compliance."""
    entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "user_id": user_id,
        "event": "data_access",
        "data_source": data_source,
        "symbol": symbol,
        "action": action,
    }
    audit_logger.info(json.dumps(entry))
```

---

## Incident Response

### Security Incident Severity Levels

| Level | Description | Response Time |
|---|---|---|
| **Critical** | Data breach, active exploitation, token leak | 1 hour |
| **High** | Vulnerability with exploit path | 24 hours |
| **Medium** | Security hardening issue | 7 days |
| **Low** | Documentation improvement | 30 days |

### Incident Response Playbook

#### Step 1: Detect
- Automated: GitHub secret scanning, Dependabot alerts
- Manual: Community reports to security@alpha-search.dev

#### Step 2: Assess
```bash
# Incident assessment checklist
# Save to: /tmp/security/incident-$(date +%Y%m%d).md

## Incident ID: INC-YYYY-MM-DD-NNN
## Severity: [Critical/High/Medium/Low]
## Reporter: [email/GitHub handle]

### Description:
[Describe the issue]

### Affected Components:
- [ ] API
- [ ] Authentication
- [ ] Data layer
- [ ] Third-party integration

### Impact:
- Users affected: [number/unknown]
- Data at risk: [description]
- Exploitability: [trivial/complex/theoretical]

### Timeline:
- Detected: [timestamp]
- Confirmed: [timestamp]
- Patched: [timestamp]
- Disclosed: [timestamp]
```

#### Step 3: Contain
- Critical: Immediately revoke affected tokens/keys
- High: Disable affected feature behind flag
- Medium/Low: Schedule fix for next release

#### Step 4: Fix
- Create fix in private fork for Critical/High
- Code review by at least one other maintainer
- Test thoroughly

#### Step 5: Disclose
- Publish GitHub Security Advisory
- Notify affected users via email (if applicable)
- Post on social media if widely known
- Credit the reporter

#### Step 6: Retrospective
- Update this document with lessons learned
- Add regression tests
- Review similar code for same vulnerability class

### Contact

| Channel | Address |
|---|---|
| Security email | security@alpha-search.dev |
| Encrypted email | PGP key available at https://alpha-search.dev/security/pgp-key |
| GitHub Advisory | https://github.com/alpha-search/alpha-search/security/advisories |
| Response time | 48 hours for acknowledgment, 7 days for initial assessment |

---

## Security Checklist

### For Contributors

Before submitting a PR:

- [ ] No API keys, passwords, or secrets in code
- [ ] `.env.example` updated if new env vars added
- [ ] Pre-commit hooks pass (`pre-commit run --all-files`)
- [ ] No `print()` statements with sensitive data
- [ ] Input validation for all user-provided data
- [ ] Dependencies pinned with hashes (`pip-compile --generate-hashes`)

### For Maintainers

Weekly:
- [ ] Review Dependabot alerts
- [ ] Check security@alpha-search.dev inbox
- [ ] Review access logs for anomalies

Monthly:
- [ ] Rotate CI/CD secrets
- [ ] Review GitHub access permissions
- [ ] Audit third-party dependencies (`pip-audit`)

Quarterly:
- [ ] Full security review of authentication code
- [ ] Penetration test of API endpoints
- [ ] Review and update this document

### Tools

```bash
# Install security tools
pip install bandit pip-audit safety

# Run security scans
bandit -r alpha_search/                    # Static analysis for security issues
pip-audit                              # Check dependencies for known vulnerabilities
safety check                           # Alternative vulnerability scanner

# Git history scan for secrets
git-secrets --scan-history
trufflehog git file://. --only-verified

# Container security scan
trivy image alpha-search:latest
docker scout cves alpha-search:latest
```

---

## References

- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [CWE Top 25](https://cwe.mitre.org/top25/)
- [Python Security Best Practices](https://python-security.readthedocs.io/)
- [Docker Security Best Practices](https://docs.docker.com/develop/security-best-practices/)
- [GitHub Security Features](https://docs.github.com/en/code-security)

---

*This document is version-controlled. For security concerns, contact security@alpha-search.dev*
