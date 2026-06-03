"""AlphaPulse API application factory and ASGI entrypoint."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import ORJSONResponse

from app.api.routes import (
    articles,
    auth,
    metrics,
    subscriptions,
    tickers,
    watchlists,
)
from app.core.config import settings
from app.core.redis_client import close_redis, get_redis
from app.middleware.paywall import PaywallMiddleware

logging.basicConfig(level=logging.INFO if not settings.DEBUG else logging.DEBUG)
logger = logging.getLogger("alphapulse")


@asynccontextmanager
async def lifespan(app: FastAPI):
    redis = get_redis()
    await redis.ping()
    logger.info("AlphaPulse API started in %s mode", settings.ENVIRONMENT)
    yield
    await close_redis()
    logger.info("AlphaPulse API shut down")


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.PROJECT_NAME,
        version="0.1.0",
        default_response_class=ORJSONResponse,
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    # Paywall runs after CORS so preflight requests are never blocked.
    app.add_middleware(PaywallMiddleware)

    prefix = settings.API_V1_PREFIX
    app.include_router(auth.router, prefix=prefix)
    app.include_router(tickers.router, prefix=prefix)
    app.include_router(metrics.router, prefix=prefix)
    app.include_router(articles.router, prefix=prefix)
    app.include_router(watchlists.router, prefix=prefix)
    app.include_router(subscriptions.router, prefix=prefix)

    @app.get("/health", tags=["system"])
    async def health() -> dict:
        await get_redis().ping()
        return {"status": "ok", "service": settings.PROJECT_NAME}

    return app


app = create_app()
