"use client";

import * as React from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { CheckCircle2 } from "lucide-react";
import { api } from "@/lib/api";
import { buttonVariants } from "@/components/ui/button";

/**
 * Post-checkout landing. In mock mode the pricing page redirects here with
 * `?mock=1&tier=...`; we confirm the upgrade against the backend so the user's
 * entitlement is activated immediately. In live mode Stripe's webhook already
 * promoted the account, so this page is purely confirmational.
 */
export default function CheckoutSuccessPage() {
  return (
    <React.Suspense fallback={null}>
      <CheckoutSuccess />
    </React.Suspense>
  );
}

function CheckoutSuccess() {
  const params = useSearchParams();
  const router = useRouter();
  const [status, setStatus] = React.useState<"working" | "done" | "error">("working");

  React.useEffect(() => {
    const mock = params.get("mock");
    const tier = params.get("tier");
    if (mock === "1" && (tier === "premium" || tier === "pro")) {
      api
        .confirmMock(tier)
        .then(() => {
          setStatus("done");
          router.refresh();
        })
        .catch(() => setStatus("error"));
    } else {
      setStatus("done");
    }
  }, [params, router]);

  return (
    <main className="mx-auto flex max-w-md flex-col items-center px-4 py-24 text-center">
      <CheckCircle2 className="h-14 w-14 text-brand" />
      <h1 className="mt-4 text-2xl font-bold">
        {status === "working" ? "Activating your subscription…" : "You're all set!"}
      </h1>
      <p className="mt-2 text-muted">
        {status === "error"
          ? "We couldn't confirm the subscription. Please contact support."
          : "Premium research, full financials, and unlimited alerts are now unlocked."}
      </p>
      <Link href="/" className={`${buttonVariants()} mt-6`}>
        Back to dashboard
      </Link>
    </main>
  );
}
