#!/usr/bin/env bash
# BBterminal — one-time setup
# Installs OpenBB Platform (Python) and the UI (Node). Run once.

set -euo pipefail
cd "$(dirname "$0")"

ROOT="$(pwd)"
AMBER="\033[33m"; GREEN="\033[32m"; RED="\033[31m"; DIM="\033[2m"; RST="\033[0m"

step() { printf "${AMBER}▸ %s${RST}\n" "$*"; }
ok()   { printf "${GREEN}✓ %s${RST}\n" "$*"; }
fail() { printf "${RED}✗ %s${RST}\n" "$*" >&2; exit 1; }

step "Checking prerequisites"

# Python 3.10-3.12 — prefer 3.12
PY=""
for cand in python3.12 python3.11 python3.10; do
  if command -v "$cand" >/dev/null 2>&1; then PY="$cand"; break; fi
done
[ -n "$PY" ] || fail "Python 3.10, 3.11, or 3.12 is required (install with: brew install python@3.12)"
ok "Python: $($PY --version)"

command -v node >/dev/null 2>&1 || fail "Node.js 18+ is required (install with: brew install node)"
ok "Node:   $(node --version)"

command -v npm >/dev/null 2>&1 || fail "npm is required"
ok "npm:    $(npm --version)"

# -------- Python venv + OpenBB --------
step "Creating Python virtual environment (.venv)"
if [ ! -d .venv ]; then
  "$PY" -m venv .venv
  ok "Created .venv with $PY"
else
  ok ".venv already exists"
fi

step "Upgrading pip"
.venv/bin/pip install --upgrade --quiet pip wheel

step "Installing OpenBB Platform (this takes ~3 minutes)"
.venv/bin/pip install --quiet "openbb[all]" openbb-cli
ok "OpenBB + all provider extensions installed"

# -------- UI dependencies --------
step "Installing UI dependencies"
( cd "$ROOT/app" && npm install --silent )
ok "Node modules installed"

cat <<EOF

${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RST}
${AMBER}  BBterminal is ready.${RST}
${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RST}

  Launch:    ${AMBER}./start.sh${RST}
  Stop:      ${AMBER}./stop.sh${RST}
  Docs:      see README.md

${DIM}First launch builds the OpenBB extension cache and takes ~10s longer.${RST}
EOF
