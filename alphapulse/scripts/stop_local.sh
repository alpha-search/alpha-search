#!/usr/bin/env bash
#
# Stop everything started by run_local.sh. Pass --clean to also delete the local
# database, logs, and node/python caches under .localdb.
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STATE="$ROOT/.localdb"
PGDATA="$STATE/pgdata"
PIDS="$STATE/pids"
REDIS_PORT="${ALPHAPULSE_REDIS_PORT:-56379}"

note() { printf '\033[1;33m▶ %s\033[0m\n' "$*"; }

# Kill API / worker / web processes recorded by run_local.sh.
if [ -f "$PIDS" ]; then
  while read -r name pid; do
    if [ -n "${pid:-}" ] && kill -0 "$pid" 2>/dev/null; then
      note "Stopping $name (pid $pid)…"
      kill "$pid" 2>/dev/null || true
    fi
  done < "$PIDS"
  rm -f "$PIDS"
fi

# Redis.
if command -v redis-cli >/dev/null 2>&1; then
  redis-cli -p "$REDIS_PORT" shutdown nosave >/dev/null 2>&1 || true
fi

# PostgreSQL.
if command -v pg_ctl >/dev/null 2>&1 && [ -d "$PGDATA" ]; then
  note "Stopping PostgreSQL…"
  pg_ctl -D "$PGDATA" -m fast stop >/dev/null 2>&1 || true
fi

if [ "${1:-}" = "--clean" ]; then
  note "Removing local state ($STATE)…"
  rm -rf "$STATE"
fi

note "Done."
