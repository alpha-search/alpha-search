import { useEffect, useRef, useState } from "react";
import { createChart, ColorType, type IChartApi, type ISeriesApi, type UTCTimestamp } from "lightweight-charts";
import { useQuery } from "@tanstack/react-query";
import { fetchHistorical } from "@/lib/api";
import { cn } from "@/lib/cn";

const RANGES = [
  { label: "1M", days: 30, interval: "1d" },
  { label: "3M", days: 90, interval: "1d" },
  { label: "6M", days: 180, interval: "1d" },
  { label: "1Y", days: 365, interval: "1d" },
  { label: "3Y", days: 365 * 3, interval: "1W" },
  { label: "5Y", days: 365 * 5, interval: "1W" },
];

export function GP({ symbol }: { symbol: string }) {
  const [range, setRange] = useState(RANGES[3]);
  const start = new Date(Date.now() - range.days * 864e5).toISOString().slice(0, 10);
  const { data, isLoading, error } = useQuery({
    queryKey: ["historical", symbol, range.label],
    queryFn: () => fetchHistorical(symbol, { interval: range.interval, start_date: start }),
    staleTime: 60_000,
  });

  const ref = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const candleRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const volRef = useRef<ISeriesApi<"Histogram"> | null>(null);

  useEffect(() => {
    if (!ref.current) return;
    const chart = createChart(ref.current, {
      layout: { background: { type: ColorType.Solid, color: "transparent" }, textColor: "#8a8a8a", fontFamily: "JetBrains Mono, monospace", fontSize: 11 },
      rightPriceScale: { borderColor: "#2a2a2a" },
      timeScale: { borderColor: "#2a2a2a", timeVisible: false },
      grid: { vertLines: { color: "rgba(42,42,42,0.5)" }, horzLines: { color: "rgba(42,42,42,0.5)" } },
      crosshair: {
        vertLine: { color: "#ff8c00", width: 1, style: 3, labelBackgroundColor: "#ff8c00" },
        horzLine: { color: "#ff8c00", width: 1, style: 3, labelBackgroundColor: "#ff8c00" },
      },
      autoSize: true,
    });
    const candle = chart.addCandlestickSeries({
      upColor: "#22ee22", downColor: "#ff3b3b",
      wickUpColor: "#22ee22", wickDownColor: "#ff3b3b",
      borderVisible: false,
    });
    const vol = chart.addHistogramSeries({ color: "rgba(255,140,0,0.3)", priceFormat: { type: "volume" }, priceScaleId: "" });
    vol.priceScale().applyOptions({ scaleMargins: { top: 0.82, bottom: 0 } });
    candle.priceScale().applyOptions({ scaleMargins: { top: 0.05, bottom: 0.22 } });
    chartRef.current = chart;
    candleRef.current = candle;
    volRef.current = vol;
    return () => { chart.remove(); chartRef.current = null; };
  }, []);

  useEffect(() => {
    if (!data || !candleRef.current || !volRef.current) return;
    const candles = data.map((c) => ({
      time: Math.floor(new Date(c.date).getTime() / 1000) as UTCTimestamp,
      open: c.open, high: c.high, low: c.low, close: c.close,
    }));
    const vols = data.map((c) => ({
      time: Math.floor(new Date(c.date).getTime() / 1000) as UTCTimestamp,
      value: c.volume,
      color: c.close >= c.open ? "rgba(34,238,34,0.35)" : "rgba(255,59,59,0.35)",
    }));
    candleRef.current.setData(candles);
    volRef.current.setData(vols);
    chartRef.current?.timeScale().fitContent();
  }, [data]);

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center justify-between px-3 h-8 border-b border-term-border bg-term-panel2">
        <div className="flex items-center gap-4 text-[11px] uppercase tracking-wider">
          <span className="text-term-amber">RANGE</span>
          {RANGES.map((r) => (
            <button key={r.label} onClick={() => setRange(r)}
              className={cn("px-1 py-0.5 border",
                r.label === range.label
                  ? "border-term-amber text-term-amber"
                  : "border-transparent text-term-muted hover:text-term-text")}>
              {r.label}
            </button>
          ))}
        </div>
      </div>
      <div className="relative flex-1">
        <div ref={ref} className="absolute inset-0" />
        {isLoading && <Centered>LOADING…</Centered>}
        {error && <Centered error>{(error as Error).message}</Centered>}
      </div>
    </div>
  );
}

function Centered({ children, error }: { children: React.ReactNode; error?: boolean }) {
  return <div className={cn("absolute inset-0 flex items-center justify-center text-[11px] uppercase tracking-widest", error ? "text-term-red" : "text-term-muted")}>{children}</div>;
}
