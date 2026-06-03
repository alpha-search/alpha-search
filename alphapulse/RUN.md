# Running AlphaPulse

Three ways to run it, from least to most setup. Pick **one**.

> When copying commands, paste **only the command lines** — your shell will try
> to execute `#` comment lines (zsh doesn't treat `#` as a comment by default).

---

## Option A — No Docker, using conda (recommended if `docker` isn't installed)

You already have `conda`. This needs **no Homebrew, no Docker, no GUI, no sudo**.
It runs Postgres + Redis + the API + worker + frontend entirely from a conda env,
with all data kept inside `alphapulse/.localdb/`.

```bash
conda create -y -n alphapulse -c conda-forge python=3.12 nodejs=22 postgresql redis
conda activate alphapulse
cd alphapulse
./scripts/run_local.sh
```

First run takes a few minutes (it installs Python + Node deps). When it finishes
you'll see the URLs printed. Then open **http://localhost:3000**.

Stop everything:
```bash
./scripts/stop_local.sh
```
Wipe the local database and start fresh:
```bash
./scripts/stop_local.sh --clean
```

> Note: plain PostgreSQL has no TimescaleDB extension, so the hypertable setup is
> skipped automatically — the app runs fine on the relational tables. To get the
> TimescaleDB features, use Option C (Docker), which ships the Timescale image.

---

## Option B — No Docker, manual (if you already have Postgres/Redis/Node/Python)

```bash
cd alphapulse/backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export DATABASE_URL="postgresql+asyncpg://USER:PASS@localhost:5432/alphapulse"
export REDIS_URL="redis://localhost:6379/0"
export USE_MOCK_MARKET_DATA=true JWT_SECRET=dev-secret STRIPE_SECRET_KEY=sk_test_mock
python -m scripts.init_db && python -m scripts.seed
uvicorn app.main:app --reload &           # API on :8000
PYTHONPATH="$PWD:$PWD/.." python -m workers.alerts_worker &   # alerts worker
cd ../frontend && npm install
BACKEND_URL=http://localhost:8000 npm run dev   # frontend on :3000
```

---

## Option C — Docker (gets the full TimescaleDB stack)

Needs a Docker engine. If you don't have Docker Desktop, the lightest CLI-only
option on macOS is **Colima** (no GUI, no license):

```bash
brew install colima docker docker-compose
colima start
```

Then, from the repo:
```bash
cd alphapulse
cp .env.example .env
docker compose up --build
```

Open **http://localhost:3000**. The compose stack auto-creates tables and seeds
demo data.

---

## What you should see

- **http://localhost:3000** — home page with featured tickers and latest research.
- **http://localhost:3000/ticker/AAPL** — ticker dashboard: live quote, candlestick
  chart, summary cards, and the **Financials** tabs.
- The Financials tabs return **402** for free users and show an upgrade gate.
- **http://localhost:8000/docs** — interactive API documentation.

### Demo accounts (created by the seed script)
| Email | Password | Tier |
| --- | --- | --- |
| `contributor@alphapulse.io` | `password123` | PRO (sees everything) |
| `reader@alphapulse.io` | `password123` | FREE (paywalled) |

Sign in as the reader to see the paywall; sign in as the contributor to unlock
premium financials and the full body of premium articles.

---

## Troubleshooting

- **`command not found: docker` / `brew`** → use **Option A** (conda). It needs
  none of those.
- **`port already in use`** → override ports, e.g.
  `ALPHAPULSE_WEB_PORT=3001 ALPHAPULSE_API_PORT=8001 ./scripts/run_local.sh`.
- **Frontend loads but data is empty** → the backend isn't up yet; check
  `alphapulse/.localdb/logs/api.log`.
- **Stuck at a `quote>` or `dquote>` prompt** → press `Ctrl+C`; you pasted a
  comment line. Re-paste only the command lines.
