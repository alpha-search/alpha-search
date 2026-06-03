"use client";

import * as React from "react";
import { Star } from "lucide-react";
import { Button } from "@/components/ui/button";
import { api, tokenStore, ApiRequestError } from "@/lib/api";

/**
 * Toggles a symbol on the signed-in user's watchlist. Renders a sign-in prompt
 * for anonymous viewers.
 */
export function WatchlistButton({ symbol }: { symbol: string }) {
  const [authed, setAuthed] = React.useState(false);
  const [active, setActive] = React.useState(false);
  const [pending, setPending] = React.useState(false);

  React.useEffect(() => {
    if (!tokenStore.access) return;
    setAuthed(true);
    api
      .watchlist()
      .then((wl) => setActive(wl.items.some((i) => i.symbol === symbol)))
      .catch(() => setAuthed(false));
  }, [symbol]);

  async function toggle() {
    setPending(true);
    try {
      if (active) {
        await api.removeFromWatchlist(symbol);
        setActive(false);
      } else {
        await api.addToWatchlist(symbol);
        setActive(true);
      }
    } catch (err) {
      if (err instanceof ApiRequestError && err.status === 409) setActive(true);
    } finally {
      setPending(false);
    }
  }

  if (!authed) {
    return (
      <Button variant="outline" size="sm" disabled title="Sign in to use watchlists">
        <Star className="h-4 w-4" /> Watch
      </Button>
    );
  }

  return (
    <Button variant={active ? "default" : "outline"} size="sm" onClick={toggle} disabled={pending}>
      <Star className={`h-4 w-4 ${active ? "fill-current" : ""}`} />
      {active ? "Watching" : "Watch"}
    </Button>
  );
}
