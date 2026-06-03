import { Card, CardContent, CardTitle } from "@/components/ui/card";
import type { Quote, TickerProfile } from "@/lib/types";
import { cn, formatCompact, formatCurrency, formatPercent } from "@/lib/utils";

interface SummaryCardsProps {
  profile: TickerProfile;
  quote: Quote;
}

export function SummaryCards({ profile, quote }: SummaryCardsProps) {
  const up = quote.change >= 0;
  const metrics: { label: string; value: string; accent?: boolean }[] = [
    { label: "Price", value: formatCurrency(quote.price) },
    {
      label: "Change (1D)",
      value: `${formatCurrency(quote.change)} (${formatPercent(quote.change_pct)})`,
      accent: true,
    },
    { label: "Day Range", value: `${formatCurrency(quote.day_low)} – ${formatCurrency(quote.day_high)}` },
    { label: "Volume", value: formatCompact(quote.volume) },
    { label: "Market Cap", value: formatCompact(quote.market_cap) },
    { label: "Sector", value: profile.sector ?? "—" },
  ];

  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
      {metrics.map((m) => (
        <Card key={m.label}>
          <CardContent className="p-4">
            <CardTitle className="text-xs uppercase tracking-wide">{m.label}</CardTitle>
            <p
              className={cn(
                "mt-1 text-lg font-semibold tabular-nums",
                m.accent && (up ? "text-bull" : "text-bear"),
              )}
            >
              {m.value}
            </p>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
