"""Background worker polling active price alerts and firing notifications.

Run standalone: ``python -m workers.alerts_worker`` (with the backend package on
PYTHONPATH). The worker:

1. Loads all active alerts grouped by symbol.
2. Fetches each symbol's quote once (Redis-cached, shared with the API).
3. Evaluates every alert's condition and dispatches a mock notification on a
   match, then de-duplicates via ``last_triggered_at`` + a Redis cooldown key so
   a user is not spammed every poll cycle.

It is intentionally idempotent and stateless beyond the database and Redis, so
multiple replicas can run safely (the Redis ``SET NX`` cooldown acts as a lock).
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from sqlalchemy import select, update

from app.db.models import AlertCondition, PriceAlert
from app.db.session import SessionLocal
from app.core.redis_client import close_redis, get_redis
from app.services import market_data
from workers.notifications import dispatch

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("alphapulse.alerts")

POLL_INTERVAL_SECONDS = 15
_COOLDOWN_SECONDS = 1800  # don't re-fire the same alert within 30 minutes


def _condition_met(condition: AlertCondition, threshold: float, quote: dict) -> bool:
    price = quote["price"]
    if condition is AlertCondition.ABOVE:
        return price >= threshold
    if condition is AlertCondition.BELOW:
        return price <= threshold
    if condition is AlertCondition.PCT_CHANGE:
        return abs(quote["change_pct"]) >= threshold
    return False


async def _evaluate_once() -> int:
    """Run one evaluation pass. Returns the number of notifications fired."""
    redis = get_redis()
    fired = 0

    async with SessionLocal() as db:
        result = await db.execute(select(PriceAlert).where(PriceAlert.is_active.is_(True)))
        alerts = list(result.scalars().all())

    if not alerts:
        return 0

    symbols = sorted({a.symbol for a in alerts})
    quotes = await asyncio.gather(*(market_data.get_quote(s) for s in symbols))
    quote_by_symbol = {q["symbol"]: q for q in quotes}

    for alert in alerts:
        quote = quote_by_symbol.get(alert.symbol)
        if quote is None or not _condition_met(alert.condition, float(alert.threshold), quote):
            continue

        # Cooldown guard: SET NX ensures only one replica fires per window.
        cooldown_key = f"alert:cooldown:{alert.id}"
        if not await redis.set(cooldown_key, "1", nx=True, ex=_COOLDOWN_SECONDS):
            continue

        await dispatch(
            user_id=str(alert.user_id),
            kind="price_alert",
            payload={
                "alert_id": str(alert.id),
                "symbol": alert.symbol,
                "condition": alert.condition.value,
                "threshold": float(alert.threshold),
                "price": quote["price"],
                "change_pct": quote["change_pct"],
            },
        )
        async with SessionLocal() as db:
            await db.execute(
                update(PriceAlert)
                .where(PriceAlert.id == alert.id)
                .values(last_triggered_at=datetime.now(timezone.utc))
            )
            await db.commit()
        fired += 1

    logger.info("evaluated %d alerts across %d symbols, fired %d", len(alerts), len(symbols), fired)
    return fired


async def run_forever() -> None:
    logger.info("AlphaPulse alerts worker started (interval=%ss)", POLL_INTERVAL_SECONDS)
    try:
        while True:
            try:
                await _evaluate_once()
            except Exception:  # never let one bad cycle kill the worker
                logger.exception("alert evaluation cycle failed")
            await asyncio.sleep(POLL_INTERVAL_SECONDS)
    finally:
        await close_redis()


if __name__ == "__main__":
    asyncio.run(run_forever())
