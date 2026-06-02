# AlphaSearch Terminal — Build Status

> Single-file Obsidian Slate terminal at `scripts/index.html`, served by the
> FastAPI backend `scripts/app_server.py` at `GET /`. Verified against a live
> server (all 10 routes return `200`).

## Design System — Obsidian Slate

| Token | Value |
|---|---|
| canvas | `#08080A` |
| surfaces | `#121216` / `#17171C` / `#1C1C22` |
| positive | `#10B981` / `#00FF66` |
| gold | `#D4AF37` |
| negative | `#EF4444` |
| type | monospace grids (`JetBrains Mono`) + geometric sans labels (`Inter`) |
| tab transition | 80ms opacity micro-fade (collateral panels **and** ASI panes) |

## Feature Matrix

| Feature | State | Notes |
|---|---|---|
| Obsidian Slate design system | Done | Tokens in `:root`; mono grids + sans labels; 80ms micro-fade |
| AlphaDB IndexedDB cache (60s) | Done | `AlphaDB` wrapper; objectStore `cache` keyed by URL; 60 000 ms TTL |
| `window.fetch` interceptor | Done | Cache-first (fresh <60s) → network (12s timeout) → stale cache → offline mock |
| Offline mock fallback | Done | `offlineMock()` covers every route; UI never crashes/throws on timeout |
| 2px gradient shimmer on `.loading` | Done | Global `#shimmer` top bar during in-flight fetches + inline `.loading::before` |
| Status bar (providers + cache/net) | Done | AV / Tavily / X / Gemini dots + live ONLINE / CACHED / OFFLINE indicator |
| Command-bar routing | Done | View codes switch tabs; `HELP` dialog; any other token → opens ASI |

### Collateral Views (7)

| # | View | Code | Layout | Route(s) | State |
|---|---|---|---|---|---|
| 1 | Command Center | `CC` | briefing + market watch | `/api/v1/equity/price/quote` (×4 indices) | Done |
| 2 | Universe Builder | `BUILD` | drag-drop 1fr/1fr | `/api/v1/sectors` | Done |
| 3 | Thematic Scanner | `SCAN` | matrix + AI report | `POST /api/v1/scan` | Done |
| 4 | Chronos | `CHRONOS` | **65/35** chart/stats | `/api/v1/equity/price/historical` | Done |
| 5 | Filing Contrast | `CONTRAST` | **50/50** A vs B | `/equity/profile` + `/fundamental/metrics` + `/price/quote` | Done |
| 6 | Yield Curve | `CURV` | 65/35 curve/table | `/api/v1/fixedincome/government/treasury_rates` | Done |
| 7 | News Flow | `FLOW` | headline stream | `/api/v1/news/company` | Done |

### Asset Signature Interface (ASI) — 7 tabs

Opened by typing a ticker in the command bar (or clicking a scanner row / peer).

| Tab | Source | State |
|---|---|---|
| SIGNATURE | profile + metrics + quote (8 metric boxes + description) | Done |
| PRICE | historical (1Y line + 50d MA, SVG) | Done |
| FUNDAMENTALS | `/equity/fundamental/metrics` | Done |
| SIGNALS | computed client-side from history (trend / MA / RSI / momentum / dist-high → buy/hold/sell pills) | Done |
| NEWS | `/api/v1/news/company` | Done |
| PEERS | sector cohort from `/api/v1/sectors` (click to inspect) | Done |
| PROFILE | `/api/v1/equity/profile` (full) | Done |

## Backend Routes (`scripts/app_server.py`)

| Route | Real / Mock | State |
|---|---|---|
| `GET /` | serves `index.html` | Done |
| `GET /api/v1/sectors` | real (`market_universes`) | Done |
| `POST /api/v1/scan` | real (`ThematicSignalAgent` + Gemini 2.5 Flash); **now degrades to graceful empty matrix instead of HTTP 500** when no market data is reachable | Done |
| `GET /api/v1/equity/price/quote` | yfinance + server-side fallback | Done |
| `GET /api/v1/equity/price/historical` | yfinance | Done |
| `GET /api/v1/equity/profile` | yfinance | Done |
| `GET /api/v1/equity/fundamental/metrics` | yfinance | Done |
| `GET /api/v1/news/company` | yfinance | Done |
| `GET /api/v1/fixedincome/government/treasury_rates` | mock | Done |
| `GET /api/v1/currency/price/historical` | yfinance | Done |
| `GET /api/v1/crypto/price/historical` | yfinance | Done |

## Verification

- JS: `node --check` passes; every `getElementById` target exists in markup.
- Server: all 10 routes return `200` against a live `uvicorn` instance.
- Offline resilience: in this sandbox there is **no upstream network**, so yfinance
  returns empty — exercising exactly the timeout/offline path. The terminal renders
  on the server-side fallbacks and the client AlphaDB offline mocks without crashing.
- `POST /api/v1/scan` with unreachable data returns `200` + a "SCAN RETURNED NO DATA"
  report (was `500`).

## Context note

The original takeover brief referenced a prior build (Obsidian Slate, ASI, Chronos,
Filing Contrast) plus 66 OpenBB reference frames in `scratch/frames/`. **Neither the
described build nor the frames were present in this repository/container** (only an
amber Bloomberg-style `scripts/index.html` existed, plus a separate `bb-terminal/`
React app). On instruction to proceed, this terminal was built fresh to the written
spec, reusing the existing FastAPI backend. Layout proportions (Chronos 65/35,
Filing Contrast 50/50, ASI 7 tabs) follow the spec; no frames were available to
pixel-match against.
