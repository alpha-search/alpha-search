const BASE = "/api/v1";

export class ApiError extends Error {
  constructor(public status: number, message: string, public needsKey?: string) {
    super(message);
  }
}

async function get<T>(
  path: string,
  params: Record<string, string | number | boolean | undefined> = {}
): Promise<T> {
  const qs = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== "") qs.set(k, String(v));
  }
  const res = await fetch(`${BASE}${path}?${qs.toString()}`);
  const body = await res.json().catch(() => ({}));
  if (!res.ok) {
    const detail = body.detail;
    let msg = res.statusText;
    let needsKey: string | undefined;
    if (typeof detail === "string") msg = detail;
    else if (Array.isArray(detail)) msg = detail.map((d: any) => d.msg || JSON.stringify(d)).join("; ");
    const m = /credential '([a-z_]+)'/i.exec(msg);
    if (m) needsKey = m[1];
    throw new ApiError(res.status, msg, needsKey);
  }
  return body.results as T;
}

// ────── Equity ──────
export interface Quote {
  symbol: string; name?: string; exchange?: string;
  last_price?: number; open?: number; high?: number; low?: number; prev_close?: number;
  bid?: number; ask?: number; bid_size?: number; ask_size?: number;
  volume?: number; volume_average?: number; year_high?: number; year_low?: number;
  ma_50d?: number; ma_200d?: number; currency?: string;
}
export interface Candle { date: string; open: number; high: number; low: number; close: number; volume: number; }
export interface NewsItem { id: string; date: string; title: string; url: string; source?: string; summary?: string; symbol?: string; }
export interface Profile {
  symbol: string; name?: string; stock_exchange?: string; long_description?: string;
  company_url?: string; business_phone_no?: string;
  hq_address1?: string; hq_address_city?: string; hq_state?: string; hq_country?: string; hq_address_postal_code?: string;
  employees?: number; sector?: string; industry_category?: string; issue_type?: string; currency?: string;
  market_cap?: number; shares_outstanding?: number; shares_float?: number;
  dividend_yield?: number; beta?: number;
}
export interface IncomeRow {
  period_ending: string;
  total_revenue?: number; cost_of_revenue?: number; gross_profit?: number;
  operating_income?: number; total_pre_tax_income?: number; net_income?: number;
  basic_earnings_per_share?: number; diluted_earnings_per_share?: number;
  research_and_development_expense?: number; selling_general_and_admin_expense?: number;
}
export interface Metrics {
  symbol: string; market_cap?: number; pe_ratio?: number; forward_pe?: number; peg_ratio?: number;
  enterprise_to_ebitda?: number; revenue_growth?: number; earnings_growth?: number;
  quick_ratio?: number; current_ratio?: number; debt_to_equity?: number;
  gross_margin?: number; operating_margin?: number; profit_margin?: number;
  return_on_assets?: number; return_on_equity?: number;
  dividend_yield?: number; payout_ratio?: number; book_value?: number; price_to_book?: number;
  enterprise_value?: number;
}
export interface Dividend { ex_dividend_date: string; amount: number; }
export interface ConsensusEstimate {
  symbol: string; target_high?: number; target_low?: number; target_consensus?: number;
  target_median?: number; recommendation?: string; recommendation_mean?: number;
  number_of_analysts?: number; current_price?: number; currency?: string;
}
export interface Mover {
  symbol: string; name?: string; price: number; change: number; percent_change: number;
  volume: number; market_cap?: number; pe_forward?: number; eps_ttm?: number;
  dividend_yield?: number; exchange?: string; earnings_date?: string;
}
export interface SearchResult { symbol: string; name: string; cik?: string; }
export interface OptionsRow {
  underlying_symbol: string; underlying_price?: number; contract_symbol: string;
  expiration: string; dte: number; strike: number; option_type: "call" | "put";
  open_interest?: number; volume?: number; last_trade_price?: number;
  bid?: number; ask?: number; change?: number; change_percent?: number;
  implied_volatility?: number; in_the_money?: boolean;
}
export interface TreasuryRow {
  date: string; month_1?: number; month_3?: number; month_6?: number;
  year_1?: number; year_2?: number; year_3?: number; year_5?: number; year_7?: number;
  year_10?: number; year_20?: number; year_30?: number;
}

