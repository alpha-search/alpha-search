#!/usr/bin/env bash
#
# AlphaPulse — no-Docker local runner.
#
# Boots the whole stack (PostgreSQL + Redis + FastAPI API + alerts worker +
# Next.js) using binaries already on your PATH. The easiest way to get those
# binaries without Homebrew or Docker is a conda env:
#
#   conda create -y -n alphapulse -c conda-forge python=3.12 nodejs=22 postgresql redis
#   conda activate alphapulse
#   cd alphapulse && ./scripts/run_local.sh
#
# Everything (DB data, logs, PIDs) is written under alphapulse/.localdb so it is
# fully self-contained and removed by ./scripts/stop_local.sh --clean.
#
# Stop everything with:  ./scripts/stop_local.sh
set -euo pipefail

# --- Paths -----------------------------------------------------------------
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STATE="$ROOT/.localdb"
PGDATA="$STATE/pgdata"
PGSOCK="$STATE/sock"
LOGS="$STATE/logs"
PIDS="$STATE/pids"
mkdir -p "$STATE" "$PGSOCK" "$LOGS"
: > "$PIDS"

# --- Config (override by exporting before running) -------------------------
PGPORT="${ALPHAPULSE_PG_PORT:-55432}"
REDIS_PORT="${ALPHAPULSE_REDIS_PORT:-56379}"
API_PORT="${ALPHAPULSE_API_PORT:-8000}"
WEB_PORT="${ALPHAPULSE_WEB_PORT:-3000}"

export DATABASE_URL="postgresql+asyncpg://alphapulse:alphapulse@127.0.0.1:${PGPORT}/alphapulse"
export REDIS_URL="redis://127.0.0.1:${REDIS_PORT}/0"
export JWT_SECRET="${JWT_SECRET:-local-dev-secret-not-for-production}"
export USE_MOCK_MARKET_DATA="true"
export STRIPE_SECRET_KEY="sk_test_mock"
export STRIPE_WEBHOOK_SECRET="whsec_mock"
export CORS_ORIGINS="http://localhost:${WEB_PORT}"
export ENVIRONMENT="development"

note() { printf '\033[1;32m▶ %s\033[0m\n' "$*"; }
die()  { printf '\033[1;31m✗ %s\033[0m\n' "$*" >&2; exit 1; }

for bin in initdb pg_ctl psql redis-server python3 node npm; do
  command -v "$bin" >/dev/null 2>&1 || die "'$bin' not found on PATH. Create the conda env shown at the top of this script, then 'conda activate alphapulse'."
done

# --- PostgreSQL ------------------------------------------------------------
if [ ! -f "$PGDATA/PG_VERSION" ]; then
  note "Initialising PostgreSQL cluster…"
  initdb -D "$PGDATA" -U postgres --auth=trust >"$LOGS/initdb.log" 2>&1
fi
note "Starting PostgreSQL on port ${PGPORT}…"
pg_ctl -D "$PGDATA" -l "$LOGS/postgres.log" -w \
  -o "-p ${PGPORT} -k ${PGSOCK} -c listen_addresses=127.0.0.1" start

psql -h 127.0.0.1 -p "$PGPORT" -U postgres -tAc \
  "SELECT 1 FROM pg_roles WHERE rolname='alphapulse'" | grep -q 1 || \
  psql -h 127.0.0.1 -p "$PGPORT" -U postgres -c \
    "CREATE ROLE alphapulse LOGIN PASSWORD 'alphapulse' SUPERUSER" >/dev/null
psql -h 127.0.0.1 -p "$PGPORT" -U postgres -tAc \
  "SELECT 1 FROM pg_database WHERE datname='alphapulse'" | grep -q 1 || \
  psql -h 127.0.0.1 -p "$PGPORT" -U postgres -c \
    "CREATE DATABASE alphapulse OWNER alphapulse" >/dev/null

# --- Redis -----------------------------------------------------------------
note "Starting Redis on port ${REDIS_PORT}…"
redis-server --port "$REDIS_PORT" --daemonize yes \
  --dir "$STATE" --pidfile "$STATE/redis.pid" --logfile "$LOGS/redis.log"

# --- Backend (venv + migrate + seed) --------------------------------------
note "Installing backend dependencies (first run only)…"
cd "$ROOT/backend"
[ -d .venv ] || python3 -m venv .venv
./.venv/bin/pip install -q -U pip >/dev/null
./.venv/bin/pip install -q -r requirements.txt
VENV_PY="$ROOT/backend/.venv/bin/python"

note "Creating tables + seeding demo data…"
"$VENV_PY" -m scripts.init_db
"$VENV_PY" -m scripts.seed

note "Starting FastAPI on :${API_PORT}…"
"$VENV_PY" -m uvicorn app.main:app --host 0.0.0.0 --port "$API_PORT" \
  >"$LOGS/api.log" 2>&1 &
echo "api $!" >> "$PIDS"

note "Starting alerts worker…"
( cd "$ROOT" && PYTHONPATH="$ROOT/backend:$ROOT" "$VENV_PY" -m workers.alerts_worker \
  >"$LOGS/worker.log" 2>&1 ) &
echo "worker $!" >> "$PIDS"

# --- Frontend --------------------------------------------------------------
note "Installing frontend dependencies (first run only)…"
cd "$ROOT/frontend"
[ -d node_modules ] || npm install --no-audit --no-fund
export NEXT_PUBLIC_API_BASE="/api/backend"
export BACKEND_URL="http://localhost:${API_PORT}"
note "Starting Next.js on :${WEB_PORT}…"
npm run dev -- --port "$WEB_PORT" >"$LOGS/web.log" 2>&1 &
echo "web $!" >> "$PIDS"

# --- Wait for the API to answer -------------------------------------------
note "Waiting for services to come up…"
for _ in $(seq 1 30); do
  if curl -fsS "http://localhost:${API_PORT}/health" >/dev/null 2>&1; then break; fi
  sleep 1
done

cat <<EOF

  ✅  AlphaPulse is running.

      Frontend   →  http://localhost:${WEB_PORT}
      API docs   →  http://localhost:${API_PORT}/docs
      Try        →  http://localhost:${WEB_PORT}/ticker/AAPL

      Demo login →  contributor@alphapulse.io / password123  (PRO tier)
                    reader@alphapulse.io      / password123  (FREE tier)

      Logs       →  $LOGS/
      Stop all   →  ./scripts/stop_local.sh

EOF
