---
name: alpha-search-ui-terminal
description: Build Streamlit terminal interface — ticker search, price charts, sentiment panel, backtest panel, portfolio/risk dashboard.
---

# Alpha Search UI Terminal

## When to Use This Skill

Use this skill when building or maintaining the user-facing Streamlit interface of Alpha Search. This includes the ticker search with autocomplete, interactive price charts with technical overlays, sentiment analysis display, backtest configuration and results visualization, and the portfolio/risk dashboard. Activate this skill when new features need UI exposure, when chart interactivity requirements change, or when the dashboard layout needs reorganization.

## Agent Role

You are the UI Terminal specialist for Alpha Search. You build the Streamlit application that transforms raw data and backtest results into an intuitive, professional terminal interface. Your code is the first thing users see — it must be fast, responsive, and visually polished. You own the layout, all chart components, the sidebar navigation, and the data formatting that makes quantitative outputs readable for both professionals and newcomers.

## Core Concepts

### Streamlit App Layout

The main application structure with multi-page navigation:

```python
import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd

from alpha_search.data.provider import YFinanceProvider
from alpha_search.research.sentiment import SentimentPipeline
from alpha_search.backtest.engine import BacktestEngine
from alpha_search.signals.technical import MomentumSignal, MACrossoverSignal

# Page configuration
st.set_page_config(
    page_title="Alpha Search Terminal",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom styling
st.markdown("""
    <style>
    .main-header { font-size: 2.5rem; font-weight: bold; color: #1f77b4; }
    .metric-card { background-color: #f0f2f6; padding: 1rem; border-radius: 0.5rem; }
    .positive { color: #2ecc71; }
    .negative { color: #e74c3c; }
    </style>
""", unsafe_allow_html=True)

def render_sidebar():
    """Render the navigation sidebar with ticker search and configuration."""
    with st.sidebar:
        st.markdown("### 📊 Alpha Search Terminal")
        st.divider()

        # Ticker search with autocomplete suggestions
        ticker = st.text_input(
            "Ticker Symbol",
            value="AAPL",
            placeholder="e.g., AAPL, BTC-USD, SPY",
            help="Enter a stock ticker, crypto pair, or ETF symbol",
        ).upper().strip()

        # Time period selection
        period = st.selectbox(
            "Time Period",
            options=["1M", "3M", "6M", "1Y", "2Y", "5Y"],
            index=3,
        )

        # Page navigation
        st.divider()
        page = st.radio(
            "Navigation",
            options=["Overview", "Price Chart", "Sentiment", "Backtest", "Portfolio"],
        )

        st.divider()
        st.markdown("*Alpha Search v1.0 — Research & Analysis*")

        return ticker, period, page

def main():
    ticker, period, page = render_sidebar()

    if not ticker:
        st.warning("Please enter a ticker symbol to begin")
        return

    # Fetch data (with caching)
    data = fetch_data_cached(ticker, period)

    if data is None:
        st.error(f"Could not fetch data for {ticker}. Please check the symbol.")
        return

    # Route to page
    if page == "Overview":
        render_overview(data, ticker)
    elif page == "Price Chart":
        render_price_chart(data, ticker)
    elif page == "Sentiment":
        render_sentiment_panel(ticker)
    elif page == "Backtest":
        render_backtest_panel(data, ticker)
    elif page == "Portfolio":
        render_portfolio_dashboard()

@st.cache_data(ttl=300)
def fetch_data_cached(ticker: str, period: str):
    """Fetch OHLCV data with Streamlit caching."""
    provider = YFinanceProvider()
    if not provider.validate_ticker(ticker):
        return None

    period_map = {"1M": 30, "3M": 90, "6M": 180, "1Y": 365, "2Y": 730, "5Y": 1825}
    days = period_map.get(period, 365)

    from datetime import date, timedelta
    end = date.today()
    start = end - timedelta(days=days)

    try:
        return provider.get_prices(ticker, start=start, end=end)
    except Exception:
        return None

if __name__ == "__main__":
    main()
```

### Ticker Search with Autocomplete

