import { useQuery } from "@tanstack/react-query";
import { fetchQuote } from "@/lib/api";
import { fmtPrice, fmtPct, fmtVolume } from "@/lib/format";
import { cn } from "@/lib/cn";

export function QR({ symbol }: { symbol: string }) {
  const { data: q, isLoading, error } = useQuery({
    queryKey: ["quote", symbol], queryFn: () => fetchQuote(symbol), refetchInterval: 3000,
  });

  const chg = q?.last_price != null && q?.prev_close != null ? q.last_price - q.prev_close : undefined;
  const chgPct = q?.last_price != null && q?.prev_close != null ? ((q.last_price - q.prev_close) / q.prev_close) * 100 : undefined;
  const dir = chg == null ? "flat" : chg >= 0 ? "up" : "down";

  if (isLoading) return <div className="p-4 text-term-muted uppercase tracking-widest text-[11px]">Loading quote…</div>;
  if (error) return <div className="p-4 text-term-red text-[12px]">{(error as Error).message}</div>;

  return (
    <div className="p-4 grid grid-cols-[minmax(0,1.3fr)_minmax(0,1fr)] gap-8">
      <div className="flex flex-col gap-4">
        <div>
          <div className="sub-header">{q?.name}</div>
          <div className="flex items-baseline gap-4 mt-2">
            <div className={cn("text-5xl num font-bold", dir === "up" && "up", dir === "down" && "down")}>
              {fmtPrice(q?.last_price)}
            </div>
            <div className={cn("text-xl num", dir === "up" && "up", dir === "down" && "down")}>
              {chg == null ? "" : (chg >= 0 ? "+" : "") + fmtPrice(chg)}
              <span className="ml-2">({fmtPct(chgPct)})</span>
            </div>
          </div>
          <div className="sub-header mt-1">{q?.exchange} · {q?.currency} · REFRESHES EVERY 3S</div>
        </div>
        <div className="grid grid-cols-2 gap-x-6 gap-y-1.5 text-[12px]">
          <Row k="OPEN" v={fmtPrice(q?.open)} />
          <Row k="PREV CLOSE" v={fmtPrice(q?.prev_close)} />
          <Row k="DAY HIGH" v={fmtPrice(q?.high)} tone="up" />
          <Row k="DAY LOW" v={fmtPrice(q?.low)} tone="down" />
          <Row k="BID" v={`${fmtPrice(q?.bid)}  ×${q?.bid_size ?? "—"}`} />
          <Row k="ASK" v={`${fmtPrice(q?.ask)}  ×${q?.ask_size ?? "—"}`} />
        </div>
      </div>
      <div className="border-l border-term-border pl-6 flex flex-col gap-1.5 text-[12px]">
        <Row k="VOLUME" v={fmtVolume(q?.volume)} />
        <Row k="AVG VOL" v={fmtVolume(q?.volume_average)} />
        <Row k="52W HIGH" v={fmtPrice(q?.year_high)} />
        <Row k="52W LOW" v={fmtPrice(q?.year_low)} />
        <Row k="MA 50D" v={fmtPrice(q?.ma_50d)} />
        <Row k="MA 200D" v={fmtPrice(q?.ma_200d)} />
      </div>
    </div>
  );
}

function Row({ k, v, tone }: { k: string; v: React.ReactNode; tone?: "up" | "down" }) {
  return (
    <>
      <div className="sub-header py-0.5">{k}</div>
      <div className={cn("num text-right py-0.5", tone === "up" && "up", tone === "down" && "down")}>{v}</div>
    </>
  );
}
