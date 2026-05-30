import { useQuery } from "@tanstack/react-query";
import { fetchNewsCompany } from "@/lib/api";
import { fmtTime } from "@/lib/format";
import { ExternalLink } from "lucide-react";

export function NI({ symbol }: { symbol: string }) {
  const { data = [], isLoading, error } = useQuery({
    queryKey: ["news", symbol], queryFn: () => fetchNewsCompany(symbol, 50),
    staleTime: 60_000,
  });

  if (isLoading) return <div className="p-4 text-term-muted uppercase text-[11px] tracking-widest">Loading…</div>;
  if (error) return <div className="p-4 text-term-red">{(error as Error).message}</div>;

  return (
    <div className="divide-y divide-term-borderSoft text-[12px]">
      {data.map((n, i) => (
        <a
          key={n.id + i}
          href={n.url}
          target="_blank"
          rel="noreferrer noopener"
          className="flex items-start gap-3 px-4 py-2 hover:bg-term-amberSubtle group"
        >
          <div className="num text-term-muted w-28 shrink-0">{fmtTime(n.date)}</div>
          <div className="flex-1 min-w-0">
            <div className="text-term-heading group-hover:text-term-amber leading-snug">{n.title}</div>
            {n.summary && <div className="text-term-muted mt-0.5 line-clamp-2">{n.summary}</div>}
            <div className="text-term-muted text-[10px] uppercase tracking-widest mt-0.5">{n.source}</div>
          </div>
          <ExternalLink size={12} className="text-term-muted group-hover:text-term-amber mt-1 shrink-0" />
        </a>
      ))}
      {data.length === 0 && <div className="p-4 text-term-muted">No news.</div>}
    </div>
  );
}
