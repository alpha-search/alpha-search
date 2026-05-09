"""Broker adapter abstract base class for Alpha Search."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict

from alpha_search.core.models import Order, Position


class BrokerAdapter(ABC):
    """Abstract base class for broker / execution adapters.

    Paper trading and live broker implementations should subclass this.
    By default, all implementations should enforce paper-trading safety
    unless explicitly configured for live trading.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Broker name."""
        ...

    @property
    @abstractmethod
    def is_paper(self) -> bool:
        """Return ``True`` if this adapter runs in simulation mode."""
        ...

    @abstractmethod
    def connect(self) -> bool:
        """Establish connection to the broker."""
        ...

    @abstractmethod
    def place_order(self, order: Order) -> Dict[str, Any]:
        """Submit an order to the broker.

        Returns:
            Fill details dictionary with at least ``order_id``, ``status``,
            ``filled_qty``, and ``avg_price``.
        """
        ...

    @abstractmethod
    def get_positions(self) -> Dict[str, Position]:
        """Return current positions keyed by ticker symbol."""
        ...

    @abstractmethod
    def get_account_value(self) -> float:
        """Return total account value (cash + positions)."""
        ...

    @abstractmethod
    def disconnect(self) -> None:
        """Close the broker connection."""
        ...

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} name={self.name!r} paper={self.is_paper}>"
