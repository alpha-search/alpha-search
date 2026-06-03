// Typed API client for the AlphaPulse FastAPI backend.
//
// Works on both the server (RSC / route handlers) and the client. Access tokens
// are read from localStorage in the browser and may be passed explicitly on the
// server. A 402 surfaces as `PaywallError` so the UI can render an upgrade CTA
// instead of a generic failure.

import type {
  Alert,
  ArticleDetail,
  ArticleSummary,
  CandleBar,
  DividendMetric,
  EarningsMetric,
  FinancialStatement,
  Quote,
  Subscription,
  TickerProfile,
  TokenPair,
  User,
  Watchlist,
  WatchlistItem,
} from "./types";

// On the server (RSC / route handlers) we must call the backend with an
// absolute URL; in the browser we go through the Next.js rewrite proxy.
const API_BASE =
  typeof window === "undefined"
    ? `${process.env.BACKEND_URL ?? "http://localhost:8000"}/api/v1`
    : process.env.NEXT_PUBLIC_API_BASE ?? "/api/backend";

const ACCESS_KEY = "alphapulse.access";
const REFRESH_KEY = "alphapulse.refresh";

export class ApiRequestError extends Error {
  constructor(
    public readonly status: number,
    message: string,
    public readonly code?: string,
  ) {
    super(message);
    this.name = "ApiRequestError";
  }
}

export class PaywallError extends ApiRequestError {
  constructor(message = "An active subscription is required") {
    super(402, message, "subscription_required");
    this.name = "PaywallError";
  }
}

export const tokenStore = {
  get access(): string | null {
    if (typeof window === "undefined") return null;
    return window.localStorage.getItem(ACCESS_KEY);
  },
  get refresh(): string | null {
    if (typeof window === "undefined") return null;
    return window.localStorage.getItem(REFRESH_KEY);
  },
  set(pair: TokenPair) {
    if (typeof window === "undefined") return;
    window.localStorage.setItem(ACCESS_KEY, pair.access_token);
    window.localStorage.setItem(REFRESH_KEY, pair.refresh_token);
  },
  clear() {
    if (typeof window === "undefined") return;
    window.localStorage.removeItem(ACCESS_KEY);
    window.localStorage.removeItem(REFRESH_KEY);
  },
};

interface RequestOptions extends RequestInit {
  token?: string | null;
  /** Skip the automatic refresh-and-retry on 401 (used by auth calls). */
  noRetry?: boolean;
}

async function request<T>(path: string, opts: RequestOptions = {}): Promise<T> {
  const { token, noRetry, headers, ...init } = opts;
  const bearer = token ?? tokenStore.access;

  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(bearer ? { Authorization: `Bearer ${bearer}` } : {}),
      ...headers,
    },
    cache: "no-store",
  });

  if (res.status === 401 && !noRetry && tokenStore.refresh) {
    const refreshed = await tryRefresh();
    if (refreshed) {
      return request<T>(path, { ...opts, token: refreshed.access_token, noRetry: true });
    }
  }

  if (res.status === 402) {
    const body = await res.json().catch(() => ({ detail: "Subscription required" }));
    throw new PaywallError(body.detail);
  }

  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }));
    throw new ApiRequestError(res.status, body.detail ?? "Request failed", body.code);
  }

  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

async function tryRefresh(): Promise<TokenPair | null> {
  const refresh = tokenStore.refresh;
  if (!refresh) return null;
  try {
    const pair = await request<TokenPair>("/auth/refresh", {
      method: "POST",
      body: JSON.stringify({ refresh_token: refresh }),
      noRetry: true,
    });
    tokenStore.set(pair);
    return pair;
  } catch {
    tokenStore.clear();
    return null;
  }
}

// --- Typed endpoint surface ------------------------------------------------ //
export const api = {
  // Auth
  register: (body: { email: string; password: string; display_name: string }) =>
    request<TokenPair>("/auth/register", { method: "POST", body: JSON.stringify(body) }),
  login: (body: { email: string; password: string }) =>
    request<TokenPair>("/auth/login", { method: "POST", body: JSON.stringify(body) }),
  me: (token?: string) => request<User>("/auth/me", { token }),

  // Tickers (public)
  profile: (symbol: string) => request<TickerProfile>(`/tickers/${symbol}/profile`),
  quote: (symbol: string) => request<Quote>(`/tickers/${symbol}/quote`),
  candles: (symbol: string, days = 365) =>
    request<CandleBar[]>(`/tickers/${symbol}/candles?days=${days}`),

  // Metrics (premium, may throw PaywallError)
  financials: (symbol: string, statement: "income" | "balance" | "cash_flow", token?: string) =>
    request<FinancialStatement>(`/metrics/${symbol}/financials/${statement}`, { token }),
  earnings: (symbol: string, token?: string) =>
    request<EarningsMetric[]>(`/metrics/${symbol}/earnings`, { token }),
  dividends: (symbol: string, token?: string) =>
    request<DividendMetric[]>(`/metrics/${symbol}/dividends`, { token }),

  // Articles
  listArticles: (symbol?: string) =>
    request<ArticleSummary[]>(`/articles${symbol ? `?symbol=${symbol}` : ""}`),
  getArticle: (slug: string, token?: string) =>
    request<ArticleDetail>(`/articles/${slug}`, { token }),

  // Subscriptions
  mySubscription: (token?: string) => request<Subscription>("/subscriptions/me", { token }),
  checkout: (body: { tier: "premium" | "pro"; success_url: string; cancel_url: string }) =>
    request<{ checkout_url: string; session_id: string }>("/subscriptions/checkout", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  confirmMock: (tier: "premium" | "pro") =>
    request<Subscription>(`/subscriptions/confirm-mock?tier=${tier}`, { method: "POST" }),

  // Watchlist & alerts
  watchlist: () => request<Watchlist>("/watchlist"),
  watchlistQuotes: () => request<Quote[]>("/watchlist/quotes"),
  addToWatchlist: (symbol: string) =>
    request<WatchlistItem>("/watchlist/items", {
      method: "POST",
      body: JSON.stringify({ symbol }),
    }),
  removeFromWatchlist: (symbol: string) =>
    request<void>(`/watchlist/items/${symbol}`, { method: "DELETE" }),
  listAlerts: () => request<Alert[]>("/watchlist/alerts"),
  createAlert: (body: { symbol: string; condition: string; threshold: number }) =>
    request<Alert>("/watchlist/alerts", { method: "POST", body: JSON.stringify(body) }),
  deleteAlert: (id: string) => request<void>(`/watchlist/alerts/${id}`, { method: "DELETE" }),
};
