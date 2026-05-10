"""Strategy engines for Alpha Search Global Multi-Asset Opportunity Discovery.

Implements three quantitative scanning strategies that work across any
asset class — US equities, Indian equities, crypto, forex, and commodities:

* **Momentum** — trend-following using RSI, MACD, ADX and volume confirmation.
* **Mean Reversion** — counter-trend signals via z-score, Bollinger Bands and RSI extremes.
* **Statistical Arbitrage** — pair-trading opportunities from correlation and cointegration.

All functions accept ``pandas.DataFrame`` price panels (tickers as columns,
dates as index) and return scored ``pandas.DataFrame`` results.

The strategy logic is market-agnostic and works for any price DataFrame
regardless of the underlying asset class or market.
"""

from __future__ import annotations

import logging
from itertools import combinations
from typing import Optional, Tuple

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

try:
    from scipy import stats
except ImportError:  # pragma: no cover
    stats = None  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------

def _clamp(val: float, lo: float = 0.0, hi: float = 1.0) -> float:
    """Clamp *val* to ``[lo, hi]``."""
    return max(lo, min(hi, val))


def _rsi(series: pd.Series, period: int = 14) -> pd.Series:
    """Compute the Relative Strength Index (RSI) for a price series.

    Parameters
    ----------
    series : pandas.Series
        Price series (typically closing prices).
    period : int
        Look-back window (default 14).

    Returns
    -------
    pandas.Series
        RSI values in ``[0, 100]``.
    """
    delta = series.diff()
    gain = delta.clip(lower=0.0)
    loss = (-delta).clip(lower=0.0)

    avg_gain = gain.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()

    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100.0 - (100.0 / (1.0 + rs))
    return rsi.fillna(50.0)


