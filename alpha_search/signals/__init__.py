"""Signal generation module for Alpha Search."""

from alpha_search.signals.base import CompositeSignal, compose_and, compose_or
from alpha_search.signals.base import Signal as SignalABC
from alpha_search.signals.ensemble import conjunction, ensemble, voting
from alpha_search.signals.technical import (
    bollinger_band_position,
    ma_crossover,
    momentum,
    rsi,
    z_score_mean_reversion,
)

__all__ = [
    "SignalABC",
    "CompositeSignal",
    "compose_and",
    "compose_or",
    "momentum",
    "ma_crossover",
    "z_score_mean_reversion",
    "rsi",
    "bollinger_band_position",
    "ensemble",
    "voting",
    "conjunction",
]
