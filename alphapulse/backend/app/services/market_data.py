"""Market-data access layer.

In production this would call Financial Modeling Prep / Polygon.io. Here every
fetch is routed through a deterministic mock generator so the platform runs with
zero external credentials, while still exercising the exact Redis caching path a
real integration would use. Flip ``USE_MOCK_MARKET_DATA=false`` and supply an
API key to hit the live endpoints (the response shapes match FMP).
"""
from __future__ import annotations

import hashlib
import math
import random
from datetime import datetime, timedelta, timezone

import httpx

from app.core.cache import redis_cache
from app.core.config import settings
from app.schemas import (
    CandleBar,
    DividendMetric,
    EarningsMetric,
    FinancialStatement,
    FinancialStatementRow,
    Quote,
    TickerProfile,
)

_SECTORS = [
    ("Technology", "Consumer Electronics"),
    ("Healthcare", "Drug Manufacturers"),
    ("Financial Services", "Banks"),
    ("Energy", "Oil & Gas"),
    ("Consumer Cyclical", "Internet Retail"),
]


def _seed(symbol: str) -> random.Random:
    """Deterministic RNG so a given symbol always yields stable mock data."""
    digest = hashlib.sha256(symbol.upper().encode()).hexdigest()
    return random.Random(int(digest[:12], 16))


async def _http_get(path: str, params: dict[str, str]) -> dict | list:
    params = {**params, "apikey": settings.MARKET_DATA_API_KEY}
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(f"{settings.MARKET_DATA_BASE_URL}{path}", params=params)
        resp.raise_for_status()
        return resp.json()


# --------------------------------------------------------------------------- #
# Profile                                                                       #
# --------------------------------------------------------------------------- #
@redis_cache(namespace="profile", ttl=settings.CACHE_TTL_PROFILE)
async def get_profile(symbol: str) -> dict:
    symbol = symbol.upper()
    if not settings.USE_MOCK_MARKET_DATA:
        data = await _http_get(f"/profile/{symbol}", {})
        record = data[0] if isinstance(data, list) and data else {}
        return TickerProfile(
            symbol=symbol,
            company_name=record.get("companyName", symbol),
            exchange=record.get("exchangeShortName"),
            sector=record.get("sector"),
            industry=record.get("industry"),
            logo_url=record.get("image"),
            description=record.get("description"),
        ).model_dump()

    rng = _seed(symbol)
    sector, industry = rng.choice(_SECTORS)
    return TickerProfile(
        symbol=symbol,
        company_name=f"{symbol} Holdings Inc.",
        exchange=rng.choice(["NASDAQ", "NYSE"]),
        sector=sector,
        industry=industry,
        logo_url=f"https://ui-avatars.com/api/?name={symbol}&background=0D1117&color=22c55e",
        description=(
            f"{symbol} Holdings Inc. designs, manufactures, and markets a portfolio "
            f"of products and services across the {industry.lower()} space, operating "
            "in segments spanning the Americas, EMEA, and APAC."
        ),
    ).model_dump()