```python
import streamlit as st

# Popular tickers for autocomplete suggestions
POPULAR_TICKERS = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "TSLA", "META", "NVDA",
    "SPY", "QQQ", "IWM", "VTI", "VOO",
    "BTC-USD", "ETH-USD", "SOL-USD",
    "GLD", "TLT", "VIX",
]

def render_ticker_search():
    """Enhanced ticker search with validation and suggestions."""
    col1, col2 = st.columns([3, 1])

    with col1:
        ticker = st.text_input(
            "🔍 Ticker Symbol",
            value="AAPL",
            placeholder="Enter ticker (e.g., AAPL, BTC-USD)",
        ).upper().strip()

    with col2:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("🚀 Load", use_container_width=True):
            st.session_state.ticker = ticker

    # Quick-select popular tickers
    st.caption("Quick select:")
    cols = st.columns(6)
    for i, t in enumerate(POPULAR_TICKERS[:6]):
        with cols[i]:
            if st.button(t, key=f"quick_{t}", use_container_width=True):
                st.session_state.ticker = t
                st.rerun()

    return ticker
```

### Plotly Price Charts with Technical Overlays

```python
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np

def render_price_chart(data, ticker: str):
    """Render interactive price chart with technical indicators."""
    st.markdown(f"### 📈 {ticker} Price Chart")

    # Indicator toggles
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        show_ma20 = st.toggle("MA 20", value=True)
    with col2:
        show_ma50 = st.toggle("MA 50", value=True)
    with col3:
        show_bollinger = st.toggle("Bollinger Bands", value=False)
    with col4:
        show_volume = st.toggle("Volume", value=True)

    df = data.to_dataframe()

    # Create subplots: price main, volume secondary
    fig = make_subplots(
        rows=2 if show_volume else 1,
        cols=1,
        shared_xaxes=True,
        row_heights=[0.8, 0.2] if show_volume else [1.0],
        vertical_spacing=0.05,
    )

    # Candlestick chart
    fig.add_trace(
        go.Candlestick(
            x=df.index,
            open=df["open"],
            high=df["high"],
            low=df["low"],
            close=df["close"],
            name=ticker,
            increasing_line_color="#26a69a",
            decreasing_line_color="#ef5350",
        ),
        row=1, col=1,
    )

    # Moving averages
    if show_ma20:
        ma20 = df["close"].rolling(20).mean()
        fig.add_trace(
            go.Scatter(x=df.index, y=ma20, name="MA 20",
                      line=dict(color="#2196F3", width=1)),
            row=1, col=1,
        )
    if show_ma50:
        ma50 = df["close"].rolling(50).mean()
        fig.add_trace(
            go.Scatter(x=df.index, y=ma50, name="MA 50",
                      line=dict(color="#FF9800", width=1)),
            row=1, col=1,
        )

    # Bollinger Bands
    if show_bollinger:
        ma20 = df["close"].rolling(20).mean()
        std20 = df["close"].rolling(20).std()
        fig.add_trace(
            go.Scatter(x=df.index, y=ma20 + 2*std20, name="BB Upper",
                      line=dict(color="#9C27B0", width=1, dash="dash")),
            row=1, col=1,
        )
        fig.add_trace(
            go.Scatter(x=df.index, y=ma20 - 2*std20, name="BB Lower",
                      line=dict(color="#9C27B0", width=1, dash="dash")),
            row=1, col=1,
        )

    # Volume bars
    if show_volume:
        colors = ["#26a69a" if c >= o else "#ef5350"
                  for c, o in zip(df["close"], df["open"])]
        fig.add_trace(
            go.Bar(x=df.index, y=df["volume"], name="Volume",
                   marker_color=colors, opacity=0.5),
            row=2, col=1,
        )

    # Layout
    fig.update_layout(
        title=f"{ticker} — Price Chart",
        yaxis_title="Price ($)",
        xaxis_rangeslider_visible=False,
        height=600 if show_volume else 500,
        template="plotly_white",
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
    )

    st.plotly_chart(fig, use_container_width=True)

    # Price statistics
    col1, col2, col3, col4, col5 = st.columns(5)
    latest = df["close"].iloc[-1]
    prev = df["close"].iloc[-2]
    change = latest - prev
    change_pct = change / prev * 100

    with col1:
        st.metric("Price", f"${latest:.2f}", f"{change:+.2f} ({change_pct:+.2f}%)")
    with col2:
        st.metric("High", f"${df['high'].max():.2f}")
    with col3:
        st.metric("Low", f"${df['low'].min():.2f}")
    with col4:
        st.metric("Volume", f"{df['volume'].iloc[-1:,.0f}")
    with col5:
        st.metric("Avg Vol (20d)", f"{df['volume'].rolling(20).mean().iloc[-1:,.0f}")
```

