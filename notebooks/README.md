# Alpha Search - Full Pipeline Demo Notebook

A comprehensive, Google Colab-ready Jupyter notebook demonstrating the complete Alpha Search quantitative research pipeline end-to-end.

## Overview

This notebook showcases the full capabilities of [Alpha Search](https://github.com/alpha-search/alpha-search), an open-source quantitative research framework featuring multi-agent AI collaboration, technical signal generation, backtesting, and opportunity discovery.

## Open in Google Colab

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/alpha-search/alpha-search/blob/main/notebooks/Alpha_Search_Demo.ipynb)

## Requirements

- Python 3.9+
- Google Colab or Jupyter Notebook environment
- Internet access (for downloading market data via Yahoo Finance)

### Dependencies

The notebook automatically installs all required packages:

```bash
pip install git+https://github.com/alpha-search/alpha-search.git
pip install yfinance pandas numpy matplotlib seaborn
```

## Notebook Sections

| Section | Description |
|---------|-------------|
| **1. Title & Description** | Overview of Alpha Search with badges and table of contents |
| **2. Install Dependencies** | Automatic installation of alpha-search and core packages |
| **3. Imports & Configuration** | All imports, plotting style, logging, and warning suppression |
| **4. Universe Selection** | Define 20 large-cap US tickers across 5 sectors + SPY benchmark |
| **5. Fetch Real Market Data** | Download 2 years of daily OHLCV data via YFinanceProvider |
| **6. Data Quality Check** | Per-ticker statistics, missing data analysis, cleaning |
| **7. Visualize Price History** | Normalized price chart (base=100) with all tickers |
| **8. Technical Signals** | Momentum, z-score mean reversion, Bollinger Band, MA crossover |
| **9. Strategy Backtesting** | Momentum, mean reversion, combined, and buy-and-hold strategies |
| **10. Agent Swarm Setup** | Instantiate and register all 5 specialized agents |
| **11. Run Agent Swarm Collaboration** | Execute the full multi-agent collaboration (~30 seconds) |
| **12. Display Critiques** | Agent-to-agent critique log with severity filtering |
| **13. Display Consensus** | Full consensus report with agent sign-offs and recommendations |
| **14. Visualize Backtest Performance** | Cumulative returns and drawdown charts for all strategies |
| **15. Statistical Arbitrage** | Pairs trading scan and correlation matrix heatmap |
| **16. Save Results to Memory** | Persist results to MemoryStore for audit trail |
| **17. Summary & Next Steps** | Key takeaways, documentation links, and disclaimer |

## Key Features Demonstrated

### Multi-Agent Collaboration
The notebook deploys 5 specialized AI agents that:
- **DataEngineerAgent**: Validates data quality and handles missing values
- **OpportunityAgent**: Discovers arbitrage and pairs trading opportunities
- **QuantEngineerAgent**: Builds and backtests technical signals
- **ResearchAgent**: Validates findings against academic literature
- **RiskManagerAgent**: Enforces position limits and drawdown controls

### Signal Generation
- 20-day momentum signals
- Z-score mean reversion
- Bollinger Band position
- Moving average crossover

### Backtesting
- Realistic cost model (0.1% commission + 0.1% slippage)
- Multiple strategy comparisons
- Sharpe ratio, max drawdown, and win rate metrics

### Error Handling
The notebook includes comprehensive error handling:
- Graceful fallback if `YFinanceProvider` fails
- Synthetic data generation if rate-limited
- Try/except blocks around all Alpha Search API calls
- Manual signal computation fallbacks

## How to Run

### In Google Colab (Recommended)
1. Click the **Open in Colab** badge above
2. Runtime > Run all (Ctrl+F9)
3. The notebook executes top-to-bottom automatically

### Locally
```bash
jupyter notebook Alpha_Search_Demo.ipynb
```

### In VS Code
1. Install the Jupyter extension
2. Open `Alpha_Search_Demo.ipynb`
3. Click "Run All"

## Expected Output

The notebook produces:
- **1 normalized price performance chart** (all tickers)
- **1 backtest comparison chart** (cumulative returns + drawdowns)
- **1 correlation matrix heatmap** (statistical arbitrage analysis)
- **4 data tables**: universe, quality report, signal summary, backtest results
- **Agent critique log** showing inter-agent feedback
- **Consensus report** with agent sign-offs

## Notebook Structure

- **27 cells total**: 14 markdown cells + 13 code cells
- All code cells have `execution_count: null` and `outputs: []` initially
- Compatible with Jupyter nbformat 4.4
- Designed to run without modification in Google Colab

## Troubleshooting

| Issue | Solution |
|-------|----------|
| `yfinance` rate limit | The notebook auto-generates synthetic fallback data |
| `alpha_search` import error | Check internet connection; package installs from GitHub |
| Matplotlib plots not showing | All plots use `plt.show()`; ensure `%matplotlib inline` |
| Missing tickers | Quality check cell auto-removes tickers with >20% missing data |

## Contributing

Contributions to Alpha Search are welcome! See the [GitHub repository](https://github.com/alpha-search/alpha-search) for guidelines.

## License

MIT License. See [LICENSE](https://github.com/alpha-search/alpha-search/blob/main/LICENSE) for details.

## Disclaimer

**This notebook is for educational and research purposes only.** Nothing herein constitutes investment advice. Past performance does not guarantee future results. Trading involves substantial risk of loss.
