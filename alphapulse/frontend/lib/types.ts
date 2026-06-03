// Shared TypeScript domain types — kept in lockstep with the FastAPI Pydantic
// schemas in backend/app/schemas/__init__.py.

export type UserRole = "reader" | "contributor" | "admin";
export type SubscriptionTier = "free" | "premium" | "pro";
export type SubscriptionStatus =
  | "active"
  | "trialing"
  | "past_due"
  | "canceled"
  | "incomplete";
export type ArticleAccess = "public" | "premium" | "pro";
export type ArticleStatus = "draft" | "published" | "archived";
export type AlertCondition = "above" | "below" | "pct_change";
export type Sentiment = "bullish" | "bearish" | "neutral";

export interface User {
  id: string;
  email: string;
  display_name: string;
  role: UserRole;
  avatar_url: string | null;
  created_at: string;
}

export interface TokenPair {
  access_token: string;
  refresh_token: string;
  token_type: "bearer";
}

export interface Subscription {
  tier: SubscriptionTier;
  status: SubscriptionStatus;
  current_period_end: string | null;
  cancel_at_period_end: boolean;
}

export interface TickerProfile {
  symbol: string;
  company_name: string;
  exchange: string | null;
  sector: string | null;
  industry: string | null;
  logo_url: string | null;
  description: string | null;
}

export interface Quote {
  symbol: string;
  price: number;
  change: number;
  change_pct: number;
  day_high: number;
  day_low: number;
  volume: number;
  market_cap: number | null;
  updated_at: string;
}

export interface CandleBar {
  time: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface FinancialStatementRow {
  label: string;
  values: Record<string, number | null>;
}

export interface FinancialStatement {
  statement: "income" | "balance" | "cash_flow";
  currency: string;
  periods: string[];
  rows: FinancialStatementRow[];
}

export interface EarningsMetric {
  date: string;
  eps_estimate: number | null;
  eps_actual: number | null;
  revenue_estimate: number | null;
  revenue_actual: number | null;
}

export interface DividendMetric {
  ex_date: string;
  payment_date: string | null;
  amount: number;
  yield_pct: number | null;
}

export interface ArticleTickerTag {
  symbol: string;
  sentiment: Sentiment | null;
}

export interface ArticleSummary {
  id: string;
  slug: string;
  title: string;
  summary: string;
  access_level: ArticleAccess;
  status: ArticleStatus;
  cover_image_url: string | null;
  tags: string[];
  published_at: string | null;
  author: User;
}

export interface ArticleDetail extends ArticleSummary {
  body_markdown: string;
  disclosure: string;
  free_preview: string;
  tickers: ArticleTickerTag[];
  is_locked: boolean;
}

export interface WatchlistItem {
  id: string;
  symbol: string;
  added_at: string;
}

export interface Watchlist {
  id: string;
  name: string;
  items: WatchlistItem[];
}

export interface Alert {
  id: string;
  symbol: string;
  condition: AlertCondition;
  threshold: number;
  is_active: boolean;
  last_triggered_at: string | null;
}

export interface ApiError {
  detail: string;
  code?: string;
}
