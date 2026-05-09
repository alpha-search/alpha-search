"""Tests for the Terminal orchestrator."""



class TestTerminalImports:
    """Ensure the top-level package and Terminal class are importable."""

    def test_terminal_imports(self) -> None:
        """alpha_search and Terminal can be imported without error."""
        import alpha_search
        from alpha_search import Terminal

        assert alpha_search.__version__ is not None
        assert Terminal is not None


class TestTerminalCreation:
    """Smoke tests for constructing a Terminal instance."""

    def test_terminal_creation(self) -> None:
        """A Terminal can be instantiated with a ticker universe."""
        from alpha_search import Terminal

        terminal = Terminal(universe=["AAPL", "MSFT", "BTC-USD"])

        assert terminal.universe == ["AAPL", "MSFT", "BTC-USD"]
        assert hasattr(terminal, "data")
        assert hasattr(terminal, "signals")
        assert hasattr(terminal, "backtest")

    def test_terminal_empty_universe(self) -> None:
        """A Terminal accepts an empty universe (no tickers)."""
        from alpha_search import Terminal

        terminal = Terminal(universe=[])
        assert terminal.universe == []
