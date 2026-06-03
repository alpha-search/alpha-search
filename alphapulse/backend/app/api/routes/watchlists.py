"""Watchlist and price-alert routes.

Watchlist items carry a live quote (Redis-cached) when listed, so the frontend
renders a real-time-feeling table. Alerts are persisted and polled by the
background worker in ``workers/alerts_worker.py``.
"""
from __future__ import annotations

import asyncio
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_user
from app.db.models import PriceAlert, User, Watchlist, WatchlistItem
from app.db.session import get_db
from app.schemas import (
    AlertCreate,
    AlertOut,
    Quote,
    WatchlistItemCreate,
    WatchlistItemOut,
    WatchlistOut,
)
from app.services import market_data

router = APIRouter(prefix="/watchlist", tags=["watchlist"])


async def _get_or_create_default(db: AsyncSession, user: User) -> Watchlist:
    result = await db.execute(
        select(Watchlist)
        .options(selectinload(Watchlist.items))
        .where(Watchlist.user_id == user.id)
        .order_by(Watchlist.created_at.asc())
    )
    watchlist = result.scalars().first()
    if watchlist is None:
        watchlist = Watchlist(user_id=user.id, name="My Watchlist")
        db.add(watchlist)
        await db.flush()
        await db.refresh(watchlist, attribute_names=["items"])
    return watchlist


@router.get("", response_model=WatchlistOut)
async def get_watchlist(
    db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)
) -> Watchlist:
    return await _get_or_create_default(db, user)


@router.get("/quotes", response_model=list[Quote])
async def watchlist_quotes(
    db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)
) -> list[dict]:
    watchlist = await _get_or_create_default(db, user)
    symbols = [item.symbol for item in watchlist.items]
    # Concurrent, individually-cached quote fetches.
    quotes = await asyncio.gather(*(market_data.get_quote(s) for s in symbols))
    return list(quotes)


@router.post("/items", response_model=WatchlistItemOut, status_code=status.HTTP_201_CREATED)
async def add_item(
    payload: WatchlistItemCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> WatchlistItem:
    watchlist = await _get_or_create_default(db, user)
    symbol = payload.symbol.upper().lstrip("$")
    if any(item.symbol == symbol for item in watchlist.items):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Already on watchlist")
    item = WatchlistItem(watchlist_id=watchlist.id, symbol=symbol)
    db.add(item)
    await db.flush()
    return item


@router.delete("/items/{symbol}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_item(
    symbol: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    watchlist = await _get_or_create_default(db, user)
    result = await db.execute(
        select(WatchlistItem).where(
            WatchlistItem.watchlist_id == watchlist.id,
            WatchlistItem.symbol == symbol.upper().lstrip("$"),
        )
    )
    item = result.scalar_one_or_none()
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not on watchlist")
    await db.delete(item)


# --------------------------------------------------------------------------- #
# Price alerts                                                                  #
# --------------------------------------------------------------------------- #
@router.get("/alerts", response_model=list[AlertOut])
async def list_alerts(
    db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)
) -> list[PriceAlert]:
    result = await db.execute(
        select(PriceAlert).where(PriceAlert.user_id == user.id).order_by(
            PriceAlert.created_at.desc()
        )
    )
    return list(result.scalars().all())


@router.post("/alerts", response_model=AlertOut, status_code=status.HTTP_201_CREATED)
async def create_alert(
    payload: AlertCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> PriceAlert:
    alert = PriceAlert(
        user_id=user.id,
        symbol=payload.symbol.upper().lstrip("$"),
        condition=payload.condition,
        threshold=payload.threshold,
    )
    db.add(alert)
    await db.flush()
    return alert


@router.delete("/alerts/{alert_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_alert(
    alert_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(PriceAlert).where(PriceAlert.id == alert_id, PriceAlert.user_id == user.id)
    )
    alert = result.scalar_one_or_none()
    if alert is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert not found")
    await db.delete(alert)
