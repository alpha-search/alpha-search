import { notFound } from "next/navigation";
import Image from "next/image";
import Link from "next/link";
import type { Metadata } from "next";

import { api, ApiRequestError } from "@/lib/api";
import type { ArticleSummary, CandleBar, Quote, TickerProfile } from "@/lib/types";
import { cn, formatCurrency, formatPercent } from "@/lib/utils";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { PriceChart } from "@/components/ticker/price-chart";
import { SummaryCards } from "@/components/ticker/summary-cards";
import { FinancialTabs } from "@/components/ticker/financial-tabs";
import { WatchlistButton } from "@/components/ticker/watchlist-button";

interface PageProps {
  params: { symbol: string };
}

export async function generateMetadata({ params }: PageProps): Promise<Metadata> {
  const symbol = params.symbol.toUpperCase();
  try {
    const profile = await api.profile(symbol);
    return {
      title: `${symbol} · ${profile.company_name} — AlphaPulse`,
      description: profile.description ?? `${symbol} quote, charts, and financials on AlphaPulse.`,
    };
  } catch {
    return { title: `${symbol} — AlphaPulse` };
  }
}

/**
 * Ticker profile dashboard.
 *
 * Server-rendered shell: profile, quote, chart candles, and related research are
 * fetched on the server (each Redis-cached on the backend). Interactive pieces
 * — the Lightweight Charts canvas, the paywalled financial tabs, and the
 * watchlist toggle — hydrate on the client.
 */
export default async function TickerPage({ params }: PageProps) {
  const symbol = params.symbol.toUpperCase();

  let profile: TickerProfile;
  let quote: Quote;
  let candles: CandleBar[];
  let articles: ArticleSummary[] = [];

  try {
    [profile, quote, candles] = await Promise.all([
      api.profile(symbol),
      api.quote(symbol),
      api.candles(symbol, 365),
    ]);
  } catch (err) {
    if (err instanceof ApiRequestError && err.status === 404) notFound();
    throw err;
  }

  // Related research is best-effort; never fail the page over it.
  try {
    articles = await api.listArticles(symbol);
  } catch {
    articles = [];
  }

  const up = quote.change >= 0;

  return (
    <main className="mx-auto max-w-7xl px-4 py-6 lg:px-8">
      {/* Header */}
      <header className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-4">
          {profile.logo_url ? (
            <Image
              src={profile.logo_url}
              alt={`${symbol} logo`}
              width={56}
              height={56}
              className="rounded-lg border border-border bg-surface"
              unoptimized
            />
          ) : (
            <div className="flex h-14 w-14 items-center justify-center rounded-lg border border-border bg-surface text-lg font-bold">
              {symbol.slice(0, 2)}
            </div>
          )}
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-2xl font-bold tracking-tight">{symbol}</h1>
              {profile.exchange && (
                <span className="rounded bg-surface-2 px-2 py-0.5 text-xs text-muted">
                  {profile.exchange}
                </span>
              )}
            </div>
            <p className="text-sm text-muted">{profile.company_name}</p>
          </div>
        </div>

        <div className="flex items-center gap-4">
          <div className="text-right">
            <p className="text-2xl font-semibold tabular-nums">{formatCurrency(quote.price)}</p>
            <p className={cn("text-sm font-medium tabular-nums", up ? "text-bull" : "text-bear")}>
              {formatCurrency(quote.change)} ({formatPercent(quote.change_pct)})
            </p>
          </div>
          <WatchlistButton symbol={symbol} />
        </div>
      </header>

      {/* Summary metric cards */}
      <section className="mt-6">
        <SummaryCards profile={profile} quote={quote} />
      </section>

      {/* Chart + content grid */}
      <div className="mt-6 grid grid-cols-1 gap-6 lg:grid-cols-3">
        <div className="space-y-6 lg:col-span-2">
          <Card>
            <CardHeader>
              <CardTitle className="text-base text-foreground">Price — 1Y Daily</CardTitle>
            </CardHeader>
            <CardContent>
              <PriceChart candles={candles} />
            </CardContent>
          </Card>

          <section>
            <h2 className="mb-3 text-lg font-semibold">Financials</h2>
            <FinancialTabs symbol={symbol} />
          </section>
        </div>

        {/* Sidebar: company profile + related research */}
        <aside className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle className="text-base text-foreground">About {profile.company_name}</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3 text-sm text-muted">
              <p className="leading-relaxed">{profile.description}</p>
              <dl className="grid grid-cols-2 gap-2 pt-2">
                <div>
                  <dt className="text-xs uppercase tracking-wide">Sector</dt>
                  <dd className="text-foreground">{profile.sector ?? "—"}</dd>
                </div>
                <div>
                  <dt className="text-xs uppercase tracking-wide">Industry</dt>
                  <dd className="text-foreground">{profile.industry ?? "—"}</dd>
                </div>
              </dl>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-base text-foreground">Related Research</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              {articles.length === 0 ? (
                <p className="text-sm text-muted">No analyst coverage yet for {symbol}.</p>
              ) : (
                articles.map((a) => (
                  <Link
                    key={a.id}
                    href={`/article/${a.slug}`}
                    className="block rounded-lg border border-border bg-surface-2 p-3 transition-colors hover:border-brand"
                  >
                    <div className="flex items-center gap-2">
                      {a.access_level !== "public" && (
                        <span className="rounded bg-brand/15 px-1.5 py-0.5 text-[10px] font-semibold uppercase text-brand">
                          {a.access_level}
                        </span>
                      )}
                      <span className="text-sm font-medium leading-snug">{a.title}</span>
                    </div>
                    <p className="mt-1 line-clamp-2 text-xs text-muted">{a.summary}</p>
                    <p className="mt-1 text-xs text-muted">by {a.author.display_name}</p>
                  </Link>
                ))
              )}
            </CardContent>
          </Card>
        </aside>
      </div>
    </main>
  );
}
