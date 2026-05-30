# Getting Started: Semiconductor Research in Antigravity IDE

Welcome to the **Alpha Search Semiconductor & AI Infrastructure Alpha Research** tutorial. This guide will show you how to open the project in the Antigravity IDE, understand its structure, and execute the backtesting notebook.

---

## 1. How to Open the Project in the IDE

1. **Copy the Path:** Copy this absolute folder path:
   ```text
   /Users/kalyandinavahi/.gemini/antigravity/scratch/alpha-search
   ```
2. **Open Antigravity IDE:** Launch the IDE on your Mac.
3. **Open Folder:** In the menu, go to **File ➔ Open Folder** (or **Open Workspace**).
4. **Navigate to Path:** If the folder is hidden, press **`Cmd` + `Shift` + `G`** in the file picker, paste the path you copied, press **Enter**, and select the `alpha-search` folder.
5. **Set Active Workspace:** Click **Open**. The workspace is now initialized.

---

## 2. Project Architecture Overview

This project implements a complete quantitative trading strategy research loop under a unified architecture:

```
[Ingestion] ➔ [Validation] ➔ [Agent Review] ➔ [Signals] ➔ [Backtesting] ➔ [Reporting]
```

*   **`alpha_search/data`:** Fetches real yfinance OHLCV prices and volumes.
*   **`alpha_search/agents`:** Swarm system containing the `DataEngineerAgent` and `OpportunityAgent` which reviews data anomalies and suggests entry filters.
*   **`alpha_search/signals`:** Generators for Cross-Sectional Momentum, Trend-Following, Mean Reversion, and Donchian Breakouts.
*   **`alpha_search/backtest`:** Vectorized portfolio simulation, deducting basis point commission and slippage (20 bps round-trip) on rebalances.

---

## 3. Running the Jupyter Notebook

We have generated a custom Jupyter Notebook specifically designed to execute this usecase.

### Step 1: Open the Notebook in the IDE
*   In the file explorer panel on the left side of the IDE, navigate to the `notebooks` directory.
*   Click to open: **`notebooks/Semiconductor_AI_Alpha_Research.ipynb`**

### Step 2: Select the Python Interpreter
*   In the top-right corner of the notebook editor, click **Select Kernel** or **Select Interpreter**.
*   Select your local Python environment (e.g. `Python 3` or your conda miniconda environment).

### Step 3: Run the Cells
1.  **Run Cell 1 (Environment Setup):** This imports the package checker. Since you are running it locally, it will print `alpha_search already installed.`
2.  **Run Cell 2 (Imports):** This imports the strategy pipelines.
    > **Note:** We added `sys.path.insert(0, os.path.abspath('..'))` at the top of this cell so that the notebook can successfully find the local `alpha_search` code without any import errors.
3.  **Run Cell 3 & 4 (Download):** Downloads the 5-year daily pricing and volume data from yfinance for the 32 semiconductor symbols.
4.  **Run Cell 5 & 6 (Validation & Agent Swarm):** Validates data quality. Runs the `DataEngineerAgent` and `OpportunityAgent` review. You will see their markdown critiques printed in the output!
5.  **Run Cells 7 & 8 (Backtest):** Calculates strategy signals and simulates backtests net-of-costs.
6.  **Run Cells 9 to 12 (Analytics & Visualization):** Renders the metrics comparison table and plots net equity log-curves, drawdowns, and rolling Sharpe ratios.
7.  **Run Cell 13 & 14 (Export):** Writes outputs (CSVs and the final report) directly to disk.

---

## 4. Leverage the Antigravity Agent in the IDE

Because this folder is your active workspace, you can ask the integrated agent in the sidebar to automate tasks for you:

*   **To run the CLI version:** Ask the agent: *"Run the semiconductor pipeline script for me."* (It will execute `scripts/run_ai_infra_research.py`).
*   **To run tests:** Ask the agent: *"Run pytest on the pipeline."*
*   **To change strategy configurations:** Ask the agent: *"Update the trend-following moving average windows to [20, 50, 100] inside `DEFAULT_CONFIG`."*

---

## 5. Finding Your Results

Once you run the notebook to completion, the CSVs and research report are saved locally on your Mac at:
```text
/Users/kalyandinavahi/.gemini/antigravity/scratch/alpha-search/outputs/research_runs/ai_infrastructure/
```

*   **`report.md`:** The compiled markdown research report containing strategy tables and agent reviews.
*   **`strategy_returns.csv`:** Full daily historical returns of the strategies.
*   **`strategy_results_summary.csv`:** Performance analytics (Sharpe, Drawdowns, Alpha vs SOXX).
