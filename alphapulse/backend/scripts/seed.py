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
                "see asymmetric upside heading into FY27. The market is still valuing "
                "Apple as a hardware company on a replacement cycle, while the reality "
                "is a high-margin, recurring-revenue platform with 2.2B active devices "
                "and pricing power that few companies on earth can match.\n\n"
                "### The Services Engine\n\nGross margin expansion in Services (now "
                "~71%) is the single most underappreciated driver of the story. The "
                "App Store, advertising, iCloud, Apple Music, and the fast-growing "
                "Apple Pay/financial-services stack now compound at a mid-teens rate. "
                "We model 8% consolidated revenue CAGR through FY27, with the Services "
                "mix shift pushing blended gross margin from ~45% toward ~48% and "
                "operating leverage driving EPS growth into the low-to-mid teens.\n\n"
                "### Capital Returns\n\nApple has retired roughly a third of its shares "
                "outstanding over the past decade. With ~$48B of net cash and ~$95B of "
                "annual free cash flow, the buyback is a structural tailwind to EPS "
                "worth an estimated 3-4% per year on its own — before any operational "
                "growth. Management has signalled a long-term intent to reach net-cash "
                "neutral, implying years of continued repurchases.\n\n"
                "### Valuation\n\nAt the current multiple the market is pricing in "
                "near-zero terminal growth for Services, which we view as far too "
                "conservative. A sum-of-the-parts that values Services at a software "
                "multiple and Hardware at a consumer-durables multiple yields a fair "
                "value ~22% above the current price.\n\n"
                "### Risks\n\nRegulatory pressure on the App Store (DMA in the EU, the "
                "DOJ suit in the US) and China demand softness are the key bear points. "
                "A forced reduction in App Store take rates would dent Services margin, "
                "and a prolonged China share-loss to domestic OEMs would pressure the "
                "iPhone line. We size these as manageable rather than thesis-breaking; "
                "balance-sheet strength ($AAPL holds ~$48B net cash) cushions any "
                "near-term shock and funds continued capital returns through the cycle."
                "\n\nWe rate $AAPL a Buy with a 12-month price target implying ~22% "
                "upside from current levels."
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
