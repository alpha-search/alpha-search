import { useQueries, useQuery } from "@tanstack/react-query";
import {
  fetchIndexHistorical, fetchTreasuryRates, fetchFxHistorical, fetchCryptoHistorical,
  fetchGainers, fetchLosers, fetchNewsCompany,
} from "@/lib/api";
import { fmtPrice, fmtPct, fmtTime, fmtPctFromDecimal } from "@/lib/format";
import { useWorkspace } from "@/store/workspaceStore";
import { cn } from "@/lib/cn";

const INDICES = [
  { sym: "^GSPC", name: "S&P 500" },
  { sym: "^DJI",  name: "Dow Jones" },
  { sym: "^IXIC", name: "NASDAQ" },
  { sym: "^RUT",  name: "Russell 2k" },
  { sym: "^VIX",  name: "VIX" },
];

const FX_CRYPTO = [
  { sym: "EURUSD=X", name: "EUR/USD", kind: "fx", digits: 4 },
  { sym: "GBPUSD=X", name: "GBP/USD", kind: "fx", digits: 4 },
  { sym: "USDJPY=X", name: "USD/JPY", kind: "fx", digits: 2 },
  { sym: "BTC-USD",  name: "BTC",     kind: "crypto", digits: 0 },
  { sym: "ETH-USD",  name: "ETH",     kind: "crypto", digits: 0 },
];

function Spark({ values, color = "#ff8c00" }: { values: number[]; color?: string }) {
  if (values.length < 2) return null;
  const min = Math.min(...values), max = Math.max(...values);
  const pts = values.map((v, i) => {
    const x = (i / (values.length - 1)) * 100;
    const y = 28 - ((v - min) / (max - min || 1)) * 24;
    return `${x},${y}`;
  }).join(" ");
  return (
    <svg viewBox="0 0 100 28" className="w-full h-8">
      <polyline fill="none" stroke={color} strokeWidth="1.5" points={pts} />
    </svg>
  );
}

