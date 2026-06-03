"use client";

import { Lock } from "lucide-react";
import Link from "next/link";
import { buttonVariants } from "@/components/ui/button";

/**
 * Blur-and-CTA overlay shown in place of premium content (financial statements,
 * locked article bodies) when the viewer lacks an active subscription.
 */
export function PaywallOverlay({
  title = "Premium financial data",
  description = "Unlock full financial statements, earnings history, and dividend metrics with an AlphaPulse subscription.",
}: {
  title?: string;
  description?: string;
}) {
  return (
    <div className="relative overflow-hidden rounded-xl border border-border bg-surface">
      {/* Blurred faux content behind the gate */}
      <div aria-hidden className="pointer-events-none select-none space-y-3 p-6 blur-sm">
        {Array.from({ length: 5 }).map((_, i) => (
          <div key={i} className="flex justify-between">
            <div className="h-4 w-40 rounded bg-surface-2" />
            <div className="h-4 w-24 rounded bg-surface-2" />
          </div>
        ))}
      </div>

      <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 bg-background/70 p-6 text-center backdrop-blur-[2px]">
        <div className="flex h-12 w-12 items-center justify-center rounded-full bg-brand/15 text-brand">
          <Lock className="h-6 w-6" />
        </div>
        <h3 className="text-lg font-semibold">{title}</h3>
        <p className="max-w-sm text-sm text-muted">{description}</p>
        <Link href="/pricing" className={buttonVariants()}>
          Upgrade to Premium
        </Link>
      </div>
    </div>
  );
}
