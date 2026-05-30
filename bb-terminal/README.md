# BBterminal

A Bloomberg-style intelligence dashboard for free financial data.

Runs locally. One data layer (OpenBB Platform — 50+ providers, 270 endpoints), one amber-on-black terminal UI, and a built-in rules engine that turns numbers into **signals** so you don't stare at raw data trying to remember what matters.

Built on [OpenBB](https://github.com/OpenBB-finance/OpenBB) + Vite + React + TypeScript + TradingView lightweight-charts.

![screenshot — Command Center landing page](app/v2-help.png)

---

## Install in one line

Paste this into your terminal (macOS or Linux):

```bash
curl -fsSL https://raw.githubusercontent.com/vaughanf1/BB-Terminal/main/install.sh | bash
```

That's it. The installer will:

1. Check that `git`, Python 3.10+, and Node.js 18+ are on your system (and tell you exactly how to install them if not)
2. Clone this repo to `~/BB-Terminal`
3. Install OpenBB Platform and all its data providers (~3 min)
4. Install the UI dependencies (~1 min)
5. Launch both servers and open the terminal in your browser

**Windows users:** run the command inside **WSL** (Ubuntu) or **Git Bash**.

### Every launch after that

```bash
cd ~/BB-Terminal
./start.sh     # launches API + UI, opens your browser
./stop.sh      # when you're done
```

The UI lives at **http://localhost:5173/**. All data works out of the box via **Yahoo Finance** — no API keys required. Optional providers (FRED, TradingEconomics, FMP, Polygon, etc.) can be added to `~/.openbb_platform/user_settings.json`.

### Prerequisites

- macOS or Linux (Windows via WSL)
- Python 3.10, 3.11, or 3.12
- Node.js 18+
- ~2 GB free disk (OpenBB pulls many provider libraries)

### Manual install (for anyone who doesn't trust `curl | bash`)

Fair enough — that pattern is a real risk if you don't know what's in the script. You can read [`install.sh`](./install.sh) first, or skip it entirely and run the steps yourself:

```bash
git clone https://github.com/vaughanf1/BB-Terminal.git
cd BB-Terminal
./setup.sh       # installs OpenBB + UI (~3-5 min)
./start.sh       # launches the terminal
```

---

## What it does

### Command Center (`CC`) — the landing page
One screen, 30-second briefing: US indices with sparklines, yield-curve shape (flat / normal / inverted), FX majors, BTC/ETH, top 5 gainers + losers (click to drill in), headline news.

### INTEL (`<TICKER>` or `AAPL INTEL`) — the scorecard
Synthesizes the noisy stuff into an interpretable opinion:

```
INTELLIGENCE VERDICT   BULLISH
● 8 bullish   ● 2 neutral   ● 1 bearish

TECHNICAL              VALUATION              FUNDAMENTALS
● Above 50d MA +5.1%   ● Fair P/E 22.4x       ● Revenue growing +12%
● Above 200d MA +8.2%  ● Rich EV/EBITDA 25x   ● Operating margin strong
● Upper range 73% of   ● Fwd P/E improving    ● Low leverage

ANALYSTS               DIVIDEND
● Buy consensus        ● Healthy payout
● Bullish target +14%
```

Each dot is a *rule*, not a prediction — see `app/src/lib/signals.ts` for the thresholds. It's meant to save the 15 minutes of reading, not replace judgement.

### The function codes
Type any of these in the command bar:

| Code    | What it shows                              |
|---------|--------------------------------------------|
| `CC`    | Command Center dashboard (home)            |
| `HELP`  | Full function directory                    |
| `<TICKER>` | Opens INTEL scorecard                   |
| `DES`   | Company description / profile              |
| `GP`    | Candlestick chart, 1M–5Y                   |
| `QR`    | Live quote (refreshes every 3s)            |
| `HP`    | Historical prices table                    |
| `FA`    | 5-year income statements                   |
| `KEY`   | All ratios (valuation, growth, margins…)   |
| `DVD`   | Dividend history + annual totals           |
| `EE`    | Analyst targets + recommendation           |
| `NI`    | Company news (50 headlines)                |
| `OMON`  | Full options chain — calls / strike / puts |
| `WEI`   | World equity indices                       |
| `MOV`   | Market movers (gainers / losers / active)  |
| `CRYPTO`| Top-12 crypto prices + sparklines          |
| `FXC`   | Major FX pairs                             |
| `CURV`  | US Treasury yield curve + spreads          |

Syntax: `[SYMBOL] CODE` — e.g., `TSLA KEY`, or `WEI` (no symbol), or just `NVDA` (defaults to INTEL).

Keyboard: `↑/↓` walks history, `⇥` autocompletes codes, `/` focuses the command bar, `<GO>` or `Enter` executes.

---

## YouTube demo script

Tight 5-7 minute walk-through for the video:

1. **Open on a black screen** — `./start.sh`, browser pops up to Command Center. Say: *"Here's a Bloomberg-style terminal I built in an afternoon, running entirely on my laptop, using free data."*
2. **CC dashboard tour (45s)** — "S&P's down 0.4%, VIX is up 2%, yield curve is normal at +52bps, biggest gainer today is URI up 23%."
3. **Click a gainer** — it opens INTEL. *"Now the terminal tells me what it thinks: 5 bullish, 2 bearish signals. This stock is trading at the upper range, P/E is rich but revenue is growing 15% — so the market's paying for growth. Without this synthesis, I'd have had to pull 6 different screens."*
4. **Type `TSLA` + Enter** — INTEL refreshes instantly. Point at the verdict badge.
5. **Type `TSLA OMON`** — full options chain fills the screen. *"That's every AAPL strike, calls left, puts right, in-the-money highlighted."*
6. **Type `CURV`** — yield curve chart. *"Here's the US Treasury yield curve with today, a week ago, and a month ago overlaid. 2s-10s is +52 basis points — normal, not inverted."*
7. **Type `WEI`** — world indices. *"Global markets by region."*
8. **Wrap** — *"16 functions, tabs across the top like Bloomberg Launchpad, completely free. Clone the repo, run `./setup.sh`, done. Link in description."*

### Shot list for the video
- Terminal window (black, amber) — at least one wide shot
- Command bar typing with autocomplete appearing
- Clicking between tabs
- The yield curve drawing itself after load
- Scrolling the options chain
- The INTEL verdict badge zoom-in

---

## Architecture (1 min)

- **Python API**: `openbb-api` (FastAPI + Uvicorn) on port 6900. Exposes `/api/v1/...`  
- **Frontend**: Vite + React + TypeScript on port 5173. Vite proxies `/api` to the Python process.
- **Data**: Yahoo Finance via OpenBB (no key). Free tier covers every function in this terminal today. Richer providers (fundamental data depth, unusual options flow, economic calendar) need keys.
- **Signals**: plain-JS rules in `app/src/lib/signals.ts` — transparent, auditable, tweakable.

```
┌──────────┐  HTTP   ┌────────────────┐  HTTP   ┌──────────────┐
│ Browser  │────────▶│ Vite dev (5173)│────────▶│ OpenBB (6900)│──▶ Yahoo, SEC, FRED…
└──────────┘         │ + /api proxy   │         └──────────────┘
                     └────────────────┘
```

---

## Known limits

- **Polling, not streaming.** Yahoo Finance has no WebSocket in OpenBB, so quotes refresh every 3–60s depending on the panel. For live ticks you'd need a broker feed (IBKR, Alpaca) — not wired in yet.
- **Yahoo symbol quirks.** A handful of Asian indices (`^N225`, `^HSI`, `^AXJO`, `^TWII`) and a few crypto tickers don't return via OpenBB's Yahoo provider; those cells show "—".
- **Rules are heuristics.** The INTEL signals are rules of thumb, not predictions. Tweak the thresholds in `signals.ts` to match your own framework.
- **Economic calendar, CPI, world news** need provider API keys (TradingEconomics, FRED, Biztoc). The UI handles the 401 gracefully.

---

## Adding API keys (optional)

```bash
# Edit this file
~/.openbb_platform/user_settings.json
```

```json
{
  "credentials": {
    "fred_api_key": "…",
    "fmp_api_key": "…",
    "intrinio_api_key": "…"
  }
}
```

Restart the API after changing (`./stop.sh && ./start.sh`).

---

## Repo layout

```
BBterminal/
├── setup.sh            # one-time install
├── start.sh            # launch API + UI
├── stop.sh             # kill both
├── README.md
├── .venv/              # Python env (created by setup)
├── OpenBB/             # cloned upstream repo, for reference
└── app/                # the terminal UI
    ├── src/
    │   ├── App.tsx
    │   ├── components/ (CommandBar, WorkspaceTabs, FunctionPanel, StatusBar)
    │   ├── functions/  (CC, INTEL, DES, GP, QR, HP, FA, KEY, DVD, EE, NI,
    │   │               WEI, MOV, OMON, CURV, FXC, CRYPTO, HELP)
    │   ├── lib/        (api.ts, signals.ts, functions.ts, format.ts, cn.ts)
    │   └── store/      (workspaceStore.ts)
    └── tailwind.config.js
```

---

## License

- Your BBterminal code: yours to relicense.
- OpenBB Platform: AGPL-v3 (upstream).
- Yahoo Finance data: subject to Yahoo's terms — personal use only.
