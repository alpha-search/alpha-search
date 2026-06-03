"use client";

import * as React from "react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Card, CardContent } from "@/components/ui/card";
import { PaywallOverlay } from "./paywall-overlay";
import { api, PaywallError } from "@/lib/api";
import type {
  DividendMetric,
  EarningsMetric,
  FinancialStatement,
} from "@/lib/types";
import { formatCurrency, formatFinancialValue } from "@/lib/utils";

type StatementKind = "income" | "balance" | "cash_flow";

interface FinancialTabsProps {
  symbol: string;
}

/**
 * Premium financial data block. Each tab lazily fetches its statement; a 402
 * from the paywalled backend is caught and rendered as an upgrade overlay
 * rather than an error.
 */
export function FinancialTabs({ symbol }: FinancialTabsProps) {
  return (
    <Tabs defaultValue="income" className="w-full">
      <TabsList>
        <TabsTrigger value="income">Income</TabsTrigger>
        <TabsTrigger value="balance">Balance Sheet</TabsTrigger>
        <TabsTrigger value="cash_flow">Cash Flow</TabsTrigger>
        <TabsTrigger value="earnings">Earnings</TabsTrigger>
        <TabsTrigger value="dividends">Dividends</TabsTrigger>
      </TabsList>

      <TabsContent value="income">
        <StatementTable symbol={symbol} statement="income" />
      </TabsContent>
      <TabsContent value="balance">
        <StatementTable symbol={symbol} statement="balance" />
      </TabsContent>
      <TabsContent value="cash_flow">
        <StatementTable symbol={symbol} statement="cash_flow" />
      </TabsContent>
      <TabsContent value="earnings">
        <EarningsTable symbol={symbol} />
      </TabsContent>
      <TabsContent value="dividends">
        <DividendsTable symbol={symbol} />
      </TabsContent>
    </Tabs>
  );
}

/** Generic async loader that converts a PaywallError into the upgrade gate. */
function usePremiumData<T>(loader: () => Promise<T>, deps: React.DependencyList) {
  const [state, setState] = React.useState<{
    data: T | null;
    locked: boolean;
    loading: boolean;
    error: string | null;
  }>({ data: null, locked: false, loading: true, error: null });

  React.useEffect(() => {
    let cancelled = false;
    setState((s) => ({ ...s, loading: true, error: null }));
    loader()
      .then((data) => {
        if (!cancelled) setState({ data, locked: false, loading: false, error: null });
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        if (err instanceof PaywallError) {
          setState({ data: null, locked: true, loading: false, error: null });
        } else {
          setState({
            data: null,
            locked: false,
            loading: false,
            error: err instanceof Error ? err.message : "Failed to load",
          });
        }
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  return state;
}

function LoadingRows() {
  return (
    <div className="space-y-2 p-2">
      {Array.from({ length: 5 }).map((_, i) => (
        <div key={i} className="h-5 w-full animate-pulse rounded bg-surface-2" />
      ))}
    </div>
  );
}

function StatementTable({ symbol, statement }: { symbol: string; statement: StatementKind }) {
  const { data, locked, loading, error } = usePremiumData<FinancialStatement>(
    () => api.financials(symbol, statement),
    [symbol, statement],
  );

  if (loading) return <LoadingRows />;
  if (locked) return <PaywallOverlay />;
  if (error) return <p className="p-4 text-sm text-bear">{error}</p>;
  if (!data) return null;

  return (
    <Card>
      <CardContent className="overflow-x-auto p-0">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border text-muted">
              <th className="px-4 py-3 text-left font-medium">Metric ({data.currency})</th>
              {data.periods.map((p) => (
                <th key={p} className="px-4 py-3 text-right font-medium tabular-nums">
                  {p}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data.rows.map((row) => (
              <tr key={row.label} className="border-b border-border/50 last:border-0">
                <td className="px-4 py-3 text-left">{row.label}</td>
                {data.periods.map((p) => (
                  <td key={p} className="px-4 py-3 text-right tabular-nums">
                    {formatFinancialValue(row.values[p] ?? null)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </CardContent>
    </Card>
  );
}

function EarningsTable({ symbol }: { symbol: string }) {
  const { data, locked, loading, error } = usePremiumData<EarningsMetric[]>(
    () => api.earnings(symbol),
    [symbol],
  );
  if (loading) return <LoadingRows />;
  if (locked) return <PaywallOverlay title="Earnings history" />;
  if (error) return <p className="p-4 text-sm text-bear">{error}</p>;
  if (!data) return null;

  return (
    <Card>
      <CardContent className="overflow-x-auto p-0">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border text-muted">
              {["Date", "EPS Est.", "EPS Actual", "Rev. Est.", "Rev. Actual"].map((h) => (
                <th key={h} className="px-4 py-3 text-right font-medium first:text-left">
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data.map((e) => {
              const beat = (e.eps_actual ?? 0) >= (e.eps_estimate ?? 0);
              return (
                <tr key={e.date} className="border-b border-border/50 last:border-0">
                  <td className="px-4 py-3 text-left">{e.date}</td>
                  <td className="px-4 py-3 text-right tabular-nums">{e.eps_estimate?.toFixed(2) ?? "—"}</td>
                  <td className={`px-4 py-3 text-right tabular-nums ${beat ? "text-bull" : "text-bear"}`}>
                    {e.eps_actual?.toFixed(2) ?? "—"}
                  </td>
                  <td className="px-4 py-3 text-right tabular-nums">{formatFinancialValue(e.revenue_estimate)}</td>
                  <td className="px-4 py-3 text-right tabular-nums">{formatFinancialValue(e.revenue_actual)}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </CardContent>
    </Card>
  );
}

function DividendsTable({ symbol }: { symbol: string }) {
  const { data, locked, loading, error } = usePremiumData<DividendMetric[]>(
    () => api.dividends(symbol),
    [symbol],
  );
  if (loading) return <LoadingRows />;
  if (locked) return <PaywallOverlay title="Dividend metrics" />;
  if (error) return <p className="p-4 text-sm text-bear">{error}</p>;
  if (!data) return null;

  return (
    <Card>
      <CardContent className="overflow-x-auto p-0">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border text-muted">
              {["Ex-Date", "Payment Date", "Amount", "Yield"].map((h) => (
                <th key={h} className="px-4 py-3 text-right font-medium first:text-left">
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data.map((d) => (
              <tr key={d.ex_date} className="border-b border-border/50 last:border-0">
                <td className="px-4 py-3 text-left">{d.ex_date}</td>
                <td className="px-4 py-3 text-right">{d.payment_date ?? "—"}</td>
                <td className="px-4 py-3 text-right tabular-nums">{formatCurrency(d.amount)}</td>
                <td className="px-4 py-3 text-right tabular-nums">
                  {d.yield_pct != null ? `${d.yield_pct.toFixed(2)}%` : "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </CardContent>
    </Card>
  );
}