### Backtest Results Display

```python
import streamlit as st
import plotly.graph_objects as go
import pandas as pd

def render_backtest_panel(data, ticker: str):
    """Render backtest configuration and results."""
    st.markdown(f"### 🧪 Backtest: {ticker}")

    # Configuration
    col1, col2, col3 = st.columns(3)
    with col1:
        signal_type = st.selectbox(
            "Signal Type",
            ["Momentum", "MA Crossover", "Z-Score", "RSI"],
        )
    with col2:
        initial_capital = st.number_input(
            "Initial Capital", value=100_000, step=10_000, min_value=10_000,
        )
    with col3:
        commission = st.number_input(
            "Commission (%)", value=0.1, step=0.05, min_value=0.0, max_value=5.0,
        ) / 100

    # Signal-specific parameters
    with st.expander("Signal Parameters"):
        if signal_type == "Momentum":
            lookback = st.slider("Lookback Period", 5, 60, 20)
            threshold = st.slider("Threshold", 0.01, 0.20, 0.05)
            signal = MomentumSignal(lookback=lookback, threshold=threshold)
        elif signal_type == "MA Crossover":
            fast = st.slider("Fast MA", 5, 50, 20)
            slow = st.slider("Slow MA", 20, 200, 50)
            signal = MACrossoverSignal(fast=fast, slow=slow)
        elif signal_type == "Z-Score":
            lookback = st.slider("Lookback", 5, 60, 20)
            threshold = st.slider("Z-Score Threshold", 0.5, 4.0, 2.0)
            signal = ZScoreSignal(lookback=lookback, threshold=threshold)

    # Run backtest
    if st.button("▶️ Run Backtest", type="primary", use_container_width=True):
        with st.spinner("Running backtest..."):
            from alpha_search.backtest.cost_model import CostModel
            from alpha_search.backtest.engine import BacktestEngine

            cost_model = CostModel(commission=commission)
            engine = BacktestEngine(cost_model=cost_model)
            result = engine.run(data, signal, initial_capital=initial_capital)

        # Results layout
        st.success(f"Backtest complete — {result.signal_name} on {ticker}")

        # Metrics cards
        col1, col2, col3, col4, col5, col6 = st.columns(6)
        metrics = result.metrics

        with col1:
            total_color = "normal" if metrics["total_return"] >= 0 else "inverse"
            st.metric("Total Return", f"{metrics['total_return']*100:.1f}%", delta_color=total_color)
        with col2:
            st.metric("Sharpe Ratio", f"{metrics['sharpe_ratio']:.2f}")
        with col3:
            st.metric("Max Drawdown", f"{metrics['max_drawdown']*100:.1f}%", delta_color="inverse")
        with col4:
            st.metric("Sortino", f"{metrics['sortino_ratio']:.2f}")
        with col5:
            st.metric("Win Rate", f"{metrics['win_rate']*100:.1f}%")
        with col6:
            st.metric("# Trades", f"{metrics['num_trades']}")

        # Equity curve
        st.markdown("#### Equity Curve")
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=result.dates,
            y=result.equity_curve,
            name="Strategy",
            line=dict(color="#2196F3", width=2),
            fill="tozeroy",
            fillcolor="rgba(33, 150, 243, 0.1)",
        ))
        # Add buy-and-hold benchmark
        benchmark = (1 + data.close.pct_change().fillna(0)).cumprod()
        fig.add_trace(go.Scatter(
            x=result.dates,
            y=benchmark,
            name="Buy & Hold",
            line=dict(color="#9E9E9E", width=1, dash="dash"),
        ))
        fig.update_layout(
            height=400,
            template="plotly_white",
            yaxis_title="Portfolio Value",
            hovermode="x unified",
            legend=dict(orientation="h", yanchor="bottom", y=1.02),
        )
        st.plotly_chart(fig, use_container_width=True)

        # Full metrics table
        with st.expander("📋 Full Metrics Report"):
            metrics_df = pd.DataFrame([
                {"Metric": k.replace("_", " ").title(), "Value": v}
                for k, v in metrics.items()
            ])
            st.dataframe(metrics_df, use_container_width=True, hide_index=True)

        # Trade log
        if not result.trades.empty:
            with st.expander("📜 Trade Log"):
                st.dataframe(
                    result.trades.style.format({
                        "entry_price": "${:.2f}",
                        "exit_price": "${:.2f}",
                        "pnl_pct": "{:.2%}",
                    }),
                    use_container_width=True,
                )
```

