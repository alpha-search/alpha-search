"""Stripe integration for the subscription paywall.

When ``STRIPE_SECRET_KEY`` is a mock value the service short-circuits to a
deterministic in-memory flow so the platform is fully testable offline. With a
real key it issues genuine Checkout Sessions and verifies webhook signatures.
"""
from __future__ import annotations

import time
import uuid

import stripe

from app.core.config import settings
from app.db.models import SubscriptionStatus, SubscriptionTier

stripe.api_key = settings.STRIPE_SECRET_KEY

_PRICE_BY_TIER = {
    "premium": settings.STRIPE_PRICE_PREMIUM,
    "pro": settings.STRIPE_PRICE_PRO,
}
_TIER_BY_PRICE = {v: k for k, v in _PRICE_BY_TIER.items()}

_IS_MOCK = settings.STRIPE_SECRET_KEY.endswith("_mock")


def is_mock() -> bool:
    return _IS_MOCK


async def create_checkout_session(
    *, customer_email: str, tier: str, success_url: str, cancel_url: str
) -> tuple[str, str]:
    """Return ``(checkout_url, session_id)`` for the requested tier."""
    if _IS_MOCK:
        session_id = f"cs_mock_{uuid.uuid4().hex[:24]}"
        # The mock checkout page lives on the frontend and immediately confirms.
        url = f"{success_url}?session_id={session_id}&tier={tier}&mock=1"
        return url, session_id

    session = stripe.checkout.Session.create(
        mode="subscription",
        customer_email=customer_email,
        line_items=[{"price": _PRICE_BY_TIER[tier], "quantity": 1}],
        success_url=f"{success_url}?session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=cancel_url,
        metadata={"tier": tier},
    )
    return session.url, session.id


def verify_webhook(payload: bytes, signature: str) -> dict:
    """Verify a Stripe webhook signature and return the parsed event."""
    if _IS_MOCK:
        import json

        return json.loads(payload.decode("utf-8"))
    return stripe.Webhook.construct_event(
        payload, signature, settings.STRIPE_WEBHOOK_SECRET
    )


def tier_from_price(price_id: str) -> SubscriptionTier:
    return SubscriptionTier(_TIER_BY_PRICE.get(price_id, "free"))


def map_stripe_status(status: str) -> SubscriptionStatus:
    mapping = {
        "active": SubscriptionStatus.ACTIVE,
        "trialing": SubscriptionStatus.TRIALING,
        "past_due": SubscriptionStatus.PAST_DUE,
        "canceled": SubscriptionStatus.CANCELED,
        "incomplete": SubscriptionStatus.INCOMPLETE,
        "incomplete_expired": SubscriptionStatus.CANCELED,
        "unpaid": SubscriptionStatus.PAST_DUE,
    }
    return mapping.get(status, SubscriptionStatus.INCOMPLETE)


def mock_period_end() -> int:
    """30 days out, used by the mock checkout confirmation."""
    return int(time.time()) + 30 * 24 * 3600
