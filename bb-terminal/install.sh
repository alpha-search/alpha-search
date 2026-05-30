#!/usr/bin/env bash
# BBterminal — one-line installer
#
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/vaughanf1/BB-Terminal/main/install.sh | bash
#
# Environment overrides:
#   INSTALL_DIR=~/somewhere    # where to clone (default: ~/BB-Terminal)
#   SKIP_LAUNCH=1              # don't auto-launch after install

set -euo pipefail

REPO_URL="https://github.com/vaughanf1/BB-Terminal.git"
INSTALL_DIR="${INSTALL_DIR:-$HOME/BB-Terminal}"
SKIP_LAUNCH="${SKIP_LAUNCH:-}"

AMBER='\033[33m'; GREEN='\033[32m'; RED='\033[31m'; DIM='\033[2m'; BOLD='\033[1m'; RST='\033[0m'
step() { printf "${AMBER}▸ %s${RST}\n" "$*"; }
ok()   { printf "${GREEN}✓ %s${RST}\n" "$*"; }
fail() { printf "${RED}✗ %s${RST}\n" "$*" >&2; exit 1; }

cat <<'BANNER'

  ██████  ██████      ████████ ███████ ██████  ███    ███ ██ ███    ██  █████  ██
  ██   ██ ██   ██        ██    ██      ██   ██ ████  ████ ██ ████   ██ ██   ██ ██
  ██████  ██████         ██    █████   ██████  ██ ████ ██ ██ ██ ██  ██ ███████ ██
  ██   ██ ██   ██        ██    ██      ██   ██ ██  ██  ██ ██ ██  ██ ██ ██   ██ ██
  ██████  ██████         ██    ███████ ██   ██ ██      ██ ██ ██   ████ ██   ██ ███████

  Bloomberg-style intelligence dashboard — powered by OpenBB
  https://github.com/vaughanf1/BB-Terminal

BANNER

# ── prerequisites ────────────────────────────────────────────
step "Checking prerequisites"

command -v git >/dev/null 2>&1 || fail "git is required. Install with: xcode-select --install (macOS) or apt install git"
ok "git     $(git --version | awk '{print $3}')"

PY=""
for cand in python3.12 python3.11 python3.10; do
  if command -v "$cand" >/dev/null 2>&1; then PY="$cand"; break; fi
done
if [ -z "$PY" ]; then
  cat <<EOF >&2

${RED}Python 3.10, 3.11, or 3.12 is required.${RST}

  macOS:     brew install python@3.12
  Ubuntu:    sudo apt install python3.12 python3.12-venv
  Windows:   download the 3.12 installer from https://python.org

EOF
  exit 1
fi
ok "Python  $($PY --version | awk '{print $2}')"

if ! command -v node >/dev/null 2>&1; then
  cat <<EOF >&2

${RED}Node.js 18+ is required.${RST}

  macOS:     brew install node
  Ubuntu:    curl -fsSL https://deb.nodesource.com/setup_20.x | sudo bash -
             sudo apt install nodejs
  Windows:   download the LTS installer from https://nodejs.org

EOF
  exit 1
fi
ok "Node    $(node --version)"

# ── clone ────────────────────────────────────────────────────
step "Cloning BB-Terminal to $INSTALL_DIR"

if [ -e "$INSTALL_DIR" ]; then
  cat <<EOF >&2

${RED}$INSTALL_DIR already exists.${RST}

To reinstall, remove it first:
  rm -rf "$INSTALL_DIR"

Or install somewhere else:
  INSTALL_DIR=~/my-path curl -fsSL https://raw.githubusercontent.com/vaughanf1/BB-Terminal/main/install.sh | bash

EOF
  exit 1
fi

git clone --depth 1 "$REPO_URL" "$INSTALL_DIR"
ok "Cloned"

# ── run project-local setup ──────────────────────────────────
cd "$INSTALL_DIR"
./setup.sh

# ── auto-launch ──────────────────────────────────────────────
if [ -z "$SKIP_LAUNCH" ]; then
  step "Launching BBterminal"
  ./start.sh
else
  cat <<EOF

${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RST}
${BOLD}${AMBER}  BBterminal installed.${RST}

  Launch it now:
    ${AMBER}cd $INSTALL_DIR && ./start.sh${RST}

${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RST}

EOF
fi