### Portfolio/Risk Dashboard

```python
import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np

def render_portfolio_dashboard():
    """Render portfolio positions, PNL, and risk metrics."""
    st.markdown("### 💼 Portfolio & Risk Dashboard")

    # Portfolio summary
    col1, col2, col3, col4 = st.columns(4)

    # Example portfolio data — in production, fetch from ExecutionGateway
    portfolio_data = {
        "cash": 45_230.50,
        "total_equity": 102_450.75,
        "total_unrealized_pnl": 2_450.75,
        "total_realized_pnl": 1_120.30,
        "gross_leverage": 1.12,
        "net_leverage": 0.56,
    }

    with col1:
        st.metric("Total Equity", f"${portfolio_data['total_equity']:,.2f}")
    with col2:
        st.metric("Cash", f"${portfolio_data['cash']:,.2f}")
    with col3:
        color = "normal" if portfolio_data["total_unrealized_pnl"] >= 0 else "inverse"
        st.metric("Unrealized P&L", f"${portfolio_data['total_unrealized_pnl']:,.2f}", delta_color=color)
    with col4:
        st.metric("Realized P&L", f"${portfolio_data['total_realized_pnl']:,.2f}")

    # Risk metrics
    st.markdown("#### Risk Metrics")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Gross Leverage", f"{portfolio_data['gross_leverage']:.2f}x")
    with col2:
        st.metric("Net Leverage", f"{portfolio_data['net_leverage']:.2f}x")
    with col3:
        st.metric("Max Drawdown", "3.2%", delta_color="inverse")
    with col4:
        st.metric("VaR (95%)", "$1,250")

    # Positions table
    st.markdown("#### Positions")
    positions_df = pd.DataFrame([
        {"Ticker": "AAPL", "Side": "Long", "Quantity": 100, "Entry": "$175.50",
         "Current": "$182.30", "P&L": "+$680", "P&L %": "+3.9%"},
        {"Ticker": "MSFT", "Side": "Long", "Quantity": 50, "Entry": "$380.00",
         "Current": "$375.20", "P&L": "-$240", "P&L %": "-1.3%"},
        {"Ticker": "SPY", "Side": "Long", "Quantity": 25, "Entry": "$520.00",
         "Current": "$528.40", "P&L": "+$210", "P&L %": "+1.6%"},
    ])
    st.dataframe(positions_df, use_container_width=True, hide_index=True)

    # Allocation pie chart
    fig = go.Figure(data=[go.Pie(
        labels=["AAPL", "MSFT", "SPY", "Cash"],
        values=[18230, 18760, 13210, 45230],
        hole=0.4,
        marker_colors=["#2196F3", "#4CAF50", "#FF9800", "#9E9E9E"],
    )])
    fig.update_layout(
        title="Portfolio Allocation",
        height=350,
        template="plotly_white",
        showlegend=True,
    )
    st.plotly_chart(fig, use_container_width=True)
```

## Responsibilities

1. Build the Streamlit main app with sidebar navigation and page routing
2. Implement ticker search with popular suggestions and validation
3. Create interactive Plotly candlestick charts with MA/Bollinger overlays
4. Build the backtest panel with signal configuration and results display
5. Render equity curves with buy-and-hold benchmark overlay
6. Display performance metrics in formatted cards and tables
7. Build the portfolio/risk dashboard with positions, PNL, and leverage
8. Ensure all data is cached appropriately (st.cache_data for expensive operations)
9. Format all monetary values, percentages, and ratios consistently
10. Make the interface responsive and visually professional

## Inputs

