"""Signal ensemble / combination utilities (vectorized)."""

from __future__ import annotations

import logging
from typing import List, Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def ensemble(
    signals: List[pd.Series],
    weights: Optional[List[float]] = None,
) -> pd.Series:
    """Weighted combination of multiple signals.

    All signals are aligned to the inner join of their indices before
    weighting. Missing values are forward-filled then back-filled.

    Args:
        signals: List of signal Series.
        weights: Optional list of weights (must sum to > 0). If ``None``,
            equal weights are used.

    Returns:
        Combined signal Series.
    """
    if not signals:
        raise ValueError("signals list is empty")

    # Equal weights if not provided
    if weights is None:
        weights = [1.0 / len(signals)] * len(signals)

    if len(weights) != len(signals):
        raise ValueError(
            f"Length mismatch: {len(signals)} signals but {len(weights)} weights"
        )

    if sum(weights) <= 0:
        raise ValueError("weights must sum to a positive value")

    # Start with the first signal's index
    combined = signals[0].copy()
    for s in signals[1:]:
        combined = combined.align(s, join="outer")[0]

    # Weighted sum aligned to combined index
    result = pd.Series(0.0, index=combined.index, name="ensemble")
    total_weight = sum(weights)

    for sig, w in zip(signals, weights):
        aligned = sig.reindex(result.index)
        aligned = aligned.ffill().bfill().fillna(0.0)
        result += aligned * (w / total_weight)

    return result


def voting(
    signals: List[pd.Series],
    threshold: int = 1,
) -> pd.Series:
    """Majority-vote combination of boolean-like signals.

    A day is a ``1.0`` (buy) if at least *threshold* signals are
    positive, else ``0.0``.

    Args:
        signals: List of signal Series (treated as boolean after > 0.5).
        threshold: Minimum number of signals that must agree.

    Returns:
        pd.Series of ``0.0`` / ``1.0``.
    """
    if not signals:
        raise ValueError("signals list is empty")

    # Build common index
    combined_idx = signals[0].index
    for s in signals[1:]:
        combined_idx = combined_idx.union(s.index)

    # Count positive signals per day
    vote_count = pd.Series(0, index=combined_idx, dtype=int)
    for sig in signals:
        aligned = sig.reindex(combined_idx).ffill().bfill().fillna(0.0)
        vote_count += (aligned > 0.5).astype(int)

    result = (vote_count >= threshold).astype(float)
    result.name = "voting"
    return result


def conjunction(signals: List[pd.Series]) -> pd.Series:
    """Logical AND of all signals (all must agree).

    Returns ``1.0`` only on days where *every* signal is positive.

    Args:
        signals: List of signal Series.

    Returns:
        pd.Series of ``0.0`` / ``1.0``.
    """
    if not signals:
        raise ValueError("signals list is empty")

    # Build common index
    combined_idx = signals[0].index
    for s in signals[1:]:
        combined_idx = combined_idx.union(s.index)

    # All must be > 0.5
    result = pd.Series(1.0, index=combined_idx, name="conjunction")
    for sig in signals:
        aligned = sig.reindex(combined_idx).ffill().bfill().fillna(0.0)
        result *= (aligned > 0.5).astype(float)

    return result
