"""Reusable FastAPI dependencies: current user, role guards, entitlements."""
from __future__ import annotations

import uuid

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.security import decode_token
from app.db.models import Subscription, SubscriptionStatus, SubscriptionTier, User, UserRole
from app.db.session import get_db

_bearer = HTTPBearer(auto_error=False)

# Tiers ranked so a higher tier satisfies a lower requirement.
_TIER_RANK = {
    SubscriptionTier.FREE: 0,
    SubscriptionTier.PREMIUM: 1,
    SubscriptionTier.PRO: 2,
}
_ACTIVE_STATUSES = {SubscriptionStatus.ACTIVE, SubscriptionStatus.TRIALING}


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Resolve and validate the bearer token into an active User row."""
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        payload = decode_token(credentials.credentials, expected_type="access")
        user_id = uuid.UUID(payload["sub"])
    except (jwt.InvalidTokenError, KeyError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    result = await db.execute(
        select(User)
        .options(selectinload(User.subscription))
        .where(User.id == user_id)
    )
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


async def get_optional_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: AsyncSession = Depends(get_db),
) -> User | None:
    """Like :func:`get_current_user` but returns ``None`` for anonymous viewers.

    Used by routes that serve both free previews and full premium content.
    """
    if credentials is None:
        return None
    try:
        return await get_current_user(credentials, db)
    except HTTPException:
        return None


def require_role(*roles: UserRole):
    """Dependency factory enforcing that the user holds one of ``roles``."""

    async def _guard(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles and user.role != UserRole.ADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient role for this operation",
            )
        return user

    return _guard


def user_tier(user: User | None) -> SubscriptionTier:
    """Effective tier for a user, honouring subscription status."""
    if user is None or user.subscription is None:
        return SubscriptionTier.FREE
    sub = user.subscription
    if sub.status not in _ACTIVE_STATUSES:
        return SubscriptionTier.FREE
    return sub.tier


def has_entitlement(user: User | None, required: SubscriptionTier) -> bool:
    """True when ``user`` holds at least the ``required`` subscription tier."""
    return _TIER_RANK[user_tier(user)] >= _TIER_RANK[required]
