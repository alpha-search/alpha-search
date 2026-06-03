import Link from "next/link";
import { TrendingUp } from "lucide-react";
import { api } from "@/lib/api";
import type { ArticleSummary } from "@/lib/types";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { buttonVariants } from "@/components/ui/button";

const FEATURED = ["AAPL", "MSFT", "NVDA", "TSLA", "AMZN", "GOOGL"];

export default async function HomePage() {
  let articles: ArticleSummary[] = [];
  try {
    articles = await api.listArticles();
  } catch {
    articles = [];
  }

  return (
    <main className="mx-auto max-w-7xl px-4 py-10 lg:px-8">
      <section className="mb-10">
        <h1 className="text-3xl font-bold tracking-tight sm:text-4xl">
          Research that moves <span className="text-brand">before</span> the market.
        </h1>
        <p className="mt-3 max-w-2xl text-muted">
          Deep ticker profiles, crowd-sourced analyst research, and real-time watchlists — all in
          one institutional-grade terminal.
        </p>
      </section>

      <section className="mb-10">
        <h2 className="mb-3 flex items-center gap-2 text-lg font-semibold">
          <TrendingUp className="h-5 w-5 text-brand" /> Featured Tickers
        </h2>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
          {FEATURED.map((sym) => (
            <Link
              key={sym}
              href={`/ticker/${sym}`}
              className="rounded-xl border border-border bg-surface p-4 text-center font-semibold transition-colors hover:border-brand"
            >
              {sym}
            </Link>
          ))}
        </div>
      </section>

      <section>
        <h2 className="mb-3 text-lg font-semibold">Latest Research</h2>
        {articles.length === 0 ? (
          <Card>
            <CardContent className="p-6 text-sm text-muted">
              No articles published yet. Seed the backend with{" "}
              <code className="text-foreground">python -m scripts.seed</code> to populate demo
              research.
            </CardContent>
          </Card>
        ) : (
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
            {articles.map((a) => (
              <Link key={a.id} href={`/article/${a.slug}`}>
                <Card className="h-full transition-colors hover:border-brand">
                  <CardHeader>
                    <div className="flex items-center gap-2">
                      {a.access_level !== "public" && (
                        <span className="rounded bg-brand/15 px-1.5 py-0.5 text-[10px] font-semibold uppercase text-brand">
                          {a.access_level}
                        </span>
                      )}
                      {a.tags.slice(0, 2).map((t) => (
                        <span key={t} className="text-[11px] text-muted">
                          #{t}
                        </span>
                      ))}
                    </div>
                    <CardTitle className="text-base text-foreground">{a.title}</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <p className="line-clamp-2 text-sm text-muted">{a.summary}</p>
                    <p className="mt-3 text-xs text-muted">by {a.author.display_name}</p>
                  </CardContent>
                </Card>
              </Link>
            ))}
          </div>
        )}
      </section>

      <section className="mt-12 rounded-2xl border border-border bg-surface p-8 text-center">
        <h2 className="text-2xl font-bold">Unlock premium research & financials</h2>
        <p className="mx-auto mt-2 max-w-lg text-muted">
          Full financial statements, premium analyst articles, and unlimited price alerts.
        </p>
        <Link href="/pricing" className={`${buttonVariants({ size: "lg" })} mt-5`}>
          View Plans
        </Link>
      </section>
    </main>
  );
}
