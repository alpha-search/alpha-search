"""FastAPI application for Alpha Search REST API."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

from alpha_search.backtest.costs import CostModel
from alpha_search.backtest.engine import BacktestEngine
from alpha_search.backtest.metrics import Metrics
from alpha_search.data.providers import ProviderRegistry

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Pydantic request / response models
# ---------------------------------------------------------------------------


class PricesRequest(BaseModel):
    ticker: str = Field(..., description="Ticker symbol")
    start: str = Field(..., description="Start date YYYY-MM-DD")
    end: str = Field(..., description="End date YYYY-MM-DD")
    source: Optional[str] = Field(default=None, description="Data provider name")


class BacktestRequest(BaseModel):
    ticker: str = Field(..., description="Ticker symbol")
    start: str = Field(..., description="Start date YYYY-MM-DD")
    end: str = Field(..., description="End date YYYY-MM-DD")
    signal_type: str = Field(default="momentum", description="momentum | ma_crossover | z_score")
    initial_capital: float = Field(default=100000.0, description="Starting capital")
    commission: float = Field(default=0.001, description="Commission rate")
    slippage: float = Field(default=0.001, description="Slippage estimate")


class BacktestResponse(BaseModel):
    ticker: str
    total_return: float
    sharpe_ratio: float
    max_drawdown: float
    volatility: float
    num_trades: int
    num_days: int
    equity_curve: Dict[str, float] = Field(default_factory=dict)
    metrics: Dict[str, float] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Alpha Search API",
    description="REST API for quantitative research and backtesting",
    version="0.1.0",
)

# Global registry (created lazily)
_registry: Optional[ProviderRegistry] = None


def _get_registry() -> ProviderRegistry:
    global _registry
    if _registry is None:
        _registry = ProviderRegistry()
    return _registry


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@app.get("/health")
def health_check() -> Dict[str, str]:
    """Health check endpoint."""
    return {"status": "ok", "service": "alpha-search", "version": "0.1.0"}


@app.get("/providers")
def list_providers() -> List[str]:
    """List available data providers."""
    registry = _get_registry()
    return registry.list_providers()


@app.post("/prices")
def get_prices(request: PricesRequest) -> Dict[str, Any]:
    """Fetch OHLCV prices for a ticker."""
    try:
        registry = _get_registry()
        df = registry.get_prices(request.ticker, request.start, request.end, request.source)

        # Convert to serializable format
        records = []
        for idx, row in df.reset_index().iterrows():
            date_val = row.iloc[0]
            if isinstance(date_val, (pd.Timestamp, datetime)):
                date_str = date_val.strftime("%Y-%m-%d")
            else:
                date_str = str(date_val)
            record = {"date": date_str}
            for col in df.columns:
                val = row[col]
                if isinstance(val, (np.floating, float)):
                    record[col] = round(float(val), 6) if not np.isnan(val) else None
                else:
                    record[col] = val
            records.append(record)

        return {
            "ticker": request.ticker,
            "start": request.start,
            "end": request.end,
            "rows": len(df),
            "data": records,
        }
    except Exception as exc:
        logger.error("Prices endpoint error: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/backtest", response_model=BacktestResponse)
def run_backtest(request: BacktestRequest) -> BacktestResponse:
    """Run a backtest for a given ticker and signal type."""
    try:
        # Fetch prices
        registry = _get_registry()
        df = registry.get_prices(request.ticker, request.start, request.end)

        if df.empty or "Close" not in df.columns:
            raise HTTPException(status_code=400, detail="No price data available")

        # Generate signal
        close = df["Close"]
        if request.signal_type == "momentum":
            from alpha_search.signals.technical import momentum as mom

            signal = mom(close)
        elif request.signal_type == "ma_crossover":
            from alpha_search.signals.technical import ma_crossover as mac

            signal = mac(close)
        elif request.signal_type == "z_score":
            from alpha_search.signals.technical import z_score_mean_reversion as zsc

            returns = close.pct_change().fillna(0)
            signal = zsc(returns)
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown signal_type: {request.signal_type}",
            )

        # Run backtest
        cost_model = CostModel(
            commission=request.commission,
            slippage=request.slippage,
        )
        engine = BacktestEngine()
        result = engine.run(df, signal, request.initial_capital, cost_model)

        # Build equity curve dict (sample every ~20 points to keep size manageable)
        eq = result.equity_curve
        step = max(1, len(eq) // 100)
        equity_dict = {
            str(eq.index[i]): round(float(eq.iloc[i]), 2)
            for i in range(0, len(eq), step)
        }

        return BacktestResponse(
            ticker=request.ticker,
            total_return=result.metrics.get("total_return", 0.0),
            sharpe_ratio=result.metrics.get("sharpe_ratio", 0.0),
            max_drawdown=result.metrics.get("max_drawdown", 0.0),
            volatility=result.metrics.get("volatility", 0.0),
            num_trades=result.n_trades,
            num_days=int(result.metrics.get("num_days", 0)),
            equity_curve=equity_dict,
            metrics=result.metrics,
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Backtest endpoint error: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/signals")
def list_signals() -> List[Dict[str, str]]:
    """List available signal types."""
    return [
        {"id": "momentum", "name": "Momentum (Returns-based)", "description": "Cumulative return momentum with sigmoid squashing"},
        {"id": "ma_crossover", "name": "MA Crossover", "description": "Short vs long moving average crossover"},
        {"id": "z_score", "name": "Z-Score Mean Reversion", "description": "Contrarian signal based on return z-scores"},
    ]


def create_app() -> FastAPI:
    """Application factory for Alpha Search FastAPI app."""
    return app