// Fetchers
export const fetchQuote = (s: string) =>
  get<Quote[] | Quote>("/equity/price/quote", { symbol: s, provider: "yfinance" })
    .then((r) => (Array.isArray(r) ? r[0] : r));

export const fetchHistorical = (s: string, o: { interval?: string; start_date?: string } = {}) => {
  const start = o.start_date ?? new Date(Date.now() - 365 * 864e5).toISOString().slice(0, 10);
  return get<Candle[]>("/equity/price/historical", {
    symbol: s, provider: "yfinance", interval: o.interval ?? "1d", start_date: start,
  });
};

export const fetchNewsCompany = (s: string, limit = 30) =>
  get<NewsItem[]>("/news/company", { symbol: s, provider: "yfinance", limit });

export const fetchProfile = (s: string) =>
  get<Profile[] | Profile>("/equity/profile", { symbol: s, provider: "yfinance" })
    .then((r) => (Array.isArray(r) ? r[0] : r));

export const fetchIncome = (s: string) =>
  get<IncomeRow[]>("/equity/fundamental/income", {
    symbol: s, provider: "yfinance", period: "annual", limit: 5,
  });

export const fetchMetrics = (s: string) =>
  get<Metrics[] | Metrics>("/equity/fundamental/metrics", { symbol: s, provider: "yfinance" })
    .then((r) => (Array.isArray(r) ? r[0] : r));

export const fetchDividends = (s: string) =>
  get<Dividend[]>("/equity/fundamental/dividends", { symbol: s, provider: "yfinance" });

export const fetchConsensus = (s: string) =>
  get<ConsensusEstimate[] | ConsensusEstimate>("/equity/estimates/consensus", {
    symbol: s, provider: "yfinance",
  }).then((r) => (Array.isArray(r) ? r[0] : r));

export const fetchGainers = () =>
  get<Mover[]>("/equity/discovery/gainers", { provider: "yfinance" });
export const fetchLosers = () =>
  get<Mover[]>("/equity/discovery/losers", { provider: "yfinance" });
export const fetchMostActive = () =>
  get<Mover[]>("/equity/discovery/active", { provider: "yfinance" });

export const fetchOptions = (s: string) =>
  get<OptionsRow[]>("/derivatives/options/chains", { symbol: s, provider: "yfinance" });

export const fetchIndexHistorical = (s: string, days = 30) => {
  const start = new Date(Date.now() - days * 864e5).toISOString().slice(0, 10);
  return get<Candle[]>("/index/price/historical", {
    symbol: s, provider: "yfinance", interval: "1d", start_date: start,
  });
};

export const fetchTreasuryRates = (days = 30) => {
  const start = new Date(Date.now() - days * 864e5).toISOString().slice(0, 10);
  return get<TreasuryRow[]>("/fixedincome/government/treasury_rates", {
    provider: "federal_reserve", start_date: start,
  });
};

export const fetchFxHistorical = (pair: string, days = 30) => {
  const start = new Date(Date.now() - days * 864e5).toISOString().slice(0, 10);
  return get<Candle[]>("/currency/price/historical", {
    symbol: pair, provider: "yfinance", interval: "1d", start_date: start,
  });
};

export const fetchCryptoHistorical = (sym: string, days = 30) => {
  const start = new Date(Date.now() - days * 864e5).toISOString().slice(0, 10);
  return get<Candle[]>("/crypto/price/historical", {
    symbol: sym, provider: "yfinance", interval: "1d", start_date: start,
  });
};

export const searchSymbols = (q: string, limit = 8) =>
  get<SearchResult[]>("/equity/search", { query: q, provider: "sec", limit, is_symbol: false });
