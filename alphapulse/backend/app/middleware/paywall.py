"""Subscription paywall enforcement.

Two layers cooperate:

1. ``PaywallMiddleware`` — a coarse ASGI guard that blocks entire premium route
   namespaces (e.g. ``/api/v1/metrics/**``) for callers without an active paid
   subscription. It performs a cheap JWT + Redis entitlement check before the
   request ever reaches a route handler.
2. ``enforce_article_access`` / ``require_tier`` — fine-grained helpers used
   inside handlers that serve mixed free/premium payloads (article bodies,
   financial statements) where a hard 402 would be wrong.
"""
from __future__ import annotations

import uuid

import jwt
from fastapi import Depends, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp

from app.api.deps import get_optional_user, has_entitlement, user_tier
from app.core.cache import cached_json
from app.core.config import settings
from app.core.security import decode_token
from app.db.models import (
    ArticleAccess,
    Subscription,
    SubscriptionStatus,
    SubscriptionTier,
    User,
)
from app.db.session import SessionLocal
from sqlalchemy import select

# Route prefixes that require a paid tier in full. Mixed-content routes
# (articles, financial statements) are intentionally excluded — they degrade
# gracefully instead of returning 402.
_PROTECTED_PREFIXES = ("/api/v1/metrics",)

_ENTITLEMENT_TTL = 30  # seconds; short so cancellations propagate quickly


async def _entitlement_for_token(token: str) -> str:
    """Resolve a user's effective tier from a JWT, cached in Redis."""
    payload = decode_token(token, expected_type="access")
    user_id = payload["sub"]

    async def _load() -> str:
        async with SessionLocal() as db:
            result = await db.execute(
                select(Subscription).where(Subscription.user_id == uuid.UUID(user_id))
            )
            sub = result.scalar_one_or_none()
            if sub is None or sub.status not in {
                SubscriptionStatus.ACTIVE,
                SubscriptionStatus.TRIALING,
            }:
                return SubscriptionTier.FREE.value
            return sub.tier.value

    return await cached_json("entitlement", (user_id,), _ENTITLEMENT_TTL, _load)


class PaywallMiddleware(BaseHTTPMiddleware):
    """Blocks fully-premium namespaces unless the caller is a paid subscriber."""

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next) -> Response:
        path = request.url.path
        if not any(path.startswith(p) for p in _PROTECTED_PREFIXES):
            return await call_next(request)

        auth = request.headers.get("authorization", "")
        token = auth[7:] if auth.lower().startswith("bearer ") else ""
        if not token:
            return self._blocked("Authentication required for premium data")

        try:
            tier = await _entitlement_for_token(token)
        except jwt.InvalidTokenError:
            return self._blocked("Invalid or expired token")

        if tier == SubscriptionTier.FREE.value:
            return self._blocked(
                "An active AlphaPulse subscription is required to access this data"
            )
        return await call_next(request)

    @staticmethod
    def _blocked(detail: str) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            content={"detail": detail, "code": "subscription_required"},
        )


# --------------------------------------------------------------------------- #
# Fine-grained helpers                                                          #
# --------------------------------------------------------------------------- #
_ACCESS_TO_TIER = {
    ArticleAccess.PUBLIC: SubscriptionTier.FREE,
    ArticleAccess.PREMIUM: SubscriptionTier.PREMIUM,
    ArticleAccess.PRO: SubscriptionTier.PRO,
}


def can_view_article(user: User | None, access_level: ArticleAccess) -> bool:
    """Whether ``user`` may read the full body of an article."""
    return has_entitlement(user, _ACCESS_TO_TIER[access_level])


def require_tier(required: SubscriptionTier):
    """Dependency factory that hard-blocks a handler with 402 below ``required``."""

    async def _guard(user: User | None = Depends(get_optional_user)) -> User | None:
        if not has_entitlement(user, required):
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail=f"Requires {required.value} subscription",
            )
        return user

    return _guard
