# AlphaPulse

A production-grade **Seeking Alpha-style** stock research platform: interactive
ticker dashboards, a contributor CMS for analyst research, a Stripe-backed
subscription paywall, and a live watchlist + price-alert engine.

> Built as a modular monorepo: **FastAPI** backend (optimised for high-throughput
> data ingestion), **Next.js 14 App Router** frontend, and a standalone
> **background worker** for alert evaluation and mock notifications.

---

## Architecture

| Layer        | Technology                                                            |
| ------------ | --------------------------------------------------------------------- |
| Frontend     | Next.js 14 (App Router), TypeScript (strict), Tailwind, shadcn-style UI |
| Charts       | TradingView **Lightweight Charts** (candlestick + volume)             |
| Backend      | Python · **FastAPI** · SQLAlchemy 2 (async) · Pydantic v2             |
| Database     | **PostgreSQL** (core) + **TimescaleDB** hypertable (price metrics)    |
| Cache/Queue  | **Redis** — read-through API cache + alert cooldown locks + notifications |
| Payments     | **Stripe** Checkout + webhooks (with a fully offline mock mode)       |
| Auth         | **JWT** access/refresh tokens, bcrypt password hashing               |

```
alphapulse/
├── docker-compose.yml          # TimescaleDB + Redis + API + worker + frontend
├── .env.example
├── backend/                    # FastAPI service
│   ├── app/
│   │   ├── main.py             # app factory, router + middleware wiring
│   │   ├── core/
│   │   │   ├── config.py       # typed settings (pydantic-settings)
│   │   │   ├── security.py     # JWT issue/verify + bcrypt
│   │   │   ├── redis_client.py # shared async pool
│   │   │   └── cache.py        # read-through cache + @redis_cache decorator
│   │   ├── db/
│   │   │   ├── models.py       # SQLAlchemy ORM (Users, Articles, Tickers…)
│   │   │   └── session.py      # async engine + per-request session
│   │   ├── schemas/            # Pydantic request/response models
│   │   ├── services/
│   │   │   ├── market_data.py  # cached FMP/Polygon-shaped data (mock or live)
│   │   │   └── stripe_service.py
│   │   ├── middleware/
│   │   │   └── paywall.py      # 402 namespace guard + per-article gating
│   │   └── api/
│   │       ├── deps.py         # current-user, role guards, entitlements
│   │       └── routes/         # auth, tickers, metrics, articles, watchlists, subscriptions
│   ├── prisma/schema.prisma    # canonical relational schema (Prisma)
│   ├── sql/timescale.sql       # hypertable, compression, continuous aggregate
│   ├── scripts/                # init_db.py, seed.py
│   └── tests/                  # JWT + entitlement unit tests
├── workers/
│   ├── alerts_worker.py        # polls active price alerts, fires notifications
│   └── notifications.py        # mock dispatcher (Redis pub/sub + inbox)
└── frontend/                   # Next.js 14
    ├── app/
    │   ├── page.tsx            # home / latest research
    │   ├── ticker/[symbol]/page.tsx   # ⭐ the ticker dashboard
    │   ├── article/[slug]/page.tsx    # markdown reader + paywall lock
    │   ├── pricing/page.tsx           # Stripe checkout
    │   ├── checkout/success/page.tsx
    │   └── login/page.tsx
    ├── components/
    │   ├── ticker/             # price-chart, summary-cards, financial-tabs, paywall-overlay
    │   └── ui/                 # card, button, tabs (shadcn-style)
    └── lib/                    # api.ts (typed client), types.ts, utils.ts
```

---

## Feature → Code map

| Feature | Where |
| --- | --- |
| **Ticker profile + charts + financial tabs** | `frontend/app/ticker/[symbol]/page.tsx`, `components/ticker/*`, `backend/app/api/routes/tickers.py` + `metrics.py` |
| **Contributor CMS** (markdown, `$TICKER` tags, disclosures) | `backend/app/api/routes/articles.py`, `frontend/app/article/[slug]/page.tsx` |
| **Subscription paywall** | `backend/app/middleware/paywall.py`, `services/stripe_service.py`, `api/routes/subscriptions.py`, `frontend/app/pricing` |
| **Watchlist & price alerts** | `backend/app/api/routes/watchlists.py`, `workers/alerts_worker.py`, `workers/notifications.py` |
| **Redis caching of external data** | `backend/app/core/cache.py` + `services/market_data.py` |
| **JWT auth** | `backend/app/core/security.py`, `api/deps.py`, `api/routes/auth.py` |

---

## Quick start

**No Docker installed?** See **[RUN.md](./RUN.md)** for a one-command,
conda-based local runner (`./scripts/run_local.sh`) that needs no Docker, no
Homebrew, and no GUI.

### With Docker

```bash
cd alphapulse
cp .env.example .env
docker compose up --build
```

This boots TimescaleDB, Redis, the API (auto-creates tables + seeds demo data),
the alerts worker, and the frontend.

- Frontend → http://localhost:3000
- API docs → http://localhost:8000/docs
- Demo login → `contributor@alphapulse.io` / `password123` (PRO tier)
  or `reader@alphapulse.io` / `password123` (FREE tier)

Try `http://localhost:3000/ticker/AAPL` — the chart and quote are public, while
the **Financials** tabs return `402` for free users and render the upgrade gate.

## Local development (without Docker)

**Backend**
```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export DATABASE_URL=postgresql+asyncpg://alphapulse:alphapulse@localhost:5432/alphapulse
python -m scripts.init_db && python -m scripts.seed
uvicorn app.main:app --reload
# in another shell — the alert worker:
python -m workers.alerts_worker
```

**Frontend**
```bash
cd frontend
npm install
npm run dev
```

**Tests**
```bash
cd backend && pytest          # JWT + entitlement logic
npm --prefix frontend run typecheck
```

---

## How the paywall works

1. **Whole-namespace gate** — `PaywallMiddleware` blocks `/api/v1/metrics/**`
   for any caller whose effective tier is `free`, returning `402` with
   `{"code": "subscription_required"}`. The tier is resolved from the JWT and
   cached in Redis (30s TTL) so cancellations propagate quickly without a DB
   hit per request.
2. **Graceful per-article gate** — article bodies degrade instead of hard-failing:
   the backend returns a free preview with `is_locked: true`, and the reader UI
   shows an inline upgrade CTA. The premium body is **never** sent to a locked
   client.

## Data caching strategy

Every external market-data fetch flows through `@redis_cache`, a stampede-protected
read-through cache. On a miss, a short Redis lock ensures only one coroutine hits
the upstream provider (critical under FMP/Polygon rate limits) while others wait
for the result. TTLs are tuned per data class (15s quotes → 12h financials).

For high-volume time-series ingestion, raw OHLCV ticks land in the TimescaleDB
`ticker_metrics` hypertable (weekly chunks, sharded by symbol), with native
compression after 14 days, a 1-day continuous aggregate for charts, and a 90-day
retention policy on raw ticks.
