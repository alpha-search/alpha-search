import { useQueries } from "@tanstack/react-query";
import { fetchIndexHistorical } from "@/lib/api";
import { fmtPrice, fmtPct } from "@/lib/format";
import { cn } from "@/lib/cn";

const INDICES = [
  { sym: "^GSPC",   name: "S&P 500",       region: "Americas" },
  { sym: "^DJI",    name: "Dow Jones",     region: "Americas" },
  { sym: "^IXIC",   name: "NASDAQ Comp",   region: "Americas" },
  { sym: "^RUT",    name: "Russell 2000",  region: "Americas" },
  { sym: "^GSPTSE", name: "TSX Comp",      region: "Americas" },
  { sym: "^BVSP",   name: "Bovespa",       region: "Americas" },
  { sym: "^FTSE",   name: "FTSE 100",      region: "EMEA" },
  { sym: "^GDAXI",  name: "DAX",           region: "EMEA" },
  { sym: "^FCHI",   name: "CAC 40",        region: "EMEA" },
  { sym: "^STOXX50E", name: "Euro Stoxx 50", region: "EMEA" },
  { sym: "^IBEX",   name: "IBEX 35",       region: "EMEA" },
  { sym: "^N225",   name: "Nikkei 225",    region: "Asia-Pac" },
  { sym: "^HSI",    name: "Hang Seng",     region: "Asia-Pac" },
  { sym: "^AXJO",   name: "ASX 200",       region: "Asia-Pac" },
  { sym: "^KS11",   name: "KOSPI",         region: "Asia-Pac" },
  { sym: "^TWII",   name: "TAIEX",         region: "Asia-Pac" },
];

export function WEI() {
  const queries = useQueries({
    queries: INDICES.map((idx) => ({
      queryKey: ["index-hist", idx.sym],
      queryFn: () => fetchIndexHistorical(idx.sym, 10),
      refetchInterval: 60_000,
    })),
  });

  const regions = Array.from(new Set(INDICES.map((i) => i.region)));

  return (
    <div className="p-3 flex flex-col gap-4 text-[12px]">
      {regions.map((region) => (
        <div key={region}>
          <div className="text-term-amber text-[10px] tracking-[0.25em] font-bold border-b border-term-border pb-1 mb-2">{region.toUpperCase()}</div>
          <table className="w-full grid-data">
            <thead>
              <tr>
                <th>Index</th>
                <th>Symbol</th>
                <th className="text-right">Last</th>
                <th className="text-right">Day Δ</th>
                <th className="text-right">Δ %</th>
                <th className="text-right">Volume</th>
              </tr>
            </thead>
            <tbody>
              {INDICES.map((idx, i) => {
                if (idx.region !== region) return null;
                const q = queries[i];
                const data = q.data ?? [];
                const last = data[data.length - 1];
                const prev = data[data.length - 2];
                const chg = last && prev ? last.close - prev.close : undefined;
                const chgPct = last && prev ? ((last.close - prev.close) / prev.close) * 100 : undefined;
                const dir = chg == null ? "flat" : chg >= 0 ? "up" : "down";
                return (
                  <tr key={idx.sym}>
                    <td className="text-term-heading">{idx.name}</td>
                    <td className="text-term-muted num">{idx.sym}</td>
                    <td className="num text-right">{q.isLoading ? "…" : fmtPrice(last?.close, 2)}</td>
                    <td className={cn("num text-right", dir === "up" && "up", dir === "down" && "down")}>
                      {chg == null ? "—" : (chg >= 0 ? "+" : "") + fmtPrice(chg, 2)}
                    </td>
                    <td className={cn("num text-right", dir === "up" && "up", dir === "down" && "down")}>
                      {fmtPct(chgPct)}
                    </td>
                    <td className="num text-right text-term-muted">
                      {last?.volume ? (last.volume / 1e9).toFixed(2) + "B" : "—"}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      ))}
      <div className="sub-header">LAST CLOSE COMPARED WITH PREVIOUS SESSION · REFRESHES EVERY 60S</div>
    </div>
  );
}
