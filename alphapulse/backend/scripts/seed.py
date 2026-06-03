"""Seed the database with demo users, tickers, and published articles.

Usage: ``python -m scripts.seed``. Idempotent — safe to re-run.

Demo credentials:
  contributor@alphapulse.io / password123   (contributor, PRO tier)
  reader@alphapulse.io      / password123   (reader, FREE tier)
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from sqlalchemy import select

from app.core.security import hash_password
from app.db.models import (
    Article,
    ArticleAccess,
    ArticleStatus,
    ArticleTicker,
    Subscription,
    SubscriptionStatus,
    SubscriptionTier,
    Ticker,
    User,
    UserRole,
)
from app.db.session import SessionLocal

_TICKERS = [
    ("AAPL", "Apple Inc.", "Technology", "Consumer Electronics"),
    ("MSFT", "Microsoft Corporation", "Technology", "Software"),
    ("NVDA", "NVIDIA Corporation", "Technology", "Semiconductors"),
    ("TSLA", "Tesla, Inc.", "Consumer Cyclical", "Auto Manufacturers"),
]


async def _get_or_create_user(db, email, name, role, tier) -> User:
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if user:
        return user
    user = User(
        email=email,
        display_name=name,
        hashed_password=hash_password("password123"),
        role=role,
    )
    db.add(user)
    await db.flush()
    db.add(
        Subscription(
            user_id=user.id,
            tier=tier,
            status=SubscriptionStatus.ACTIVE,
            current_period_end=datetime(2030, 1, 1, tzinfo=timezone.utc),
        )
    )
    await db.flush()
    return user


async def main() -> None:
    async with SessionLocal() as db:
        contributor = await _get_or_create_user(
            db, "contributor@alphapulse.io", "Jane Analyst",
            UserRole.CONTRIBUTOR, SubscriptionTier.PRO,
        )
        await _get_or_create_user(
            db, "reader@alphapulse.io", "Bob Reader",
            UserRole.READER, SubscriptionTier.FREE,
        )

        ticker_by_symbol: dict[str, Ticker] = {}
        for symbol, company, sector, industry in _TICKERS:
            result = await db.execute(select(Ticker).where(Ticker.symbol == symbol))
            ticker = result.scalar_one_or_none()
            if ticker is None:
                ticker = Ticker(
                    symbol=symbol, company_name=company, sector=sector,
                    industry=industry, exchange="NASDAQ",
                )
                db.add(ticker)
                await db.flush()
            ticker_by_symbol[symbol] = ticker

        result = await db.execute(select(Article).where(Article.slug == "apple-q4-deep-dive"))
        if result.scalar_one_or_none() is None:
            body = (
                "## Thesis\n\nApple's services flywheel continues to compound, and "
                "with $AAPL trading at a forward multiple below its 5-year average we "
                "see asymmetric upside.\n\n### Margins\n\nGross margin expansion in "
                "Services (now ~71%) is the single most underappreciated driver. We "
                "model 8% revenue CAGR through FY27 with operating leverage pushing "
                "EPS growth into the low-teens.\n\n### Risks\n\nRegulatory pressure on "
                "the App Store and China demand softness are the key bear points, but "
                "balance-sheet strength ($AAPL holds ~$48B cash) cushions any shock.\n\n"
                "We rate $AAPL a Buy with a 12-month target implying 22% upside."
            )
            article = Article(
                slug="apple-q4-deep-dive",
                title="Apple: The Services Flywheel Is Just Getting Started",
                summary="Why we think AAPL's services-led margin story is mispriced heading into FY27.",
                body_markdown=body,
                free_preview=body[:600],
                disclosure="I/we have a beneficial long position in the shares of AAPL. I wrote this article myself, and it expresses my own opinions. I am not receiving compensation for it.",
                access_level=ArticleAccess.PREMIUM,
                status=ArticleStatus.PUBLISHED,
                author_id=contributor.id,
                tags=["large-cap", "technology", "long-idea"],
                published_at=datetime.now(timezone.utc),
            )
            db.add(article)
            await db.flush()
            db.add(ArticleTicker(article_id=article.id, ticker_id=ticker_by_symbol["AAPL"].id, sentiment="bullish"))

        await db.commit()
    print("✓ seed complete — login as contributor@alphapulse.io / password123")


if __name__ == "__main__":
    asyncio.run(main())
