import { create } from "zustand";

export interface OpportunityRecord {
  Ticker: string;
  Current_Close: number;
  Med_Dollar_Vol_63d_M: number;
  Volatility_21d_Ann: number;
  Momentum_12_1M: number;
  Z_Score_20d: number;
  Dist_to_20d_High_Pct: number;
  Beta_vs_SPY: number;
  Mean_Pairwise_Correlation: number;
  Is_Selected_Uncorrelated: number;
  Social_Sentiment_Score: number;
  Patent_YoY_Growth: number;
  Insider_Net_Buy_Ratio: number;
  Opportunity_Type: string;
  Overall_Opportunity_Score: number;
}

interface ScanState {
  tickers: string[];
  theme: string;
  scanResults: OpportunityRecord[];
  report: string;
  isScanning: boolean;
  error: string | null;
  setTickers: (tickers: string[]) => void;
  setTheme: (theme: string) => void;
  runThematicScan: () => Promise<void>;
}

export const useScan = create<ScanState>((set, get) => ({
  tickers: ["NVDA", "MSFT", "VRT", "AMZN", "AVGO", "SMCI", "AAPL", "COST", "WMT"],
  theme: "liquid cooling for artificial intelligence server infrastructure",
  scanResults: [],
  report: "",
  isScanning: false,
  error: null,
  setTickers: (tickers) => set({ tickers }),
  setTheme: (theme) => set({ theme }),
  runThematicScan: async () => {
    const { tickers, theme } = get();
    if (tickers.length === 0) {
      set({ error: "Please select at least one stock to scan." });
      return;
    }
    
    set({ isScanning: true, error: null });
    try {
      const res = await fetch("/api/v1/scan", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ tickers, theme }),
      });
      
      if (!res.ok) {
        throw new Error(await res.text() || "Scan execution failed.");
      }
      
      const body = await res.json();
      const payload = body.results;
      
      set({
        scanResults: payload.data,
        report: payload.report,
        isScanning: false,
      });
    } catch (e: any) {
      set({
        error: e.message || "An unexpected error occurred during the scan.",
        isScanning: false,
      });
    }
  },
}));