- OHLCV data from DataProvider for charts and backtests
- Signal objects from the signal framework for backtest configuration
- BacktestResult objects for results display
- Sentiment data from Research Intelligence for sentiment panel
- Portfolio data from Execution Gateway for dashboard
- User selections (ticker, time period, signal parameters)

## Outputs

- Streamlit-rendered web pages (Overview, Price Chart, Sentiment, Backtest, Portfolio)
- Interactive Plotly charts (candlesticks, equity curves, allocation pies)
- Formatted metric cards and data tables
- Backtest configuration forms and results reports

## Required Files to Create or Modify

- `alpha_search/ui/app.py` — main Streamlit application (create)
- `alpha_search/ui/pages/overview.py` — market overview page (create)
- `alpha_search/ui/pages/backtest.py` — backtest configuration + results (create)
- `alpha_search/ui/pages/portfolio.py` — portfolio + risk dashboard (create)
- `alpha_search/ui/pages/sentiment.py` — sentiment analysis panel (create)
- `alpha_search/ui/components/charts.py` — Plotly chart wrappers (create)
- `alpha_search/ui/components/sidebar.py` — navigation sidebar (create)
- `alpha_search/ui/components/tables.py` — formatted data tables (create)
- `alpha_search/ui/__init__.py` — module exports (create)
- `alpha_search/ui/pages/__init__.py` — page exports (create)
- `alpha_search/ui/components/__init__.py` — component exports (create)

## Implementation Checklist

- [ ] Create main app.py with page configuration and sidebar navigation
- [ ] Implement ticker search with validation and quick-select buttons
- [ ] Build candlestick chart with MA 20/50 and Bollinger Band overlays
- [ ] Add volume subplot to price chart
- [ ] Create backtest panel with signal type selector
- [ ] Add signal parameter controls (sliders for lookback, threshold, etc.)
- [ ] Display backtest metrics in card layout (Sharpe, return, drawdown, win rate)
- [ ] Render equity curve with buy-and-hold benchmark
- [ ] Display trade log in sortable data table
- [ ] Build sentiment panel with composite score gauge
- [ ] Build portfolio dashboard with positions, PNL, leverage
- [ ] Create allocation pie chart
- [ ] Add risk metrics display (VaR, drawdown, leverage ratios)
- [ ] Implement data caching for expensive operations
- [ ] Ensure responsive layout on mobile and desktop

## Testing Checklist

- [ ] App loads without errors on `streamlit run alpha_search/ui/app.py`
- [ ] Ticker search accepts input and fetches data
- [ ] Candlestick chart renders with correct OHLC data
- [ ] MA overlays calculate correctly (verified against pandas)
- [ ] Backtest panel runs without errors for all signal types
- [ ] Equity curve starts at 1.0 and reflects strategy returns
- [ ] Metrics cards display correct values from BacktestResult
- [ ] Trade log shows all trades with correct PNL
- [ ] Portfolio dashboard displays positions and allocation
- [ ] All charts are interactive (zoom, pan, hover tooltips)
- [ ] Data caching prevents redundant API calls
- [ ] Invalid tickers show appropriate error messages
- [ ] Layout is readable on both desktop and mobile screens

## Definition of Done

- Streamlit app launches successfully and all 5 pages are navigable
- Price chart renders interactive candlesticks with optional overlays
- Backtest panel allows signal selection, parameter tuning, and displays results
- Equity curve chart includes buy-and-hold benchmark
- All backtest metrics are displayed in readable card format
- Portfolio dashboard shows positions, PNL, leverage, and allocation
- Sentiment panel displays composite score and source breakdown
- Data is cached to prevent redundant API calls
- UI is visually professional and responsive
- No runtime errors across all pages and interactions

## Example Prompt

> You are the Alpha Search UI Terminal agent. Build a Streamlit application with 5 pages: Overview, Price Chart, Sentiment, Backtest, and Portfolio. The Price Chart page must show interactive Plotly candlesticks with optional MA 20/50 and Bollinger Band overlays plus a volume subplot. The Backtest page must allow signal selection (Momentum/MA Crossover/Z-Score) with parameter sliders, run the backtest, and display results with equity curve, metrics cards, and trade log. Use st.cache_data for API calls. Make it visually professional with consistent formatting.