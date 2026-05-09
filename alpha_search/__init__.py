"""Alpha Search - The Operating System for Quantitative Research."""

from __future__ import annotations

__version__ = "0.2.0"

# Core imports that don't depend on optional deps
from alpha_search.core.errors import QuantOSError

# Lazy imports for heavy/optional modules
try:
    from alpha_search.terminal import Terminal
except ImportError:  # pragma: no cover
    Terminal = None  # type: ignore

try:
    from alpha_search.core.models import OHLCV, SignalData, BacktestResult, Order, Position
except ImportError:  # pragma: no cover
    OHLCV = SignalData = BacktestResult = Order = Position = None  # type: ignore

try:
    from alpha_search.data.providers import ProviderRegistry
except ImportError:  # pragma: no cover
    ProviderRegistry = None  # type: ignore

try:
    from alpha_search.backtest.engine import BacktestEngine
    from alpha_search.backtest.metrics import Metrics
    from alpha_search.backtest.costs import CostModel
    from alpha_search.backtest.walk_forward import WalkForwardValidator
except ImportError:  # pragma: no cover
    BacktestEngine = Metrics = CostModel = WalkForwardValidator = None  # type: ignore

try:
    from alpha_search.execution.paper import PaperTrader
    from alpha_search.execution.risk_controls import RiskManager
except ImportError:  # pragma: no cover
    PaperTrader = RiskManager = None  # type: ignore

try:
    from alpha_search.portfolio.construction import Portfolio
except ImportError:  # pragma: no cover
    Portfolio = None  # type: ignore

try:
    from alpha_search.opportunities.models import StockOpportunity, PairOpportunity
    from alpha_search.opportunities.scanner import StockOpportunityScanner
    from alpha_search.opportunities.scoring import FinalScore
except ImportError:  # pragma: no cover
    StockOpportunity = PairOpportunity = StockOpportunityScanner = FinalScore = None  # type: ignore

try:
    from alpha_search.memory.models import MemoryRecord, StrategyMemory, HandoffRecord, RiskDecision
    from alpha_search.memory.store import MemoryStore
    from alpha_search.memory.journal import AgentJournal
    from alpha_search.memory.retrieval import MemoryRetriever
except ImportError:  # pragma: no cover
    MemoryRecord = StrategyMemory = HandoffRecord = RiskDecision = None  # type: ignore
    MemoryStore = AgentJournal = MemoryRetriever = None  # type: ignore

__all__ = [
    "Terminal", "OHLCV", "SignalData", "BacktestResult", "Order", "Position",
    "ProviderRegistry", "BacktestEngine", "Metrics", "CostModel",
    "WalkForwardValidator", "PaperTrader", "RiskManager", "Portfolio",
    "StockOpportunity", "PairOpportunity", "StockOpportunityScanner", "FinalScore",
    "MemoryRecord", "StrategyMemory", "HandoffRecord", "RiskDecision",
    "MemoryStore", "AgentJournal", "MemoryRetriever",
    "__version__",
]