def _macd(series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.DataFrame:
    """Compute MACD line, signal line and histogram.

    Returns a DataFrame with columns ``macd``, ``signal``, ``histogram``.
    """
    ema_fast = series.ewm(span=fast, adjust=False).mean()
    ema_slow = series.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line
    return pd.DataFrame({
        "macd": macd_line,
        "signal": signal_line,
        "histogram": histogram,
    })


def _adx(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    """Compute Average Directional Index (ADX) from HLC series.

    Uses the classic Wilder smoothing approach.  If *high* and *low* are
    identical (e.g. from close-only data), a simplified ADX based on
    absolute returns is used as a fallback.
    """
    if high.equals(close) and low.equals(close):
        # Close-only data — simplified ADX proxy
        returns = close.pct_change().abs()
        adx = returns.rolling(window=period, min_periods=period).mean() * 100.0
        return adx.fillna(0.0)

    # True Range
    tr1 = high - low
    tr2 = (high - close.shift(1)).abs()
    tr3 = (low - close.shift(1)).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

    # +DM / -DM
    up_move = high - high.shift(1)
    down_move = low.shift(1) - low
    plus_dm = ((up_move > down_move) & (up_move > 0)).astype(float) * up_move
    minus_dm = ((down_move > up_move) & (down_move > 0)).astype(float) * down_move

    atr = tr.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()
    plus_di = 100.0 * plus_dm.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean() / atr
    minus_di = 100.0 * minus_dm.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean() / atr

    dx = 100.0 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    adx = dx.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()
    return adx.fillna(0.0)


def _bollinger_bands(series: pd.Series, period: int = 20, num_std: float = 2.0) -> pd.DataFrame:
    """Compute Bollinger Bands and %B position.

    Returns a DataFrame with columns ``upper``, ``middle``, ``lower``, ``percent_b``.
    """
    middle = series.rolling(window=period, min_periods=period).mean()
    std = series.rolling(window=period, min_periods=period).std()
    upper = middle + num_std * std
    lower = middle - num_std * std
    band_width = upper - lower

    percent_b = np.where(
        band_width != 0,
        (series - lower) / band_width,
        0.5,
    )
    return pd.DataFrame({
        "upper": upper,
        "middle": middle,
        "lower": lower,
        "percent_b": percent_b,
    })


def _returns(prices: pd.Series, days: int) -> float:
    """Return the *days*-period total return for the latest available window."""
    if len(prices) < days + 1:
        return 0.0
    return (prices.iloc[-1] / prices.iloc[-(days + 1)]) - 1.0


# ---------------------------------------------------------------------------
# 1. Momentum Scan
# ---------------------------------------------------------------------------

def momentum_scan(
    prices_df: pd.DataFrame,
    volume_df: Optional[pd.DataFrame] = None,
    min_adx: float = 25.0,
    min_volume_ratio: float = 1.5,
) -> pd.DataFrame:
    """Scan for momentum opportunities.

    For each ticker in *prices_df*:

    1. Compute 5-day, 10-day and 20-day returns.
    2. Compute RSI(14).
    3. Compute MACD histogram.
    4. Compute ADX(14) — simplified proxy when H/L data unavailable.
    5. Check volume ratio vs 20-day average (if *volume_df* provided).
    6. Combine into a composite momentum score.

    Parameters
    ----------
    prices_df : pandas.DataFrame
        Closing prices — index = datetime, columns = tickers.
    volume_df : pandas.DataFrame, optional
        Volume data matching *prices_df* shape.
    min_adx : float
        Minimum ADX for a strong-trend filter (default 25).
    min_volume_ratio : float
        Minimum volume spike ratio for confirmation (default 1.5).

    Returns
    -------
    pandas.DataFrame
        Columns: ``ticker``, ``momentum_score``, ``signal_direction``,
        ``adx``, ``volume_ratio``, ``returns_20d``.
    """
    if prices_df is None or prices_df.empty:
        return pd.DataFrame(
            columns=["ticker", "momentum_score", "signal_direction",
                     "adx", "volume_ratio", "returns_20d"]
        )

    results: list[dict] = []

    for ticker in prices_df.columns:
        prices = prices_df[ticker].dropna()
        if len(prices) < 22:
            continue

        # Multi-period returns
        _ = _returns(prices, 5)  # noqa: F841
        _ = _returns(prices, 10)  # noqa: F841
        r20 = _returns(prices, 20)

        # RSI
        rsi = _rsi(prices, period=14)
        rsi_latest = rsi.iloc[-1] if len(rsi) > 0 else 50.0

        # MACD histogram
        macd_df = _macd(prices)
        macd_hist = macd_df["histogram"].iloc[-1] if len(macd_df) > 0 else 0.0

        # ADX — use close-only fallback
        adx_series = _adx(prices, prices, prices, period=14)
        adx_latest = adx_series.iloc[-1] if len(adx_series) > 0 else 0.0

        # Volume ratio
        vol_ratio = 1.0
        if volume_df is not None and ticker in volume_df.columns:
            vol = volume_df[ticker].dropna()
            if len(vol) >= 20:
                avg_vol = vol.iloc[-20:].mean()
                latest_vol = vol.iloc[-1]
                if avg_vol > 0:
                    vol_ratio = latest_vol / avg_vol

        # --- Scoring ---
        # Return direction component: [-1, 1] based on 20d return magnitude
        return_score = np.tanh(r20 * 5)  # tanh maps large returns to ±1

        # RSI trend zone: bullish if 50 < RSI < 70, bearish if 30 < RSI < 50
        if 50 <= rsi_latest <= 70:
            rsi_score = (rsi_latest - 50) / 20.0  # 0 → 1
        elif 30 <= rsi_latest < 50:
            rsi_score = (rsi_latest - 50) / 20.0  # -1 → 0
        elif rsi_latest > 70:
            rsi_score = 0.3  # overbought but still momentum
        elif rsi_latest < 30:
            rsi_score = -0.3  # oversold but still has momentum
        else:
            rsi_score = 0.0

        # MACD histogram: positive = bullish momentum, negative = bearish
        macd_score = np.tanh(macd_hist / prices.iloc[-1] * 100)

        # ADX confirmation: > min_adx = strong trend
        adx_score = 1.0 if adx_latest >= min_adx else adx_latest / min_adx

        # Volume confirmation
        vol_score = 1.0 if vol_ratio >= min_volume_ratio else vol_ratio / min_volume_ratio

        # Composite momentum score: weighted average → [0, 1]
        composite = (
            0.30 * abs(return_score) * (1 if return_score > 0 else -1)
            + 0.20 * rsi_score
            + 0.20 * macd_score
            + 0.15 * adx_score
            + 0.15 * vol_score
        )
        # Normalize to [0, 1]
        momentum_score = _clamp((composite + 1.0) / 2.0)

        # Signal direction
        if composite > 0.2:
            signal = "long"
        elif composite < -0.2:
            signal = "short"
        elif momentum_score > 0.4:
            signal = "watch"
        else:
            signal = "avoid"

        results.append({
            "ticker": ticker,
            "momentum_score": round(momentum_score, 4),
            "signal_direction": signal,
            "adx": round(adx_latest, 2),
            "volume_ratio": round(vol_ratio, 2),
            "returns_20d": round(r20 * 100, 2),  # in percent
        })

    return pd.DataFrame(results)


# ---------------------------------------------------------------------------
# 2. Mean Reversion Scan
# ---------------------------------------------------------------------------

def mean_reversion_scan(
    prices_df: pd.DataFrame,
    zscore_threshold: float = 2.0,
) -> pd.DataFrame:
    """Scan for mean-reversion opportunities.

    For each ticker:

    1. Compute z-score vs 20-day rolling mean.
    2. Compute RSI(14) — flag > 70 or < 30.
    3. Compute Bollinger Band position (%B).
    4. Higher score when z-score is extreme AND RSI confirms.

    Parameters
    ----------
    prices_df : pandas.DataFrame
        Closing prices — index = datetime, columns = tickers.
    zscore_threshold : float
        Z-score magnitude considered "extreme" (default 2.0).

    Returns
    -------
    pandas.DataFrame
        Columns: ``ticker``, ``mean_reversion_score``, ``signal_direction``,
        ``zscore``, ``rsi``, ``bb_position``.
    """
    if prices_df is None or prices_df.empty:
        return pd.DataFrame(
            columns=["ticker", "mean_reversion_score", "signal_direction",
                     "zscore", "rsi", "bb_position"]
        )

    results: list[dict] = []

    for ticker in prices_df.columns:
        prices = prices_df[ticker].dropna()
        if len(prices) < 22:
            continue

        # Rolling statistics
        rolling_mean = prices.rolling(window=20, min_periods=20).mean()
        rolling_std = prices.rolling(window=20, min_periods=20).std()

        latest_price = prices.iloc[-1]
        latest_mean = rolling_mean.iloc[-1]
        latest_std = rolling_std.iloc[-1]

        # Z-score
        if latest_std > 0:
            zscore = (latest_price - latest_mean) / latest_std
        else:
            zscore = 0.0

        # RSI
        rsi = _rsi(prices, period=14)
        rsi_latest = rsi.iloc[-1] if len(rsi) > 0 else 50.0

        # Bollinger %B
        bb = _bollinger_bands(prices)
        bb_pos = bb["percent_b"].iloc[-1] if len(bb) > 0 else 0.5

        # --- Scoring ---
        # Z-score extremity: higher magnitude = stronger mean-reversion signal
        zscore_magnitude = abs(zscore)
        zscore_score = _clamp(zscore_magnitude / zscore_threshold) if zscore_threshold > 0 else 0.0

        # RSI confirmation: oversold (< 30) → long signal, overbought (> 70) → short signal
        if rsi_latest < 30:
            rsi_confirm = (30 - rsi_latest) / 30.0  # 0 → 1 as RSI gets lower
            direction = "long"
        elif rsi_latest > 70:
            rsi_confirm = (rsi_latest - 70) / 30.0  # 0 → 1 as RSI gets higher
            direction = "short"
        else:
            rsi_confirm = 0.0
            direction = "watch"

        # Bollinger Band position: near 0 = oversold, near 1 = overbought
        if bb_pos < 0.1:
            bb_confirm = (0.1 - bb_pos) / 0.1
        elif bb_pos > 0.9:
            bb_confirm = (bb_pos - 0.9) / 0.1
        else:
            bb_confirm = 0.0

        # Composite: mean-reversion is strongest when z-score extreme + RSI confirms + BB extreme
        composite = (
            0.40 * zscore_score
            + 0.35 * rsi_confirm
            + 0.25 * bb_confirm
        )
        mr_score = _clamp(composite)

        # Override direction if z-score strongly disagrees with RSI
        if zscore < -zscore_threshold and direction == "short":
            direction = "long"
        elif zscore > zscore_threshold and direction == "long":
            direction = "short"

        if mr_score < 0.2:
            direction = "watch"

        results.append({
            "ticker": ticker,
            "mean_reversion_score": round(mr_score, 4),
            "signal_direction": direction,
            "zscore": round(zscore, 3),
            "rsi": round(rsi_latest, 2),
            "bb_position": round(bb_pos, 4),
        })

    return pd.DataFrame(results)


# ---------------------------------------------------------------------------
# 3. Statistical Arbitrage Scan
# ---------------------------------------------------------------------------

def _adf_pvalue(spread: pd.Series) -> float:
    """Run Augmented Dickey-Fuller test on *spread* and return the p-value.

    A low p-value (< 0.05) suggests the spread is stationary → cointegrated.
    Falls back to correlation-based heuristic when scipy is unavailable.
    """
    if stats is None:
        # scipy not available — use correlation-based heuristic
        clean = spread.dropna()
        if len(clean) < 30:
            return 1.0
        # Simple half-life approximation
        lagged = clean.shift(1).dropna()
        delta = clean.diff().dropna()
        if len(lagged) > 0 and len(delta) > 0:
            rho = np.corrcoef(lagged.values[:len(delta)], delta.values)[0, 1]
            return 1.0 - abs(rho)  # proxy: higher correlation = lower p-value
        return 1.0

    clean = spread.dropna()
    if len(clean) < 30:
        return 1.0  # not enough data
    try:
        adf_stat, pvalue, _, _, critical_values, _ = stats.adfuller(clean, autolag="AIC")
        return float(pvalue)
    except Exception:
        return 1.0


def _hedge_ratio(
    stock_a: pd.Series,
    stock_b: pd.Series,
    estimation_window: int = 252,
) -> Tuple[float, pd.Series]:
    """Estimate hedge ratio via OLS on a training window.

    Beta is estimated on the *first* ``estimation_window`` observations
    only, preventing look-ahead bias.  The residuals are computed on the
    full aligned series using the out-of-sample beta.

    Parameters
    ----------
    stock_a, stock_b :
        Aligned price series (same index).
    estimation_window :
        Number of initial observations for beta estimation
        (default 252 ≈ 1 year).

    Returns
    -------
    float, pd.Series
        Hedge ratio (beta) and spread residuals (a - beta * b).
    """
    aligned = pd.concat([stock_a, stock_b], axis=1).dropna()
    if aligned.shape[0] < 20:
        return 1.0, pd.Series(dtype=float)

    # Training window: first N observations for beta estimation
    n_train = min(estimation_window, aligned.shape[0])
    train_a = aligned.iloc[:n_train, 0].values
    train_b = aligned.iloc[:n_train, 1].values

    # OLS: beta = Cov(a, b) / Var(b)
    b_var = np.var(train_b, ddof=1)
    if b_var == 0 or not np.isfinite(b_var):
        return 1.0, pd.Series(dtype=float)

    covariance = np.cov(train_a, train_b, ddof=1)[0, 1]
    beta = covariance / b_var

    # Residuals on FULL series (out-of-sample for points > n_train)
    full_a = aligned.iloc[:, 0].values
    full_b = aligned.iloc[:, 1].values
    residuals = full_a - beta * full_b
    return float(beta), pd.Series(residuals, index=aligned.index)


def arbitrage_scan(
    prices_df: pd.DataFrame,
    min_correlation: float = 0.7,
    max_pairs: int = 20,
    max_tickers: int = 50,
) -> pd.DataFrame:
    """Scan for statistical arbitrage (pair-trading) opportunities.

    1. Compute correlation matrix for all tickers.
    2. Find pairs with correlation > *min_correlation*.
    3. For each pair, run Engle-Granger cointegration test (ADF on spread).
    4. Calculate spread z-score.
    5. Calculate hedge ratio from OLS: ``stock_a = beta * stock_b + residual``.
    6. Score: ``correlation * cointegration * spread_zscore_magnitude``.

    Parameters
    ----------
    prices_df : pandas.DataFrame
        Closing prices — index = datetime, columns = tickers.
    min_correlation : float
        Minimum Pearson correlation to consider a pair (default 0.7).
    max_pairs : int
        Maximum number of pairs to return, sorted by confidence (default 20).
    max_tickers : int
        Maximum tickers to consider. Pre-filters by variance to keep
        the most volatile (default 50). Prevents O(n²) blow-up on
        large universes like S&P 500.

    Returns
    -------
    pandas.DataFrame
        Columns: ``stock_a``, ``stock_b``, ``correlation``,
        ``cointegration_score``, ``spread_zscore``, ``hedge_ratio``,
        ``confidence_score``.
    """
    if prices_df is None or prices_df.empty:
        return pd.DataFrame(
            columns=["stock_a", "stock_b", "correlation",
                     "cointegration_score", "spread_zscore",
                     "hedge_ratio", "confidence_score"]
        )

    # Validate: check for non-positive prices before log transform
    invalid = (prices_df <= 0).any()
    if invalid.any():
        bad_tickers = invalid[invalid].index.tolist()
        logger.warning(
            "Excluding %d ticker(s) with non-positive prices: %s",
            len(bad_tickers), bad_tickers,
        )
        prices_df = prices_df.drop(columns=bad_tickers)

    # Use log-prices for cointegration (more stable)
    log_prices = np.log(prices_df)
    log_prices = log_prices.dropna(how="all", axis=1).dropna(how="all", axis=0)

    if log_prices.shape[1] < 2:
        return pd.DataFrame(
            columns=["stock_a", "stock_b", "correlation",
                     "cointegration_score", "spread_zscore",
                     "hedge_ratio", "confidence_score"]
        )

    # Pre-filter: keep only top *max_tickers* by return variance.
    # This prevents O(n²) blow-up on large universes (e.g., S&P 500).
    n_cols = log_prices.shape[1]
    if n_cols > max_tickers:
        logger.info(
            "arbitrage_scan: %d tickers exceed max_tickers=%d, "
            "pre-filtering by variance", n_cols, max_tickers,
        )
        variances = log_prices.diff().dropna().var()
        top_tickers = variances.nlargest(max_tickers).index.tolist()
        log_prices = log_prices[top_tickers]

    # Correlation on returns (more meaningful than price correlation)
    returns = log_prices.diff().dropna()
    if returns.shape[0] < 10:
        return pd.DataFrame(
            columns=["stock_a", "stock_b", "correlation",
                     "cointegration_score", "spread_zscore",
                     "hedge_ratio", "confidence_score"]
        )

    corr_matrix = returns.corr()
    tickers = list(corr_matrix.columns)

    candidates: list[dict] = []

    for a, b in combinations(tickers, 2):
        corr = corr_matrix.loc[a, b]
        if corr < min_correlation or np.isnan(corr):
            continue

        # Align log-price series
        pair_data = log_prices[[a, b]].dropna()
        if len(pair_data) < 30:
            continue

        # Hedge ratio via OLS on log-prices
        beta, residuals = _hedge_ratio(pair_data[a], pair_data[b])
        if len(residuals) < 10:
            continue

        # Cointegration test on residuals (spread)
        adf_pvalue = _adf_pvalue(residuals)
        # Convert p-value to score: p < 0.05 → strong cointegration
        coint_score = _clamp(1.0 - (adf_pvalue / 0.20))  # p=0 → 1, p=0.2 → 0

        # Spread z-score
        spread_mean = residuals.mean()
        spread_std = residuals.std()
        if spread_std > 0:
            spread_z = (residuals.iloc[-1] - spread_mean) / spread_std
        else:
            spread_z = 0.0

        # Confidence score: correlation * cointegration * z-score magnitude
        zscore_magnitude = min(abs(spread_z) / 2.0, 1.0)  # normalize |z| > 2 → 1.0
        confidence = _clamp(corr * coint_score * (0.5 + 0.5 * zscore_magnitude))

        candidates.append({
            "stock_a": a,
            "stock_b": b,
            "correlation": round(corr, 4),
            "cointegration_score": round(coint_score, 4),
            "spread_zscore": round(spread_z, 4),
            "hedge_ratio": round(beta, 4),
            "confidence_score": round(confidence, 4),
        })

    # Sort by confidence descending and cap
    df = pd.DataFrame(candidates)
    if df.empty:
        return pd.DataFrame(
            columns=["stock_a", "stock_b", "correlation",
                     "cointegration_score", "spread_zscore",
                     "hedge_ratio", "confidence_score"]
        )

    df = df.sort_values("confidence_score", ascending=False).head(max_pairs)
    return df.reset_index(drop=True)
