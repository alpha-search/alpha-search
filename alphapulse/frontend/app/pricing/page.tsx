"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { Check } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { api, tokenStore, ApiRequestError } from "@/lib/api";

interface Plan {
  tier: "free" | "premium" | "pro";
  name: string;
  price: string;
  features: string[];
  cta: string;
  highlighted?: boolean;
}

const PLANS: Plan[] = [
  {
    tier: "free",
    name: "Free",
    price: "$0",
    features: ["Live quotes & charts", "Public analyst articles", "1 watchlist"],
    cta: "Current plan",
  },
  {
    tier: "premium",
    name: "Premium",
    price: "$29/mo",
    features: [
      "Everything in Free",
      "Full financial statements",
      "Premium research articles",
      "Unlimited price alerts",
    ],
    cta: "Upgrade to Premium",
    highlighted: true,
  },
  {
    tier: "pro",
    name: "Pro",
    price: "$99/mo",
    features: [
      "Everything in Premium",
      "Pro-only deep-dive research",
      "Earnings & dividend models",
      "Priority data refresh",
    ],
    cta: "Upgrade to Pro",
  },
];

export default function PricingPage() {
  const router = useRouter();
  const [pending, setPending] = React.useState<string | null>(null);
  const [error, setError] = React.useState<string | null>(null);

  async function subscribe(tier: "premium" | "pro") {
    setError(null);
    if (!tokenStore.access) {
      router.push("/login?next=/pricing");
      return;
    }
    setPending(tier);
    try {
      const origin = window.location.origin;
      const { checkout_url } = await api.checkout({
        tier,
        success_url: `${origin}/checkout/success`,
        cancel_url: `${origin}/pricing`,
      });
      // In mock mode the URL is the in-app success route; live mode is Stripe.
      window.location.href = checkout_url;
    } catch (err) {
      setError(err instanceof ApiRequestError ? err.message : "Checkout failed");
      setPending(null);
    }
  }

  return (
    <main className="mx-auto max-w-5xl px-4 py-12 lg:px-8">
      <div className="text-center">
        <h1 className="text-3xl font-bold tracking-tight">Choose your edge</h1>
        <p className="mt-2 text-muted">Cancel anytime. Mock Stripe checkout in development.</p>
      </div>

      {error && <p className="mt-4 text-center text-sm text-bear">{error}</p>}

      <div className="mt-10 grid grid-cols-1 gap-6 md:grid-cols-3">
        {PLANS.map((plan) => (
          <Card
            key={plan.tier}
            className={plan.highlighted ? "border-brand ring-1 ring-brand" : undefined}
          >
            <CardContent className="flex h-full flex-col p-6">
              <h2 className="text-lg font-semibold">{plan.name}</h2>
              <p className="mt-1 text-3xl font-bold">{plan.price}</p>
              <ul className="mt-5 space-y-2 text-sm">
                {plan.features.map((f) => (
                  <li key={f} className="flex items-start gap-2">
                    <Check className="mt-0.5 h-4 w-4 shrink-0 text-brand" />
                    <span className="text-muted">{f}</span>
                  </li>
                ))}
              </ul>
              <div className="mt-6 flex-1" />
              {plan.tier === "free" ? (
                <Button variant="outline" disabled>
                  {plan.cta}
                </Button>
              ) : (
                <Button
                  variant={plan.highlighted ? "default" : "outline"}
                  disabled={pending !== null}
                  onClick={() => subscribe(plan.tier as "premium" | "pro")}
                >
                  {pending === plan.tier ? "Redirecting…" : plan.cta}
                </Button>
              )}
            </CardContent>
          </Card>
        ))}
      </div>
    </main>
  );
}
