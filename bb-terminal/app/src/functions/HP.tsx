import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { fetchHistorical } from "@/lib/api";
import { fmtPrice, fmtVolume, fmtDate, fmtPct } from "@/lib/format";
import { cn } from "@/lib/cn";

const RANGES = [
  { label: "1M", days: 30 },
  { label: "3M", days: 90 },
  { label: "6M", days: 180 },
  { label: "1Y", days: 365 },
  { label: "5Y", days: 365 * 5 },
];

export function HP({ symbol }: { symbol: string }) {
  const [range, setRange] = useState(RANGES[1]);
  const start = new Date(Date.now() - range.days * 864e5).toISOString().slice(0, 10);
  const { data = [], isLoading, error } = useQuery({
    queryKey: ["historical-table", symbol, range.label],
    queryFn: () => fetchHistorical(symbol, { start_date: start }),
  });

  const sorted = [...data].sort((a, b) => (a.date < b.date ? 1 : -1));

  return (
    <div className="h-full flex flex-col">
      <div className="flex items-center gap-4 px-3 h-8 border-b border-term-border bg-term-panel2 text-[11px] uppercase tracking-wider">
        <span className="text-term-amber">RANGE</span>
        {RANGES.map((r) => (
          <button key={r.label} onClick={() => setRange(r)}
            className={cn("px-1 py-0.5 border",
              r.label === range.label ? "border-term-amber text-term-amber" : "border-transparent text-term-muted hover:text-term-text")}>
            {r.label}
          </button>
        ))}
        <span className="ml-auto text-term-muted">{sorted.length} rows</span>
      </div>
      <div className="flex-1 overflow-auto scroll-thin">
        {isLoading && <div className="p-4 text-term-muted uppercase text-[11px] tracking-widest">Loading…</div>}
        {error && <div className="p-4 text-term-red">{(error as Error).message}</div>}
        {!isLoading && !error && (
          <table className="w-full text-[12px] grid-data">
            <thead>
              <tr>
                <th>Date</th>
                <th className="text-right">Open</th>
                <th className="text-right">High</th>
                <th className="text-right">Low</th>
                <th className="text-right">Close</th>
                <th className="text-right">Δ%</th>
                <th className="text-right">Volume</th>
              </tr>
            </thead>
            <tbody>
              {sorted.map((r, i) => {
                const prev = sorted[i + 1];
                const chg = prev ? ((r.close - prev.close) / prev.close) * 100 : undefined;
                return (
                  <tr key={r.date}>
                    <td className="num">{fmtDate(r.date)}</td>
                    <td className="num text-right">{fmtPrice(r.open)}</td>
                    <td className="num text-right up">{fmtPrice(r.high)}</td>
                    <td className="num text-right down">{fmtPrice(r.low)}</td>
                    <td className="num text-right text-term-heading">{fmtPrice(r.close)}</td>
                    <td className={cn("num text-right", chg != null && (chg >= 0 ? "up" : "down"))}>{fmtPct(chg)}</td>
                    <td className="num text-right text-term-muted">{fmtVolume(r.volume)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
