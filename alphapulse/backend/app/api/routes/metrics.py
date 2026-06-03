"""Premium financial metrics — gated wholesale by ``PaywallMiddleware``.

Any request reaching these handlers has already passed the paywall, so the code
here is concerned only with data shaping. All upstream fetches are Redis-cached.
"""
from __future__ import annotations

from fastapi import APIRouter, Path

from app.schemas import DividendMetric, EarningsMetric, FinancialStatement
from app.services import market_data

router = APIRouter(prefix="/metrics", tags=["metrics (premium)"])

_STATEMENTS = {"income", "balance", "cash_flow"}


@router.get("/{symbol}/financials/{statement}", response_model=FinancialStatement)
async def financials(
    symbol: str,
    statement: str = Path(..., pattern="^(income|balance|cash_flow)$"),
) -> dict:
    return await market_data.get_financials(symbol, statement)


@router.get("/{symbol}/earnings", response_model=list[EarningsMetric])
async def earnings(symbol: str) -> list[dict]:
    return await market_data.get_earnings(symbol)


@router.get("/{symbol}/dividends", response_model=list[DividendMetric])
async def dividends(symbol: str) -> list[dict]:
    return await market_data.get_dividends(symbol)
