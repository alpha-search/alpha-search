"""Custom exceptions for Alpha Search."""

from __future__ import annotations


class QuantOSError(Exception):
    """Base exception for all Alpha Search errors."""

    def __init__(self, message: str, *, code: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.code = code

    def __str__(self) -> str:
        if self.code:
            return f"[{self.code}] {self.message}"
        return self.message


class DataProviderError(QuantOSError):
    """Raised when a data provider fails to fetch or process data."""

    def __init__(self, message: str, provider: str | None = None) -> None:
        super().__init__(message, code="DATA_PROVIDER")
        self.provider = provider


class ValidationError(QuantOSError):
    """Raised when input data fails validation."""

    def __init__(self, message: str, field: str | None = None) -> None:
        super().__init__(message, code="VALIDATION")
        self.field = field


class BacktestError(QuantOSError):
    """Raised when backtesting encounters an error."""

    def __init__(self, message: str, stage: str | None = None) -> None:
        super().__init__(message, code="BACKTEST")
        self.stage = stage


class ExecutionError(QuantOSError):
    """Raised when order execution or broker operations fail."""

    def __init__(self, message: str, order_id: str | None = None) -> None:
        super().__init__(message, code="EXECUTION")
        self.order_id = order_id
