"""Public ticker routes: profile, live quote, and chart candles.

These are free (the chart and quote are teasers). Deep financial statements live
under ``/metrics`` and are paywalled by ``PaywallMiddleware``.
"""
from __future__ import annotations

from fastapi import APIRouter, Query

from app.schemas import CandleBar, Quote, TickerProfile
from app.services import market_data

router = APIRouter(prefix="/tickers", tags=["tickers"])


@router.get("/{symbol}/profile", response_model=TickerProfile)
async def profile(symbol: str) -> dict:
    return await market_data.get_profile(symbol)


@router.get("/{symbol}/quote", response_model=Quote)
async def quote(symbol: str) -> dict:
    return await market_data.get_quote(symbol)


@router.get("/{symbol}/candles", response_model=list[CandleBar])
async def candles(symbol: str, days: int = Query(default=365, ge=30, le=1825)) -> list[dict]:
    return await market_data.get_candles(symbol, days=days)