# --------------------------------------------------------------------------- #
# Quote                                                                         #
# --------------------------------------------------------------------------- #
@redis_cache(namespace="quote", ttl=settings.CACHE_TTL_QUOTE)
async def get_quote(symbol: str) -> dict:
    symbol = symbol.upper()
    if not settings.USE_MOCK_MARKET_DATA:
        data = await _http_get(f"/quote/{symbol}", {})
        r = data[0] if isinstance(data, list) and data else {}
        return Quote(
            symbol=symbol,
            price=r.get("price", 0.0),
            change=r.get("change", 0.0),
            change_pct=r.get("changesPercentage", 0.0),
            day_high=r.get("dayHigh", 0.0),
            day_low=r.get("dayLow", 0.0),
            volume=int(r.get("volume", 0)),
            market_cap=r.get("marketCap"),
            updated_at=datetime.now(timezone.utc),
        ).model_dump()

    rng = _seed(symbol)
    base = 40 + rng.random() * 360
    # Intraday jitter keyed to the current minute so the "live" quote moves.
    minute_seed = int(datetime.now(timezone.utc).timestamp() // 60)
    jitter = random.Random(f"{symbol}:{minute_seed}").uniform(-0.03, 0.03)
    price = round(base * (1 + jitter), 2)
    change = round(price * jitter, 2)
    return Quote(
        symbol=symbol,
        price=price,
        change=change,
        change_pct=round(jitter * 100, 2),
        day_high=round(price * 1.012, 2),
        day_low=round(price * 0.988, 2),
        volume=rng.randint(1_000_000, 90_000_000),
        market_cap=round(price * rng.randint(500_000_000, 8_000_000_000)),
        updated_at=datetime.now(timezone.utc),
    ).model_dump()


# --------------------------------------------------------------------------- #
# Chart candles                                                                 #
# --------------------------------------------------------------------------- #
@redis_cache(namespace="chart", ttl=settings.CACHE_TTL_CHART)
async def get_candles(symbol: str, days: int = 365) -> list[dict]:
    symbol = symbol.upper()
    if not settings.USE_MOCK_MARKET_DATA:
        data = await _http_get(
            f"/historical-price-full/{symbol}", {"timeseries": str(days)}
        )
        history = data.get("historical", []) if isinstance(data, dict) else []
        bars: list[dict] = []
        for row in reversed(history):
            ts = int(datetime.strptime(row["date"], "%Y-%m-%d").timestamp())
            bars.append(
                CandleBar(
                    time=ts,
                    open=row["open"],
                    high=row["high"],
                    low=row["low"],
                    close=row["close"],
                    volume=int(row.get("volume", 0)),
                ).model_dump()
            )
        return bars

    rng = _seed(symbol)
    price = 40 + rng.random() * 360
    bars = []
    start = datetime.now(timezone.utc) - timedelta(days=days)
    for i in range(days):
        day = start + timedelta(days=i)
        if day.weekday() >= 5:  # skip weekends
            continue
        drift = math.sin(i / 18) * 0.004
        shock = rng.uniform(-0.025, 0.027) + drift
        open_p = price
        close_p = max(1.0, open_p * (1 + shock))
        high_p = max(open_p, close_p) * (1 + abs(rng.uniform(0, 0.012)))
        low_p = min(open_p, close_p) * (1 - abs(rng.uniform(0, 0.012)))
        bars.append(
            CandleBar(
                time=int(day.timestamp()),
                open=round(open_p, 2),
                high=round(high_p, 2),
                low=round(low_p, 2),
                close=round(close_p, 2),
                volume=rng.randint(1_000_000, 50_000_000),
            ).model_dump()
        )
        price = close_p
    return bars


# --------------------------------------------------------------------------- #
# Financial statements (premium-gated)                                          #
# --------------------------------------------------------------------------- #
@redis_cache(namespace="financials", ttl=settings.CACHE_TTL_FINANCIALS)
async def get_financials(symbol: str, statement: str) -> dict:
    symbol = symbol.upper()
    rng = _seed(f"{symbol}:{statement}")
    periods = [str(y) for y in range(datetime.now().year - 1, datetime.now().year - 5, -1)]

    templates = {
        "income": [
            ("Revenue", 200e9, 0.08),
            ("Cost of Revenue", 110e9, 0.07),
            ("Gross Profit", 90e9, 0.09),
            ("Operating Expenses", 40e9, 0.06),
            ("Operating Income", 50e9, 0.10),
            ("Net Income", 38e9, 0.11),
            ("EPS (Diluted)", 6.1, 0.10),
        ],
        "balance": [
            ("Total Assets", 350e9, 0.05),
            ("Total Liabilities", 280e9, 0.04),
            ("Total Equity", 70e9, 0.07),
            ("Cash & Equivalents", 48e9, 0.03),
            ("Total Debt", 110e9, 0.02),
        ],
        "cash_flow": [
            ("Operating Cash Flow", 95e9, 0.08),
            ("Capital Expenditure", -11e9, 0.05),
            ("Free Cash Flow", 84e9, 0.09),
            ("Financing Cash Flow", -90e9, 0.03),
            ("Net Change in Cash", 6e9, 0.12),
        ],
    }
    rows: list[FinancialStatementRow] = []
    for label, base, growth in templates.get(statement, []):
        values: dict[str, float | None] = {}
        val = base * (1 + rng.uniform(-0.05, 0.05))
        for period in periods:
            values[period] = round(val, 2)
            val = val / (1 + growth + rng.uniform(-0.02, 0.02))
        rows.append(FinancialStatementRow(label=label, values=values))

    return FinancialStatement(
        statement=statement,  # type: ignore[arg-type]
        periods=periods,
        rows=rows,
    ).model_dump()


@redis_cache(namespace="earnings", ttl=settings.CACHE_TTL_FINANCIALS)
async def get_earnings(symbol: str) -> list[dict]:
    rng = _seed(f"{symbol}:earn")
    out: list[dict] = []
    for q in range(4):
        date = (datetime.now(timezone.utc) - timedelta(days=q * 91)).strftime("%Y-%m-%d")
        est = round(1.2 + rng.uniform(-0.3, 0.4), 2)
        out.append(
            EarningsMetric(
                date=date,
                eps_estimate=est,
                eps_actual=round(est + rng.uniform(-0.15, 0.25), 2),
                revenue_estimate=round(80e9 + rng.uniform(-5e9, 5e9)),
                revenue_actual=round(80e9 + rng.uniform(-3e9, 7e9)),
            ).model_dump()
        )
    return out


@redis_cache(namespace="dividends", ttl=settings.CACHE_TTL_FINANCIALS)
async def get_dividends(symbol: str) -> list[dict]:
    rng = _seed(f"{symbol}:div")
    out: list[dict] = []
    amount = round(0.20 + rng.uniform(0, 0.6), 2)
    for q in range(4):
        ex = datetime.now(timezone.utc) - timedelta(days=q * 91)
        out.append(
            DividendMetric(
                ex_date=ex.strftime("%Y-%m-%d"),
                payment_date=(ex + timedelta(days=14)).strftime("%Y-%m-%d"),
                amount=amount,
                yield_pct=round(rng.uniform(0.4, 2.8), 2),
            ).model_dump()
        )
    return out
