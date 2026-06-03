---
name: fintech-platform-scaffold
description: >-
  Scaffold a production-grade financial research / investing platform (a
  "Seeking Alpha / fintech terminal" style app) with a FastAPI backend,
  Next.js 14 + TypeScript frontend, PostgreSQL + TimescaleDB, Redis caching,
  Stripe subscription paywall, JWT auth, and a background price-alert worker.
  USE WHEN the user asks to build, scaffold, or extend a stock-research,
  ticker-dashboard, investing, market-data, contributor-CMS, or
  subscription-paywalled finance web app. Reference implementation lives at
  alphapulse/ in this repo.
---

# Fintech Platform Scaffold

Build a modular, production-ready stock-research platform. A complete reference
implementation already exists at `alphapulse/` — **read it first** and reuse its
patterns rather than reinventing them.

## When to use
- "Build me a Seeking Alpha / stock research / investing platform"
- "Add a ticker dashboard / financial statements / charts"
- "Add a subscription paywall / Stripe tiers to my finance app"
- "Add watchlists / price alerts / a contributor CMS"

## Architecture decisions (defaults — keep unless the user overrides)
- **Backend: FastAPI (Python)** — chosen over Node for data-processing ergonomics
  (pandas/numpy interop, async SQLAlchemy, Pydantic typing).
- **DB: PostgreSQL** for relational core + **TimescaleDB** hypertable for
  high-ingestion OHLCV/price time-series. Never put tick data in a plain table.
- **Redis** for: read-through caching of external market-data fetches, paywall
  entitlement cache, and alert-worker cooldown locks.
- **Frontend: Next.js 14 App Router**, strict TypeScript, Tailwind, shadcn-style
  primitives, TradingView **Lightweight Charts** for candlesticks.
- **Auth: JWT** access + refresh tokens; bcrypt passwords.
- **Payments: Stripe** Checkout + webhooks, with an **offline mock mode**
  (keys ending in `_mock`) so the app runs with zero external credentials.

## Build order (follow this sequence)
1. **Schema first** — define entities (Users, Subscriptions, Tickers, Articles,
   ArticleTickers, Watchlists, WatchlistItems, PriceAlerts). Provide BOTH a
   Prisma schema (canonical reference) and the SQLAlchemy ORM, plus a separate
   `sql/timescale.sql` for the hypertable + compression + continuous aggregate +
   retention policies.
2. **Backend core** — `core/config.py` (typed settings), `core/security.py`
   (JWT), `core/cache.py` (stampede-protected `@redis_cache` decorator),
   `services/market_data.py` (cached, mock-or-live, FMP/Polygon-shaped).
3. **Paywall** — a `PaywallMiddleware` that 402-blocks premium namespaces by
   JWT-derived tier (Redis-cached), PLUS a graceful per-resource gate that
   returns a free preview with `is_locked: true` for mixed free/premium content.
   Never ship premium bodies to a locked client.
4. **Routes** — auth, tickers (public), metrics (premium), articles (CMS),
   watchlists + alerts, subscriptions (checkout + webhook).
5. **Worker** — a standalone polling loop that evaluates active alerts against
   cached quotes and dispatches notifications, de-duplicated via a Redis
   `SET NX` cooldown so multiple replicas are safe.
6. **Frontend** — typed API client with a `PaywallError` (402) branch; the
   `app/ticker/[symbol]/page.tsx` dashboard (server-rendered shell + client
   chart/tabs); article reader; pricing/checkout; auth pages.

## Non-negotiable quality bar
- Strict typing end to end (Pydantic v2 backend, `"strict": true` tsconfig).
- No `// TODO` / `...` placeholders in core logic — write complete files.
- Every external data fetch goes through the Redis cache wrapper.
- Every mutating/private endpoint is auth-guarded; role guards for the CMS.
- Tier hierarchy: `free < premium < pro`; a higher tier satisfies a lower
  requirement; a non-active subscription downgrades to `free`.

## Reference files to copy/adapt from `alphapulse/`
- Cache wrapper:        `backend/app/core/cache.py`
- JWT:                  `backend/app/core/security.py`
- Paywall:             `backend/app/middleware/paywall.py`
- Entitlements:        `backend/app/api/deps.py`
- Mock market data:     `backend/app/services/market_data.py`
- TimescaleDB schema:   `backend/sql/timescale.sql`
- Alert worker:        `workers/alerts_worker.py`
- Ticker dashboard:     `frontend/app/ticker/[symbol]/page.tsx`
- Typed API client:     `frontend/lib/api.ts`
- Chart canvas:        `frontend/components/ticker/price-chart.tsx`

## Verify before finishing
- Backend: `python -m py_compile` all modules; `pytest` the auth + entitlement
  tests.
- Frontend: `npm run typecheck`.
- `docker compose up --build` boots DB + Redis + API (auto-seed) + worker +
  frontend; `GET /health` returns ok; `/ticker/AAPL` renders; Financials tabs
  return 402 for a free user.
