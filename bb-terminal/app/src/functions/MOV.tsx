import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { fetchGainers, fetchLosers, fetchMostActive } from "@/lib/api";
import { fmtPrice, fmtPct, fmtVolume } from "@/lib/format";
import { useWorkspace } from "@/store/workspaceStore";
import { cn } from "@/lib/cn";

type Kind = "gainers" | "losers" | "active";
const TABS: { id: Kind; label: string }[] = [
  { id: "gainers", label: "Top Gainers" },
  { id: "losers", label: "Top Losers" },
  { id: "active", label: "Most Active" },
];

export function MOV() {
  const [tab, setTab] = useState<Kind>("gainers");
  const openTab = useWorkspace((s) => s.openTab);

  const { data = [], isLoading, error } = useQuery({
    queryKey: ["movers", tab],
    queryFn: () => tab === "gainers" ? fetchGainers() : tab === "losers" ? fetchLosers() : fetchMostActive(),
    refetchInterval: 60_000,
  });

  return (
    <div className="h-full flex flex-col">
      <div className="flex items-center gap-3 h-8 px-3 border-b border-term-border bg-term-panel2 text-[11px] uppercase tracking-wider">
        {TABS.map((t) => (
          <button key={t.id} onClick={() => setTab(t.id)}
            className={cn("px-2 py-0.5 border",
              tab === t.id ? "border-term-amber text-term-amber" : "border-transparent text-term-muted hover:text-term-text")}>
            {t.label}
          </button>
        ))}
        <span className="ml-auto text-term-muted">{data.length} rows · src: yfinance</span>
      </div>
      <div className="flex-1 overflow-auto scroll-thin">
        {isLoading && <div className="p-4 text-term-muted uppercase text-[11px] tracking-widest">Loading…</div>}
        {error && <div className="p-4 text-term-red">{(error as Error).message}</div>}
        {!isLoading && !error && (
          <table className="w-full text-[12px] grid-data">
            <thead>
              <tr>
                <th>#</th>
                <th>Symbol</th>
                <th>Name</th>
                <th className="text-right">Price</th>
                <th className="text-right">Chg</th>
                <th className="text-right">Chg %</th>
                <th className="text-right">Volume</th>
                <th className="text-right">Mkt Cap</th>
                <th className="text-right">P/E fwd</th>
              </tr>
            </thead>
            <tbody>
              {data.slice(0, 100).map((m, i) => {
                const dir = m.percent_change >= 0 ? "up" : "down";
                return (
                  <tr key={m.symbol} className="cursor-pointer" onClick={() => openTab("DES", m.symbol)}>
                    <td className="text-term-muted num">{i + 1}</td>
                    <td className="num text-term-amber font-semibold">{m.symbol}</td>
                    <td className="truncate max-w-[260px] text-term-heading">{m.name}</td>
                    <td className="num text-right">{fmtPrice(m.price)}</td>
                    <td className={cn("num text-right", dir === "up" ? "up" : "down")}>
                      {(m.change >= 0 ? "+" : "") + fmtPrice(m.change)}
                    </td>
                    <td className={cn("num text-right", dir === "up" ? "up" : "down")}>
                      {fmtPct(m.percent_change * 100)}
                    </td>
                    <td className="num text-right text-term-muted">{fmtVolume(m.volume)}</td>
                    <td className="num text-right text-term-muted">{fmtVolume(m.market_cap)}</td>
                    <td className="num text-right text-term-muted">{m.pe_forward?.toFixed(1) ?? "—"}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>
      <div className="px-3 py-1 border-t border-term-border sub-header">CLICK A ROW TO OPEN DES</div>
    </div>
  );
}
