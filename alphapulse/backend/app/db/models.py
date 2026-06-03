"""SQLAlchemy ORM models for AlphaPulse core data.

These mirror the Prisma schema in ``prisma/schema.prisma`` and the TimescaleDB
hypertable defined in ``sql/timescale.sql``. Time-series price metrics are NOT
modelled here as a regular table — they live in the ``ticker_metrics``
hypertable and are queried via raw SQL in ``services/market_data.py`` for
ingestion throughput.
"""
from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Declarative base with a shared UUID primary-key convention."""


def _pk() -> Mapped[uuid.UUID]:
    return mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)


# --------------------------------------------------------------------------- #
# Enums                                                                        #
# --------------------------------------------------------------------------- #
class UserRole(str, enum.Enum):
    READER = "reader"
    CONTRIBUTOR = "contributor"
    ADMIN = "admin"


class SubscriptionTier(str, enum.Enum):
    FREE = "free"
    PREMIUM = "premium"
    PRO = "pro"


class SubscriptionStatus(str, enum.Enum):
    ACTIVE = "active"
    TRIALING = "trialing"
    PAST_DUE = "past_due"
    CANCELED = "canceled"
    INCOMPLETE = "incomplete"


class ArticleAccess(str, enum.Enum):
    PUBLIC = "public"
    PREMIUM = "premium"
    PRO = "pro"


class ArticleStatus(str, enum.Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class AlertCondition(str, enum.Enum):
    ABOVE = "above"
    BELOW = "below"
    PCT_CHANGE = "pct_change"


# --------------------------------------------------------------------------- #
# Users & auth                                                                 #
# --------------------------------------------------------------------------- #
class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = _pk()
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str] = mapped_column(String(120), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        SAEnum(UserRole, name="user_role"), default=UserRole.READER, nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    avatar_url: Mapped[str | None] = mapped_column(String(512))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    subscription: Mapped["Subscription | None"] = relationship(
        back_populates="user", uselist=False, cascade="all, delete-orphan"
    )
    articles: Mapped[list["Article"]] = relationship(back_populates="author")
    watchlists: Mapped[list["Watchlist"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    alerts: Mapped[list["PriceAlert"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


# --------------------------------------------------------------------------- #
# Subscriptions                                                                #
# --------------------------------------------------------------------------- #
class Subscription(Base):
    __tablename__ = "subscriptions"

    id: Mapped[uuid.UUID] = _pk()
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    tier: Mapped[SubscriptionTier] = mapped_column(
        SAEnum(SubscriptionTier, name="subscription_tier"),
        default=SubscriptionTier.FREE,
        nullable=False,
    )
    status: Mapped[SubscriptionStatus] = mapped_column(
        SAEnum(SubscriptionStatus, name="subscription_status"),
        default=SubscriptionStatus.ACTIVE,
        nullable=False,
    )
    stripe_customer_id: Mapped[str | None] = mapped_column(String(255), index=True)
    stripe_subscription_id: Mapped[str | None] = mapped_column(String(255), index=True)
    current_period_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancel_at_period_end: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    user: Mapped[User] = relationship(back_populates="subscription")


# --------------------------------------------------------------------------- #
# Tickers                                                                       #
# --------------------------------------------------------------------------- #
class Ticker(Base):
    __tablename__ = "tickers"

    id: Mapped[uuid.UUID] = _pk()
    symbol: Mapped[str] = mapped_column(String(16), unique=True, index=True, nullable=False)
    company_name: Mapped[str] = mapped_column(String(255), nullable=False)
    exchange: Mapped[str | None] = mapped_column(String(32))
    sector: Mapped[str | None] = mapped_column(String(120))
    industry: Mapped[str | None] = mapped_column(String(120))
    logo_url: Mapped[str | None] = mapped_column(String(512))
    description: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    article_links: Mapped[list["ArticleTicker"]] = relationship(back_populates="ticker")


# --------------------------------------------------------------------------- #
# Articles (Contributor CMS)                                                    #
# --------------------------------------------------------------------------- #
class Article(Base):
    __tablename__ = "articles"

    id: Mapped[uuid.UUID] = _pk()
    slug: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    body_markdown: Mapped[str] = mapped_column(Text, nullable=False)
    # First N characters always served free; the remainder is paywalled.
    free_preview: Mapped[str] = mapped_column(Text, nullable=False, default="")
    disclosure: Mapped[str] = mapped_column(Text, nullable=False)
    cover_image_url: Mapped[str | None] = mapped_column(String(512))
    access_level: Mapped[ArticleAccess] = mapped_column(
        SAEnum(ArticleAccess, name="article_access"),
        default=ArticleAccess.PUBLIC,
        nullable=False,
    )
    status: Mapped[ArticleStatus] = mapped_column(
        SAEnum(ArticleStatus, name="article_status"),
        default=ArticleStatus.DRAFT,
        nullable=False,
    )
    author_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    tags: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    view_count: Mapped[int] = mapped_column(default=0)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    author: Mapped[User] = relationship(back_populates="articles")
    ticker_links: Mapped[list["ArticleTicker"]] = relationship(
        back_populates="article", cascade="all, delete-orphan"
    )

    __table_args__ = (Index("ix_articles_status_published", "status", "published_at"),)


class ArticleTicker(Base):
    """Many-to-many between Articles and Tickers (a single $ tag)."""

    __tablename__ = "article_tickers"

    article_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("articles.id", ondelete="CASCADE"), primary_key=True
    )
    ticker_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tickers.id", ondelete="CASCADE"), primary_key=True
    )
    # The author's stated stance, surfaced on the ticker page.
    sentiment: Mapped[str | None] = mapped_column(String(16))  # bullish / bearish / neutral

    article: Mapped[Article] = relationship(back_populates="ticker_links")
    ticker: Mapped[Ticker] = relationship(back_populates="article_links")


# --------------------------------------------------------------------------- #
# Watchlists & alerts                                                           #
# --------------------------------------------------------------------------- #
class Watchlist(Base):
    __tablename__ = "watchlists"

    id: Mapped[uuid.UUID] = _pk()
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(120), default="My Watchlist", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped[User] = relationship(back_populates="watchlists")
    items: Mapped[list["WatchlistItem"]] = relationship(
        back_populates="watchlist", cascade="all, delete-orphan"
    )


class WatchlistItem(Base):
    __tablename__ = "watchlist_items"

    id: Mapped[uuid.UUID] = _pk()
    watchlist_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("watchlists.id", ondelete="CASCADE"), nullable=False
    )
    symbol: Mapped[str] = mapped_column(String(16), nullable=False)
    added_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    watchlist: Mapped[Watchlist] = relationship(back_populates="items")

    __table_args__ = (UniqueConstraint("watchlist_id", "symbol", name="uq_watchlist_symbol"),)


class PriceAlert(Base):
    __tablename__ = "price_alerts"

    id: Mapped[uuid.UUID] = _pk()
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    symbol: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    condition: Mapped[AlertCondition] = mapped_column(
        SAEnum(AlertCondition, name="alert_condition"), nullable=False
    )
    threshold: Mapped[float] = mapped_column(Numeric(18, 4), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    last_triggered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    notify_payload: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped[User] = relationship(back_populates="alerts")
