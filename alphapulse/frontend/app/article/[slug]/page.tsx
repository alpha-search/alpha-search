import { notFound } from "next/navigation";
import Link from "next/link";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import { api, ApiRequestError } from "@/lib/api";
import type { ArticleDetail } from "@/lib/types";
import { Card, CardContent } from "@/components/ui/card";
import { buttonVariants } from "@/components/ui/button";

interface PageProps {
  params: { slug: string };
}

/**
 * Article reader. The backend returns the full body for entitled viewers and a
 * truncated free preview (with `is_locked: true`) otherwise, so the paywall is
 * enforced server-side — the premium body is never shipped to a locked client.
 */
export default async function ArticlePage({ params }: PageProps) {
  let article: ArticleDetail;
  try {
    article = await api.getArticle(params.slug);
  } catch (err) {
    if (err instanceof ApiRequestError && err.status === 404) notFound();
    throw err;
  }

  return (
    <main className="mx-auto max-w-3xl px-4 py-10 lg:px-0">
      <div className="mb-6 flex flex-wrap items-center gap-2">
        {article.access_level !== "public" && (
          <span className="rounded bg-brand/15 px-2 py-0.5 text-xs font-semibold uppercase text-brand">
            {article.access_level}
          </span>
        )}
        {article.tickers.map((t) => (
          <Link
            key={t.symbol}
            href={`/ticker/${t.symbol}`}
            className="rounded bg-surface-2 px-2 py-0.5 text-xs font-medium text-brand hover:underline"
          >
            ${t.symbol}
          </Link>
        ))}
      </div>

      <h1 className="text-3xl font-bold leading-tight tracking-tight">{article.title}</h1>
      <p className="mt-2 text-muted">{article.summary}</p>
      <p className="mt-3 text-sm text-muted">
        by <span className="text-foreground">{article.author.display_name}</span>
        {article.published_at && (
          <> · {new Date(article.published_at).toLocaleDateString()}</>
        )}
      </p>

      <article className="prose-alpha mt-8 text-foreground">
        <ReactMarkdown remarkPlugins={[remarkGfm]}>{article.body_markdown}</ReactMarkdown>
      </article>

      {article.is_locked && (
        <div className="mt-6 rounded-xl border border-brand/40 bg-gradient-to-b from-surface to-background p-8 text-center">
          <h3 className="text-xl font-semibold">Continue reading with AlphaPulse Premium</h3>
          <p className="mx-auto mt-2 max-w-md text-sm text-muted">
            This is a {article.access_level} article. Subscribe to unlock the full analysis,
            financial models, and the author&apos;s price target.
          </p>
          <Link href="/pricing" className={`${buttonVariants({ size: "lg" })} mt-5`}>
            Unlock Full Article
          </Link>
        </div>
      )}

      {/* Required financial disclosure */}
      <Card className="mt-10 border-dashed">
        <CardContent className="p-5">
          <h4 className="text-xs font-semibold uppercase tracking-wide text-muted">Disclosure</h4>
          <p className="mt-2 text-sm text-muted">{article.disclosure}</p>
        </CardContent>
      </Card>
    </main>
  );
}
