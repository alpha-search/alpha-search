"use client";

import * as React from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { api, tokenStore, ApiRequestError } from "@/lib/api";

export default function LoginPage() {
  return (
    <React.Suspense fallback={null}>
      <LoginForm />
    </React.Suspense>
  );
}

function LoginForm() {
  const router = useRouter();
  const params = useSearchParams();
  const next = params.get("next") ?? "/";

  const [mode, setMode] = React.useState<"login" | "register">("login");
  const [email, setEmail] = React.useState("");
  const [password, setPassword] = React.useState("");
  const [displayName, setDisplayName] = React.useState("");
  const [error, setError] = React.useState<string | null>(null);
  const [pending, setPending] = React.useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setPending(true);
    try {
      const pair =
        mode === "login"
          ? await api.login({ email, password })
          : await api.register({ email, password, display_name: displayName });
      tokenStore.set(pair);
      router.push(next);
      router.refresh();
    } catch (err) {
      setError(err instanceof ApiRequestError ? err.message : "Authentication failed");
    } finally {
      setPending(false);
    }
  }

  return (
    <main className="mx-auto max-w-md px-4 py-16">
      <Card>
        <CardContent className="p-6">
          <h1 className="text-xl font-bold">
            {mode === "login" ? "Sign in to AlphaPulse" : "Create your account"}
          </h1>

          <form onSubmit={submit} className="mt-6 space-y-4">
            {mode === "register" && (
              <input
                value={displayName}
                onChange={(e) => setDisplayName(e.target.value)}
                placeholder="Display name"
                required
                className="h-10 w-full rounded-lg border border-border bg-surface-2 px-3 text-sm outline-none focus:border-brand"
              />
            )}
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="Email"
              required
              className="h-10 w-full rounded-lg border border-border bg-surface-2 px-3 text-sm outline-none focus:border-brand"
            />
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Password (min 8 chars)"
              minLength={8}
              required
              className="h-10 w-full rounded-lg border border-border bg-surface-2 px-3 text-sm outline-none focus:border-brand"
            />

            {error && <p className="text-sm text-bear">{error}</p>}

            <Button type="submit" className="w-full" disabled={pending}>
              {pending ? "Please wait…" : mode === "login" ? "Sign in" : "Create account"}
            </Button>
          </form>

          <button
            onClick={() => setMode(mode === "login" ? "register" : "login")}
            className="mt-4 text-sm text-muted hover:text-foreground"
          >
            {mode === "login"
              ? "Need an account? Register"
              : "Already have an account? Sign in"}
          </button>

          <p className="mt-4 rounded-lg bg-surface-2 p-3 text-xs text-muted">
            Demo: <span className="text-foreground">contributor@alphapulse.io</span> /{" "}
            <span className="text-foreground">password123</span>
          </p>
        </CardContent>
      </Card>
    </main>
  );
}
