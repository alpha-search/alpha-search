"use client";

import * as React from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Activity, Search } from "lucide-react";
import { Button } from "@/components/ui/button";
import { tokenStore } from "@/lib/api";

export function Navbar() {
  const router = useRouter();
  const [query, setQuery] = React.useState("");
  const [authed, setAuthed] = React.useState(false);

  React.useEffect(() => {
    setAuthed(Boolean(tokenStore.access));
  }, []);

  function onSearch(e: React.FormEvent) {
    e.preventDefault();
    const sym = query.trim().toUpperCase().replace(/^\$/, "");
    if (sym) router.push(`/ticker/${sym}`);
  }

  return (
    <header className="sticky top-0 z-40 border-b border-border bg-background/80 backdrop-blur">
      <div className="mx-auto flex h-14 max-w-7xl items-center gap-4 px-4 lg:px-8">
        <Link href="/" className="flex items-center gap-2 font-bold">
          <Activity className="h-5 w-5 text-brand" />
          AlphaPulse
        </Link>

        <form onSubmit={onSearch} className="relative ml-2 hidden flex-1 sm:block">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted" />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search ticker — e.g. AAPL"
            className="h-9 w-full max-w-xs rounded-lg border border-border bg-surface pl-9 pr-3 text-sm outline-none focus:border-brand"
          />
        </form>

        <nav className="ml-auto flex items-center gap-2">
          <Link href="/pricing" className="text-sm text-muted hover:text-foreground">
            Pricing
          </Link>
          {authed ? (
            <Button
              variant="outline"
              size="sm"
              onClick={() => {
                tokenStore.clear();
                setAuthed(false);
                router.refresh();
              }}
            >
              Sign out
            </Button>
          ) : (
            <Link href="/login">
              <Button size="sm">Sign in</Button>
            </Link>
          )}
        </nav>
      </div>
    </header>
  );
}