export function CC() {
  const openTab = useWorkspace((s) => s.openTab);

  // Indices
  const idxQueries = useQueries({
    queries: INDICES.map((i) => ({
      queryKey: ["cc-idx", i.sym],
      queryFn: () => fetchIndexHistorical(i.sym, 14),
      refetchInterval: 60_000,
    })),
  });

  // FX + crypto
  const fxQueries = useQueries({
    queries: FX_CRYPTO.map((x) => ({
      queryKey: ["cc-fxc", x.sym],
      queryFn: () => x.kind === "fx"
        ? fetchFxHistorical(x.sym, 14)
        : fetchCryptoHistorical(x.sym, 14),
      refetchInterval: 60_000,
    })),
  });

  // Yield curve
  const curve = useQuery({
    queryKey: ["cc-treasury"], queryFn: () => fetchTreasuryRates(2),
    refetchInterval: 3600_000,
  });
  const today = curve.data?.sort((a, b) => (a.date > b.date ? -1 : 1))[0];

  // Movers
  const gainers = useQuery({ queryKey: ["cc-gainers"], queryFn: fetchGainers, refetchInterval: 120_000 });
  const losers = useQuery({ queryKey: ["cc-losers"], queryFn: fetchLosers, refetchInterval: 120_000 });

  // News — use SPY as macro feed
  const news = useQuery({
    queryKey: ["cc-news"], queryFn: () => fetchNewsCompany("SPY", 12),
    staleTime: 60_000,
  });

  const spread2y10y = today?.year_10 != null && today?.year_2 != null
    ? (today.year_10 - today.year_2) * 100 : undefined;
  const spread3m10y = today?.year_10 != null && today?.month_3 != null
    ? (today.year_10 - today.month_3) * 100 : undefined;
  const curveStatus =
    spread2y10y == null ? { t: "—", tone: "text-term-muted" as const }
    : spread2y10y < 0 ? { t: "INVERTED", tone: "down" as const }
    : spread2y10y < 25 ? { t: "FLAT", tone: "amber" as const }
    : spread2y10y < 100 ? { t: "NORMAL", tone: "up" as const }
    : { t: "STEEP", tone: "up" as const };

  return (
    <div className="p-3 grid gap-3 h-full"
      style={{
        gridTemplateColumns: "minmax(0,2fr) minmax(0,1fr) minmax(0,1fr)",
        gridTemplateRows: "minmax(160px, 1fr) minmax(0,1fr)",
      }}>
      {/* MARKETS */}
      <div className="panel">
        <div className="panel-header">
          <span>US MARKETS</span>
          <span className="sub-header normal-case tracking-normal font-normal">close-over-close · 14d</span>
        </div>
        <div className="grid grid-cols-5 divide-x divide-term-border">
          {INDICES.map((idx, i) => {
            const q = idxQueries[i];
            const data = q.data ?? [];
            const last = data[data.length - 1];
            const prev = data[data.length - 2];
            const chgPct = last && prev ? ((last.close - prev.close) / prev.close) * 100 : undefined;
            const dir = chgPct == null ? "flat" : chgPct >= 0 ? "up" : "down";
            const vals = data.map((d) => d.close);
            return (
              <div key={idx.sym} className="p-2 flex flex-col">
                <div className="sub-header">{idx.name}</div>
                <div className="num text-[16px] text-term-heading mt-1">
                  {q.isLoading ? "…" : last?.close != null ? last.close.toFixed(2) : "—"}
                </div>
                <div className={cn("num text-[11px]", dir === "up" && "up", dir === "down" && "down")}>
                  {fmtPct(chgPct)}
                </div>
                <div className="mt-auto">
                  <Spark values={vals} color={dir === "up" ? "#22ee22" : dir === "down" ? "#ff3b3b" : "#ff8c00"} />
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* YIELD CURVE */}
      <div className="panel cursor-pointer" onClick={() => openTab("CURV")}>
        <div className="panel-header">
          <span>US YIELD CURVE</span>
          <span className={cn("normal-case tracking-normal font-bold text-[11px]",
            curveStatus.tone === "up" && "up", curveStatus.tone === "down" && "down",
            curveStatus.tone === "amber" && "amber", curveStatus.tone.startsWith("text") && curveStatus.tone)}>{curveStatus.t}</span>
        </div>
        <div className="p-3 flex flex-col gap-1.5 text-[11px]">
          <div className="flex items-center justify-between">
            <span className="sub-header">2s-10s SPREAD</span>
            <span className={cn("num font-semibold text-[13px]",
              spread2y10y == null ? "" : spread2y10y >= 0 ? "up" : "down")}>
              {spread2y10y == null ? "—" : `${spread2y10y >= 0 ? "+" : ""}${spread2y10y.toFixed(0)} bps`}
            </span>
          </div>
          <div className="flex items-center justify-between">
            <span className="sub-header">3m-10y SPREAD</span>
            <span className={cn("num font-semibold",
              spread3m10y == null ? "" : spread3m10y >= 0 ? "up" : "down")}>
              {spread3m10y == null ? "—" : `${spread3m10y >= 0 ? "+" : ""}${spread3m10y.toFixed(0)} bps`}
            </span>
          </div>
          <div className="border-t border-term-borderSoft pt-2 mt-1 grid grid-cols-6 gap-1">
            {[["3M","month_3"],["1Y","year_1"],["2Y","year_2"],["5Y","year_5"],["10Y","year_10"],["30Y","year_30"]].map(([l,k]) => (
              <div key={k} className="text-center">
                <div className="sub-header">{l}</div>
                <div className="num text-term-text">
                  {today?.[k as keyof typeof today] != null
                    ? fmtPctFromDecimal(today[k as keyof typeof today] as number, 2)
                    : "—"}
                </div>
              </div>
            ))}
          </div>
          <div className="sub-header mt-1 text-center">CLICK → CURV</div>
        </div>
      </div>

      {/* FX + CRYPTO */}
      <div className="panel">
        <div className="panel-header">
          <span>FX · CRYPTO</span>
          <span className="sub-header normal-case tracking-normal font-normal cursor-pointer hover:text-term-amber"
                onClick={() => openTab("FXC")}>all FX →</span>
        </div>
        <div className="p-2 flex flex-col divide-y divide-term-borderSoft text-[12px]">
          {FX_CRYPTO.map((x, i) => {
            const q = fxQueries[i];
            const data = q.data ?? [];
            const last = data[data.length - 1];
            const prev = data[data.length - 2];
            const chgPct = last && prev ? ((last.close - prev.close) / prev.close) * 100 : undefined;
            const dir = chgPct == null ? "flat" : chgPct >= 0 ? "up" : "down";
            return (
              <div key={x.sym} className="flex items-center gap-2 py-1.5">
                <span className="text-term-amber font-bold text-[11px] w-16">{x.name}</span>
                <span className="num flex-1">
                  {q.isLoading ? "…" : last?.close != null
                    ? last.close.toLocaleString(undefined, { minimumFractionDigits: x.digits, maximumFractionDigits: x.digits })
                    : "—"}
                </span>
                <span className={cn("num text-[11px] w-16 text-right", dir === "up" && "up", dir === "down" && "down")}>
                  {fmtPct(chgPct)}
                </span>
              </div>
            );
          })}
        </div>
      </div>

      {/* GAINERS */}
      <div className="panel">
        <div className="panel-header">
          <span className="up">TOP GAINERS</span>
          <span className="sub-header normal-case tracking-normal font-normal cursor-pointer hover:text-term-amber" onClick={() => openTab("MOV")}>view all →</span>
        </div>
        <div className="flex-1 overflow-auto scroll-thin">
          <table className="w-full text-[12px]">
            <tbody>
              {(gainers.data ?? []).slice(0, 8).map((m, i) => (
                <tr key={m.symbol} onClick={() => openTab("INTEL", m.symbol)}
                    className="cursor-pointer border-b border-term-borderSoft hover:bg-term-amberSubtle">
                  <td className="px-2 py-1 text-term-muted num w-6">{i + 1}</td>
                  <td className="px-2 py-1 num text-term-amber font-semibold w-16">{m.symbol}</td>
                  <td className="px-2 py-1 text-term-heading truncate max-w-[200px]">{m.name}</td>
                  <td className="px-2 py-1 num text-right">{fmtPrice(m.price)}</td>
                  <td className="px-2 py-1 num text-right up w-20">{fmtPct(m.percent_change * 100)}</td>
                </tr>
              ))}
              {gainers.isLoading && <tr><td colSpan={5} className="p-3 text-term-muted">Loading…</td></tr>}
            </tbody>
          </table>
        </div>
        <div className="border-t border-term-border p-1 sub-header text-center">CLICK → INTEL</div>
      </div>

      {/* LOSERS */}
      <div className="panel">
        <div className="panel-header">
          <span className="down">TOP LOSERS</span>
          <span className="sub-header normal-case tracking-normal font-normal cursor-pointer hover:text-term-amber" onClick={() => openTab("MOV")}>view all →</span>
        </div>
        <div className="flex-1 overflow-auto scroll-thin">
          <table className="w-full text-[12px]">
            <tbody>
              {(losers.data ?? []).slice(0, 8).map((m, i) => (
                <tr key={m.symbol} onClick={() => openTab("INTEL", m.symbol)}
                    className="cursor-pointer border-b border-term-borderSoft hover:bg-term-amberSubtle">
                  <td className="px-2 py-1 text-term-muted num w-6">{i + 1}</td>
                  <td className="px-2 py-1 num text-term-amber font-semibold w-16">{m.symbol}</td>
                  <td className="px-2 py-1 text-term-heading truncate max-w-[200px]">{m.name}</td>
                  <td className="px-2 py-1 num text-right">{fmtPrice(m.price)}</td>
                  <td className="px-2 py-1 num text-right down w-20">{fmtPct(m.percent_change * 100)}</td>
                </tr>
              ))}
              {losers.isLoading && <tr><td colSpan={5} className="p-3 text-term-muted">Loading…</td></tr>}
            </tbody>
          </table>
        </div>
        <div className="border-t border-term-border p-1 sub-header text-center">CLICK → INTEL</div>
      </div>

      {/* NEWS */}
      <div className="panel min-h-0">
        <div className="panel-header"><span>MARKET HEADLINES</span></div>
        <div className="flex-1 overflow-auto scroll-thin divide-y divide-term-borderSoft">
          {news.isLoading && <div className="p-3 text-term-muted">Loading…</div>}
          {(news.data ?? []).slice(0, 12).map((n, i) => (
            <a key={n.id + i} href={n.url} target="_blank" rel="noreferrer"
              className="block px-3 py-1.5 hover:bg-term-amberSubtle group">
              <div className="sub-header">{fmtTime(n.date)} · {n.source}</div>
              <div className="text-term-heading group-hover:text-term-amber text-[12px] leading-snug line-clamp-2">{n.title}</div>
            </a>
          ))}
        </div>
      </div>
    </div>
  );
}
