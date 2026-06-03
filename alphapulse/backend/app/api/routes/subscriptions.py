"""Subscription routes: current status, Stripe checkout, and webhook ingest."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.cache import invalidate
from app.db.models import Subscription, SubscriptionStatus, SubscriptionTier, User
from app.db.session import get_db
from app.schemas import CheckoutRequest, CheckoutSession, SubscriptionOut
from app.services import stripe_service

router = APIRouter(prefix="/subscriptions", tags=["subscriptions"])


@router.get("/me", response_model=SubscriptionOut)
async def my_subscription(
    db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)
) -> Subscription:
    result = await db.execute(select(Subscription).where(Subscription.user_id == user.id))
    sub = result.scalar_one_or_none()
    if sub is None:
        sub = Subscription(user_id=user.id, tier=SubscriptionTier.FREE)
        db.add(sub)
        await db.flush()
    return sub


@router.post("/checkout", response_model=CheckoutSession)
async def create_checkout(
    payload: CheckoutRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> CheckoutSession:
    url, session_id = await stripe_service.create_checkout_session(
        customer_email=user.email,
        tier=payload.tier,
        success_url=payload.success_url,
        cancel_url=payload.cancel_url,
    )
    return CheckoutSession(checkout_url=url, session_id=session_id)


@router.post("/confirm-mock", response_model=SubscriptionOut)
async def confirm_mock(
    tier: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Subscription:
    """Mock-mode only: promotes the user after the simulated checkout redirect."""
    if not stripe_service.is_mock():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Live mode active")
    if tier not in {"premium", "pro"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid tier")

    result = await db.execute(select(Subscription).where(Subscription.user_id == user.id))
    sub = result.scalar_one_or_none() or Subscription(user_id=user.id)
    sub.tier = SubscriptionTier(tier)
    sub.status = SubscriptionStatus.ACTIVE
    sub.stripe_customer_id = f"cus_mock_{user.id.hex[:12]}"
    sub.current_period_end = datetime.fromtimestamp(
        stripe_service.mock_period_end(), tz=timezone.utc
    )
    db.add(sub)
    await db.flush()
    await invalidate("entitlement", str(user.id))
    return sub


@router.post("/webhook", status_code=status.HTTP_200_OK)
async def stripe_webhook(
    request: Request,
    stripe_signature: str = Header(default="", alias="Stripe-Signature"),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Handle Stripe lifecycle events to keep subscription rows in sync."""
    payload = await request.body()
    try:
        event = stripe_service.verify_webhook(payload, stripe_signature)
    except Exception as exc:  # signature failure
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Bad signature") from exc

    event_type = event.get("type")
    obj = event.get("data", {}).get("object", {})

    if event_type in {"customer.subscription.updated", "customer.subscription.created",
                      "customer.subscription.deleted"}:
        customer_id = obj.get("customer")
        result = await db.execute(
            select(Subscription).where(Subscription.stripe_customer_id == customer_id)
        )
        sub = result.scalar_one_or_none()
        if sub is not None:
            price_id = (
                obj.get("items", {}).get("data", [{}])[0].get("price", {}).get("id", "")
            )
            sub.tier = stripe_service.tier_from_price(price_id)
            sub.status = stripe_service.map_stripe_status(obj.get("status", "incomplete"))
            sub.stripe_subscription_id = obj.get("id")
            sub.cancel_at_period_end = bool(obj.get("cancel_at_period_end", False))
            period_end = obj.get("current_period_end")
            if period_end:
                sub.current_period_end = datetime.fromtimestamp(period_end, tz=timezone.utc)
            await db.flush()
            await invalidate("entitlement", str(sub.user_id))

    return {"received": True}
