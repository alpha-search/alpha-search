import { useScan } from "@/store/scanStore";
import { fmtPrice, fmtPct } from "@/lib/format";
import { cn } from "@/lib/cn";

export function SCAN() {
  const { scanResults, report, isScanning, error, theme, tickers } = useScan();

  // Helper to parse simple markdown to JSX
  const renderMarkdown = (md: string) => {
    if (!md) return <div className="text-term-muted">No report generated yet. Run a scan to synthesize analysis.</div>;
    
    const lines = md.split("\n");
    let inTable = false;
    let tableRows: string[][] = [];
    const elements: JSX.Element[] = [];

    const flushTable = (keyIdx: number) => {
      if (tableRows.length > 0) {
        const headers = tableRows[0];
        const rows = tableRows.slice(2); // Skip separator row
        elements.push(
          <div key={`table-${keyIdx}`} className="my-3 overflow-x-auto">
            <table className="w-full grid-data">
              <thead>
                <tr>
                  {headers.map((h, i) => (
                    <th key={i} className={cn(i > 0 && "text-right")}>{h.trim()}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {rows.map((row, rIdx) => (
                  <tr key={rIdx}>
                    {row.map((cell, cIdx) => {
                      const text = cell.trim();
                      const isNum = cIdx > 0 && !isNaN(parseFloat(text.replace(/[\$%]/g, "")));
                      return (
                        <td key={cIdx} className={cn(isNum ? "num text-right" : "text-term-heading")}>
                          {text}
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        );
        tableRows = [];
      }
      inTable = false;
    };

    lines.forEach((line, idx) => {
      const trimmed = line.trim();
      
      // Parse tables
      if (trimmed.startsWith("|")) {
        inTable = true;
        const cols = trimmed.split("|").filter((_, i, arr) => i > 0 && i < arr.length - 1);
        tableRows.push(cols);
        return;
      } else if (inTable) {
        flushTable(idx);
      }

      if (trimmed === "") {
        elements.push(<div key={idx} className="h-2" />);
        return;
      }

      // Headers
      if (trimmed.startsWith("# ")) {
        elements.push(
          <h1 key={idx} className="text-term-amber text-[14px] font-bold border-b border-term-border pb-1 mt-4 mb-2 uppercase tracking-widest">
            {trimmed.slice(2)}
          </h1>
        );
      } else if (trimmed.startsWith("## ")) {
        elements.push(
          <h2 key={idx} className="text-term-amberBright text-[12px] font-bold mt-3 mb-1.5 uppercase tracking-wide">
            {trimmed.slice(3)}
          </h2>
        );
      } else if (trimmed.startsWith("### ")) {
        elements.push(
          <h3 key={idx} className="text-term-heading text-[11px] font-bold mt-2 mb-1">
            {trimmed.slice(4)}
          </h3>
        );
      } else if (trimmed.startsWith("* ") || trimmed.startsWith("- ")) {
        elements.push(
          <div key={idx} className="flex gap-2 pl-4 py-0.5 text-term-text">
            <span className="text-term-amber select-none">•</span>
            <span>{trimmed.slice(2)}</span>
          </div>
        );
      } else {
        // Render bold text matching
        const boldRegex = /\*\*(.*?)\*\*/g;
        let match;
        const textParts = [];
        let lastIdx = 0;
        
        while ((match = boldRegex.exec(trimmed)) !== null) {
          if (match.index > lastIdx) {
            textParts.push(trimmed.slice(lastIdx, match.index));
          }
          textParts.push(<strong key={match.index} className="text-term-heading font-semibold">{match[1]}</strong>);
          lastIdx = boldRegex.lastIndex;
        }
        if (lastIdx < trimmed.length) {
          textParts.push(trimmed.slice(lastIdx));
        }
        
        elements.push(
          <p key={idx} className="text-term-text leading-relaxed py-0.5">
            {textParts.length > 0 ? textParts : trimmed}
          </p>
        );
      }
    });

    if (inTable) {
      flushTable(9999);
    }

    return <div className="flex flex-col gap-1 pr-2">{elements}</div>;
  };

  return (
    <div className="flex-1 flex flex-col min-h-0 text-[12px] font-mono p-3 gap-3">
      {/* Header */}
      <div className="flex justify-between items-center border-b border-term-border pb-1">
        <span className="text-term-amber text-[10px] tracking-[0.25em] font-bold">THEMATIC SCANNER</span>
        <span className="text-term-muted text-[10px]">THEME: "{theme.toUpperCase()}" · ({tickers.length} TICKERS)</span>
      </div>

      {/* Main split panels */}
      {isScanning ? (
        <div className="flex-1 flex flex-col items-center justify-center border border-term-border bg-term-panel rounded-sm">
          <div className="flex items-center gap-3">
            <span className="w-4 h-4 border-2 border-term-amber border-t-transparent rounded-full animate-spin" />
            <span className="text-term-amber font-bold uppercase tracking-widest text-[13px] animate-pulse">Running Stock Opportunity Agent Scan...</span>
          </div>
          <span className="text-term-muted text-[10px] mt-2">Ingesting quotes, computing 21d volatility, correlation pruning, X sentiment & patent growth...</span>
        </div>
      ) : error ? (
        <div className="flex-1 flex flex-col items-center justify-center border border-term-red bg-term-panel rounded-sm p-6 text-center">
          <span className="text-term-red font-bold text-[13px] uppercase tracking-wider mb-2">Scan Failed</span>
          <p className="text-term-text max-w-md">{error}</p>
        </div>
      ) : scanResults.length === 0 ? (
        <div className="flex-1 flex flex-col items-center justify-center border border-term-border bg-term-panel rounded-sm text-center">
          <span className="text-term-muted text-[11px] uppercase tracking-wider mb-1">Scanner Idle</span>
          <p className="text-term-muted max-w-sm">Use the BUILD command to choose stocks, set a thematic query, and click RUN.</p>
        </div>
      ) : (
        <div className="flex-1 flex flex-col min-h-0 gap-3">
          {/* Opportunity Grid Table */}
          <div className="border border-term-border bg-term-panel rounded-sm flex flex-col max-h-[45%]">
            <div className="bg-term-bg border-b border-term-border p-2 flex justify-between items-center select-none">
              <span className="text-term-amberBright font-bold uppercase tracking-wider">Opportunity Scorecard</span>
              <span className="text-term-muted text-[10px]">SORTED BY OVERALL OPPORTUNITY SCORE</span>
            </div>
            
            <div className="overflow-auto p-2">
              <table className="w-full grid-data">
                <thead>
                  <tr>
                    <th>Ticker</th>
                    <th className="text-right">Price</th>
                    <th className="text-right">Vol (63d)</th>
                    <th className="text-right">21d Vol</th>
                    <th className="text-right">Momentum</th>
                    <th className="text-right">Z-Score</th>
                    <th className="text-right">Dist High</th>
                    <th className="text-right">Beta</th>
                    <th className="text-right">Avg Corr</th>
                    <th className="text-center">Uncorr?</th>
                    <th className="text-right">X Sentiment</th>
                    <th className="text-right">Patents YoY</th>
                    <th className="text-right">Insider Ratio</th>
                    <th>Opportunity Type</th>
                    <th className="text-right">Score</th>
                  </tr>
                </thead>
                <tbody>
                  {scanResults.map((row) => (
                    <tr key={row.Ticker}>
                      <td className="num text-term-amber font-semibold">{row.Ticker}</td>
                      <td className="num text-right">{fmtPrice(row.Current_Close)}</td>
                      <td className="num text-right text-term-muted">${row.Med_Dollar_Vol_63d_M.toFixed(1)}M</td>
                      <td className="num text-right">{fmtPct(row.Volatility_21d_Ann * 100)}</td>
                      <td className={cn("num text-right", row.Momentum_12_1M >= 0 ? "up" : "down")}>
                        {fmtPct(row.Momentum_12_1M * 100)}
                      </td>
                      <td className={cn("num text-right", row.Z_Score_20d <= -1.25 && "up", row.Z_Score_20d >= 1.5 && "down")}>
                        {row.Z_Score_20d.toFixed(2)}
                      </td>
                      <td className="num text-right">{fmtPct(row.Dist_to_20d_High_Pct * 100)}</td>
                      <td className="num text-right text-term-muted">{row.Beta_vs_SPY.toFixed(2)}</td>
                      <td className="num text-right text-term-muted">{row.Mean_Pairwise_Correlation.toFixed(2)}</td>
                      <td className="text-center font-bold">
                        {row.Is_Selected_Uncorrelated === 1 ? (
                          <span className="text-term-green">●</span>
                        ) : (
                          <span className="text-term-muted">○</span>
                        )}
                      </td>
                      <td className={cn("num text-right", row.Social_Sentiment_Score > 0 ? "up" : row.Social_Sentiment_Score < 0 ? "down" : "")}>
                        {row.Social_Sentiment_Score > 0 ? "+" : ""}{row.Social_Sentiment_Score.toFixed(2)}
                      </td>
                      <td className="num text-right">{fmtPct(row.Patent_YoY_Growth * 100)}</td>
                      <td className={cn("num text-right", row.Insider_Net_Buy_Ratio > 0 ? "up" : row.Insider_Net_Buy_Ratio < 0 ? "down" : "")}>
                        {row.Insider_Net_Buy_Ratio > 0 ? "+" : ""}{row.Insider_Net_Buy_Ratio.toFixed(2)}
                      </td>
                      <td className={cn(
                        "font-semibold",
                        row.Opportunity_Type === "Momentum Breakout" && "text-term-green",
                        row.Opportunity_Type === "Mean Reversion Dip" && "text-term-cyan",
                        row.Opportunity_Type === "Neutral" && "text-term-muted"
                      )}>
                        {row.Opportunity_Type}
                      </td>
                      <td className="num text-right text-term-amber font-bold">{row.Overall_Opportunity_Score.toFixed(2)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* AI Report Panel */}
          <div className="flex-1 border border-term-border bg-term-panel rounded-sm flex flex-col min-h-0">
            <div className="bg-term-bg border-b border-term-border p-2 flex justify-between items-center select-none">
              <span className="text-term-amberBright font-bold uppercase tracking-wider">AI Analyst Quantitative Synthesis</span>
              <span className="text-term-muted text-[10px]">POWERED BY GOOGLE GEMINI 2.5 FLASH</span>
            </div>
            <div className="flex-1 overflow-y-auto p-4 custom-scrollbar">
              {renderMarkdown(report)}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
