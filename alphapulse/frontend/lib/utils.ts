import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

/** Tailwind-aware className combiner (shadcn/ui convention). */
export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}

const _compact = new Intl.NumberFormat("en-US", {
  notation: "compact",
  maximumFractionDigits: 2,
});
const _currency = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

export function formatCompact(value: number | null | undefined): string {
  if (value == null) return "—";
  return _compact.format(value);
}

export function formatCurrency(value: number | null | undefined): string {
  if (value == null) return "—";
  return _currency.format(value);
}

export function formatPercent(value: number | null | undefined): string {
  if (value == null) return "—";
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toFixed(2)}%`;
}

export function formatFinancialValue(value: number | null): string {
  if (value == null) return "—";
  if (Math.abs(value) >= 1_000) return formatCompact(value);
  return value.toFixed(2);
}
