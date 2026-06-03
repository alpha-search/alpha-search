"""Tests for the tier-based entitlement logic that drives the paywall."""
from __future__ import annotations

import types
import uuid
from datetime import datetime, timezone

from app.api.deps import has_entitlement, user_tier
from app.db.models import (
    ArticleAccess,
    SubscriptionStatus,
    SubscriptionTier,
)
from app.middleware.paywall import can_view_article


def _fake_user(tier: SubscriptionTier | None, status: SubscriptionStatus = SubscriptionStatus.ACTIVE):
    if tier is None:
        return types.SimpleNamespace(id=uuid.uuid4(), subscription=None)
    sub = types.SimpleNamespace(
        tier=tier,
        status=status,
        current_period_end=datetime(2030, 1, 1, tzinfo=timezone.utc),
    )
    return types.SimpleNamespace(id=uuid.uuid4(), subscription=sub)


def test_anonymous_is_free() -> None:
    assert user_tier(None) is SubscriptionTier.FREE


def test_canceled_subscription_downgrades_to_free() -> None:
    user = _fake_user(SubscriptionTier.PRO, SubscriptionStatus.CANCELED)
    assert user_tier(user) is SubscriptionTier.FREE


def test_pro_satisfies_premium_requirement() -> None:
    user = _fake_user(SubscriptionTier.PRO)
    assert has_entitlement(user, SubscriptionTier.PREMIUM)
    assert has_entitlement(user, SubscriptionTier.PRO)


def test_premium_does_not_satisfy_pro() -> None:
    user = _fake_user(SubscriptionTier.PREMIUM)
    assert has_entitlement(user, SubscriptionTier.PREMIUM)
    assert not has_entitlement(user, SubscriptionTier.PRO)


def test_article_access_matrix() -> None:
    free = _fake_user(None)
    premium = _fake_user(SubscriptionTier.PREMIUM)

    assert can_view_article(free, ArticleAccess.PUBLIC)
    assert not can_view_article(free, ArticleAccess.PREMIUM)
    assert can_view_article(premium, ArticleAccess.PREMIUM)
    assert not can_view_article(premium, ArticleAccess.PRO)
