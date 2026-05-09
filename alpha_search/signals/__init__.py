"""Signal generation module for Alpha Search."""

from alpha_search.signals.base import Signal as SignalABC, CompositeSignal, compose_and, compose_or
from alpha_search.signals.technical import (
    momentum,
    ma_crossover,
    z_score_mean_reversion,
    rsi,
    bollinger_band_position,
)
from alpha_search.signals.ensemble import ensemble, voting, conjunction

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
