import { useState, useEffect } from "react";
import { useScan } from "@/store/scanStore";
import { useWorkspace } from "@/store/workspaceStore";
import { cn } from "@/lib/cn";

interface SourceTicker {
  ticker: string;
  name: string;
  sector: string;
}

export function BUILD() {
  const { tickers, theme, setTickers, setTheme, runThematicScan, isScanning } = useScan();
  const { openTab } = useWorkspace();
  const [sectorsData, setSectorsData] = useState<Record<string, SourceTicker[]>>({});
  const [activeCategory, setActiveCategory] = useState<string>("");
  const [search, setSearch] = useState("");
  const [isLoading, setIsLoading] = useState(true);

  // Load sectors from FastAPI backend
  useEffect(() => {
    fetch("/api/v1/sectors")
      .then((res) => res.json())
      .then((body) => {
        const data = body.results || {};
        setSectorsData(data);
        const categories = Object.keys(data);
        if (categories.length > 0) {
          setActiveCategory(categories[0]);
        }
        setIsLoading(false);
      })
      .catch(() => setIsLoading(false));
  }, []);

  const sourceList = sectorsData[activeCategory] || [];
  const filteredSource = sourceList.filter(
    (item) =>
      item.ticker.toLowerCase().includes(search.toLowerCase()) ||
      item.name.toLowerCase().includes(search.toLowerCase())
  );

  // Drag and Drop handlers
  const handleDragStart = (e: React.DragEvent, ticker: string) => {
    e.dataTransfer.setData("text/plain", ticker);
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    const ticker = e.dataTransfer.getData("text/plain");
    if (ticker && !tickers.includes(ticker)) {
      setTickers([...tickers, ticker]);
    }
  };

  const removeTicker = (ticker: string) => {
    setTickers(tickers.filter((t) => t !== ticker));
  };

  const addAllFiltered = () => {
    const toAdd = filteredSource.map((s) => s.ticker).filter((t) => !tickers.includes(t));
    setTickers([...tickers, ...toAdd]);
  };

  const clearAll = () => {
    setTickers([]);
  };

  const handleRunScan = async () => {
    openTab("SCAN");
    await runThematicScan();
  };

  return (
    <div className="flex-1 flex flex-col min-h-0 text-[12px] font-mono p-3 gap-3">
      {/* Header */}
      <div className="flex justify-between items-center border-b border-term-border pb-1">
        <span className="text-term-amber text-[10px] tracking-[0.25em] font-bold">UNIVERSE BUILDER</span>
        <span className="text-term-muted text-[10px]">DRAG ITEMS OR CLICK TO BUILD PORTFOLIO</span>
      </div>

      {/* Theme Settings Panel */}
      <div className="bg-term-bg2 border border-term-border p-3 flex flex-col gap-3 rounded-sm shadow-[0_0_15px_rgba(255,140,0,0.02)]">
        <div className="flex items-center gap-3">
          <span className="text-term-amberDim uppercase text-[10px] font-bold tracking-widest w-28">Thematic Query:</span>
          <input
            type="text"
            value={theme}
            onChange={(e) => setTheme(e.target.value)}
            disabled={isScanning}
            className="flex-1 bg-term-bg border border-term-border px-3 py-1.5 text-term-heading focus:outline-none focus:border-term-amber text-[12px]"
            placeholder="e.g. AI server liquid cooling, cloud data centers, etc."
          />
          <button
            onClick={handleRunScan}
            disabled={isScanning || tickers.length === 0}
            className={cn(
              "px-5 py-1.5 font-bold uppercase border tracking-wider transition-all duration-200 select-none",
              tickers.length === 0
                ? "border-term-border text-term-muted cursor-not-allowed"
                : "border-term-amber text-term-amber hover:bg-term-amber hover:text-term-bg cursor-pointer shadow-[0_0_10px_rgba(255,140,0,0.2)]"
            )}
          >
            {isScanning ? "Scanning..." : "<RUN OPPORTUNITY SCAN>"}
          </button>
        </div>
      </div>

      {/* Grid panels */}
      <div className="flex-1 grid grid-cols-2 gap-3 min-h-0">
        {/* Source Stock List */}
        <div className="flex flex-col border border-term-border bg-term-panel min-h-0 rounded-sm">
          {/* Ticker source Category tabs */}
          <div className="flex flex-wrap bg-term-bg border-b border-term-border p-1 gap-1">
            {Object.keys(sectorsData).map((cat) => (
              <button
                key={cat}
                onClick={() => { setActiveCategory(cat); setSearch(""); }}
                className={cn(
                  "px-3 py-1 text-[10px] uppercase font-bold border transition-colors",
                  cat === activeCategory
                    ? "border-term-amber text-term-amber bg-term-amberSubtle"
                    : "border-transparent text-term-muted hover:text-term-heading"
                )}
              >
                {cat}
              </button>
            ))}
          </div>

          {/* Search filter */}
          <div className="p-2 border-b border-term-border flex gap-2">
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="SEARCH TICKER OR COMPANY NAME..."
              className="flex-1 bg-term-bg border border-term-border px-3 py-1 text-term-heading focus:outline-none text-[11px]"
            />
            <button
              onClick={addAllFiltered}
              className="px-2.5 py-1 border border-term-greenDim text-term-green hover:bg-term-green hover:text-term-bg font-bold text-[10px] uppercase"
            >
              Add Category
            </button>
          </div>

          {/* List items */}
          <div className="flex-1 overflow-y-auto p-2 flex flex-col gap-1.5 custom-scrollbar">
            {isLoading ? (
              <div className="text-term-muted p-4 text-center">Loading stock sectors...</div>
            ) : filteredSource.length === 0 ? (
              <div className="text-term-muted p-4 text-center">No tickers match search filter.</div>
            ) : (
              filteredSource.map((item) => {
                const added = tickers.includes(item.ticker);
                return (
                  <div
                    key={item.ticker}
                    draggable={!added}
                    onDragStart={(e) => handleDragStart(e, item.ticker)}
                    onClick={() => {
                      if (!added) setTickers([...tickers, item.ticker]);
                    }}
                    className={cn(
                      "flex items-center justify-between p-2 border border-term-borderSoft rounded-sm select-none transition-all duration-150",
                      added
                        ? "bg-term-bg opacity-40 cursor-not-allowed"
                        : "bg-term-bg2 hover:border-term-amber hover:bg-term-bg cursor-grab"
                    )}
                  >
                    <div className="flex items-center gap-3">
                      <span className="text-term-amber font-bold w-16">{item.ticker}</span>
                      <span className="text-term-heading truncate max-w-[220px]">{item.name}</span>
                    </div>
                    <span className="text-term-muted text-[10px]">{item.sector}</span>
                  </div>
                );
              })
            )}
          </div>
        </div>

        {/* Target Scan Universe zone */}
        <div
          onDragOver={handleDragOver}
          onDrop={handleDrop}
          className="flex flex-col border border-term-border bg-term-panel min-h-0 rounded-sm"
        >
          <div className="flex justify-between items-center bg-term-bg border-b border-term-border p-2">
            <span className="text-term-amberBright font-bold uppercase tracking-wider">Target Scan Universe ({tickers.length})</span>
            <button
              onClick={clearAll}
              className="px-2 py-0.5 border border-term-redDim text-term-red hover:bg-term-red hover:text-term-bg font-bold text-[9px] uppercase"
            >
              Clear All
            </button>
          </div>

          {/* List targets */}
          <div className="flex-1 overflow-y-auto p-2 flex flex-col gap-1.5 custom-scrollbar">
            {tickers.length === 0 ? (
              <div className="flex-1 flex flex-col items-center justify-center border-2 border-dashed border-term-borderSoft text-term-muted p-8 text-center rounded-sm">
                <span>DRAG TICKERS HERE FROM THE LEFT PANEL</span>
                <span className="text-[10px] mt-1 text-term-amberDim">OR CLICK THEM TO QUICK ADD</span>
              </div>
            ) : (
              tickers.map((t) => (
                <div
                  key={t}
                  className="flex items-center justify-between p-2 border border-term-borderSoft bg-term-bg hover:border-term-red rounded-sm"
                >
                  <div className="flex items-center gap-3">
                    <span className="text-term-amberBright font-bold">{t}</span>
                    <span className="text-term-heading text-[11px]">{t}</span>
                  </div>
                  <button
                    onClick={() => removeTicker(t)}
                    className="text-term-red font-bold hover:scale-115 transition-transform px-1.5"
                  >
                    ✕
                  </button>
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
