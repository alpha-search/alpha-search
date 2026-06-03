"""Contributor CMS routes.

Readers list and read articles (premium bodies are withheld with a free preview
for non-entitled viewers). Contributors create, update, and publish their own
articles, attaching ticker tags ($AAPL) and required disclosures.
"""
from __future__ import annotations

import re
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from slugify import slugify
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_user, get_optional_user, require_role
from app.db.models import (
    Article,
    ArticleStatus,
    ArticleTicker,
    Ticker,
    User,
    UserRole,
)
from app.db.session import get_db
from app.middleware.paywall import can_view_article
from app.schemas import (
    ArticleCreate,
    ArticleDetail,
    ArticleSummary,
    ArticleTickerTag,
    ArticleUpdate,
)

router = APIRouter(prefix="/articles", tags=["articles"])

_PREVIEW_CHARS = 600
_TICKER_RE = re.compile(r"\$([A-Z]{1,6})")


async def _resolve_ticker(db: AsyncSession, symbol: str) -> Ticker:
    """Fetch a ticker row, lazily creating a stub so $TAGs always resolve."""
    symbol = symbol.upper()
    result = await db.execute(select(Ticker).where(Ticker.symbol == symbol))
    ticker = result.scalar_one_or_none()
    if ticker is None:
        ticker = Ticker(symbol=symbol, company_name=f"{symbol} Holdings Inc.")
        db.add(ticker)
        await db.flush()
    return ticker


async def _sync_ticker_links(
    db: AsyncSession, article: Article, tags: list[ArticleTickerTag]
) -> None:
    article.ticker_links.clear()
    await db.flush()
    seen: set[str] = set()
    for tag in tags:
        sym = tag.symbol.upper().lstrip("$")
        if sym in seen:
            continue
        seen.add(sym)
        ticker = await _resolve_ticker(db, sym)
        db.add(
            ArticleTicker(
                article_id=article.id, ticker_id=ticker.id, sentiment=tag.sentiment
            )
        )


def _to_summary(article: Article) -> ArticleSummary:
    return ArticleSummary.model_validate(article)


def _to_detail(article: Article, *, locked: bool) -> ArticleDetail:
    tickers = [
        ArticleTickerTag(symbol=link.ticker.symbol, sentiment=link.sentiment)  # type: ignore[arg-type]
        for link in article.ticker_links
    ]
    detail = ArticleDetail.model_validate(article)
    detail.tickers = tickers
    detail.is_locked = locked
    if locked:
        # Withhold the paid body, returning only the free preview.
        detail.body_markdown = article.free_preview or article.body_markdown[:_PREVIEW_CHARS]
    return detail


@router.get("", response_model=list[ArticleSummary])
async def list_articles(
    db: AsyncSession = Depends(get_db),
    symbol: str | None = Query(default=None, description="Filter by ticker tag"),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> list[ArticleSummary]:
    stmt = (
        select(Article)
        .options(selectinload(Article.author))
        .where(Article.status == ArticleStatus.PUBLISHED)
        .order_by(Article.published_at.desc())
        .limit(limit)
        .offset(offset)
    )
    if symbol:
        stmt = stmt.join(Article.ticker_links).join(ArticleTicker.ticker).where(
            Ticker.symbol == symbol.upper()
        )
    result = await db.execute(stmt)
    return [_to_summary(a) for a in result.scalars().unique().all()]


@router.get("/{slug}", response_model=ArticleDetail)
async def get_article(
    slug: str,
    db: AsyncSession = Depends(get_db),
    user: User | None = Depends(get_optional_user),
) -> ArticleDetail:
    result = await db.execute(
        select(Article)
        .options(
            selectinload(Article.author),
            selectinload(Article.ticker_links).selectinload(ArticleTicker.ticker),
        )
        .where(Article.slug == slug)
    )
    article = result.scalar_one_or_none()
    if article is None or article.status != ArticleStatus.PUBLISHED:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Article not found")

    await db.execute(
        Article.__table__.update()
        .where(Article.id == article.id)
        .values(view_count=Article.view_count + 1)
    )
    locked = not can_view_article(user, article.access_level)
    return _to_detail(article, locked=locked)


@router.post("", response_model=ArticleDetail, status_code=status.HTTP_201_CREATED)
async def create_article(
    payload: ArticleCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(UserRole.CONTRIBUTOR)),
) -> ArticleDetail:
    slug = f"{slugify(payload.title)}-{uuid.uuid4().hex[:6]}"
    # Auto-extract any $TICKERS mentioned in the body in addition to explicit tags.
    body_symbols = {m.group(1) for m in _TICKER_RE.finditer(payload.body_markdown)}
    explicit = {t.symbol.upper().lstrip("$") for t in payload.tickers}
    merged = list(payload.tickers) + [
        ArticleTickerTag(symbol=s) for s in body_symbols - explicit
    ]

    article = Article(
        slug=slug,
        title=payload.title,
        summary=payload.summary,
        body_markdown=payload.body_markdown,
        free_preview=payload.body_markdown[:_PREVIEW_CHARS],
        disclosure=payload.disclosure,
        cover_image_url=payload.cover_image_url,
        access_level=payload.access_level,
        status=ArticleStatus.DRAFT,
        author_id=user.id,
        tags=payload.tags,
    )
    db.add(article)
    await db.flush()
    await _sync_ticker_links(db, article, merged)
    await db.refresh(article, attribute_names=["ticker_links", "author"])
    return _to_detail(article, locked=False)


@router.patch("/{article_id}", response_model=ArticleDetail)
async def update_article(
    article_id: uuid.UUID,
    payload: ArticleUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ArticleDetail:
    result = await db.execute(
        select(Article)
        .options(
            selectinload(Article.author),
            selectinload(Article.ticker_links).selectinload(ArticleTicker.ticker),
        )
        .where(Article.id == article_id)
    )
    article = result.scalar_one_or_none()
    if article is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Article not found")
    if article.author_id != user.id and user.role != UserRole.ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your article")

    data = payload.model_dump(exclude_unset=True)
    if "body_markdown" in data:
        article.free_preview = data["body_markdown"][:_PREVIEW_CHARS]
    if data.get("status") == ArticleStatus.PUBLISHED and article.published_at is None:
        article.published_at = func.now()
    tickers = data.pop("tickers", None)
    for field, value in data.items():
        setattr(article, field, value)
    if tickers is not None:
        await _sync_ticker_links(
            db, article, [ArticleTickerTag(**t) for t in tickers]
        )
    await db.flush()
    await db.refresh(article, attribute_names=["ticker_links", "author"])
    return _to_detail(article, locked=False)
