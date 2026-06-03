"""Pydantic v2 request/response models for the AlphaPulse API."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.db.models import (
    AlertCondition,
    ArticleAccess,
    ArticleStatus,
    SubscriptionStatus,
    SubscriptionTier,
    UserRole,
)


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# --- Auth ------------------------------------------------------------------ #
class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    display_name: str = Field(min_length=1, max_length=120)


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserOut(ORMModel):
    id: uuid.UUID
    email: EmailStr
    display_name: str
    role: UserRole
    avatar_url: str | None = None
    created_at: datetime


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: Literal["bearer"] = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


# --- Subscriptions --------------------------------------------------------- #
class SubscriptionOut(ORMModel):
    tier: SubscriptionTier
    status: SubscriptionStatus
    current_period_end: datetime | None = None
    cancel_at_period_end: bool = False


class CheckoutRequest(BaseModel):
    tier: Literal["premium", "pro"]
    success_url: str
    cancel_url: str


class CheckoutSession(BaseModel):
    checkout_url: str
    session_id: str


# --- Tickers --------------------------------------------------------------- #
class TickerProfile(BaseModel):
    symbol: str
    company_name: str
    exchange: str | None = None
    sector: str | None = None
    industry: str | None = None
    logo_url: str | None = None
    description: str | None = None


class Quote(BaseModel):
    symbol: str
    price: float
    change: float
    change_pct: float
    day_high: float
    day_low: float
    volume: int
    market_cap: float | None = None
    updated_at: datetime


class CandleBar(BaseModel):
    time: int  # unix seconds, the format TradingView Lightweight Charts expects
    open: float
    high: float
    low: float
    close: float
    volume: int


class FinancialStatementRow(BaseModel):
    label: str
    values: dict[str, float | None]  # period -> value, e.g. {"2023": 383285000000}


class FinancialStatement(BaseModel):
    statement: Literal["income", "balance", "cash_flow"]
    currency: str = "USD"
    periods: list[str]
    rows: list[FinancialStatementRow]


class EarningsMetric(BaseModel):
    date: str
    eps_estimate: float | None = None
    eps_actual: float | None = None
    revenue_estimate: float | None = None
    revenue_actual: float | None = None


class DividendMetric(BaseModel):
    ex_date: str
    payment_date: str | None = None
    amount: float
    yield_pct: float | None = None


# --- Articles -------------------------------------------------------------- #
class ArticleTickerTag(BaseModel):
    symbol: str
    sentiment: Literal["bullish", "bearish", "neutral"] | None = None


class ArticleCreate(BaseModel):
    title: str = Field(min_length=4, max_length=300)
    summary: str = Field(min_length=10, max_length=1000)
    body_markdown: str = Field(min_length=1)
    disclosure: str = Field(min_length=1, description="Required financial disclosure")
    access_level: ArticleAccess = ArticleAccess.PUBLIC
    cover_image_url: str | None = None
    tickers: list[ArticleTickerTag] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)


class ArticleUpdate(BaseModel):
    title: str | None = None
    summary: str | None = None
    body_markdown: str | None = None
    disclosure: str | None = None
    access_level: ArticleAccess | None = None
    status: ArticleStatus | None = None
    cover_image_url: str | None = None
    tickers: list[ArticleTickerTag] | None = None
    tags: list[str] | None = None


class ArticleSummary(ORMModel):
    id: uuid.UUID
    slug: str
    title: str
    summary: str
    access_level: ArticleAccess
    status: ArticleStatus
    cover_image_url: str | None = None
    tags: list[str]
    published_at: datetime | None = None
    author: UserOut


class ArticleDetail(ArticleSummary):
    body_markdown: str
    disclosure: str
    free_preview: str
    # Populated by the route after validation (ORM exposes `ticker_links`).
    tickers: list[ArticleTickerTag] = Field(default_factory=list)
    # True when the body was withheld behind the paywall for this viewer.
    is_locked: bool = False


# --- Watchlists & alerts --------------------------------------------------- #
class WatchlistItemOut(ORMModel):
    id: uuid.UUID
    symbol: str
    added_at: datetime


class WatchlistOut(ORMModel):
    id: uuid.UUID
    name: str
    items: list[WatchlistItemOut]


class WatchlistItemCreate(BaseModel):
    symbol: str = Field(min_length=1, max_length=16)


class AlertCreate(BaseModel):
    symbol: str = Field(min_length=1, max_length=16)
    condition: AlertCondition
    threshold: float


class AlertOut(ORMModel):
    id: uuid.UUID
    symbol: str
    condition: AlertCondition
    threshold: float
    is_active: bool
    last_triggered_at: datetime | None = None
