/**
 * Real API client — talks to the FastAPI backend (backend/app/api/) over
 * the frozen contract in docs/build-plan.md section 5. This replaces the
 * in-browser mock/local-engine client that existed before Phase 3's
 * endpoints were built; see git history for that version if the backend
 * is ever unavailable and a standalone demo is needed again.
 *
 * Money and rate fields travel as decimal strings over the wire
 * (pydantic v2's default Decimal JSON encoding) but are represented as
 * plain `number` everywhere else in this frontend (see lib/types.ts) —
 * the parse* helpers below are the one place that string-to-number
 * conversion happens on the way in. Nothing needs to happen on the way
 * out: FastAPI/pydantic accepts plain JSON numbers for Decimal fields
 * just fine, so requests just send the DealInputFields numbers as-is.
 */

import type {
  AnnualCashFlowOut,
  CapitalStackLayer,
  DealCreate,
  DealOut,
  DealUpdate,
  Distribution,
  ExcludedDealOut,
  GeographyOut,
  HurdleOut,
  HurdleTableOut,
  MetricsOut,
  MonteCarloRequest,
  MonteCarloResponse,
  RankedDealOut,
  RentCheckOut,
  RiskRankRequest,
  RiskRankResponse,
  RiskRankedDealOut,
  SweepPoint,
  SweepResponse,
  SweepVariable,
  TreasuryOut,
  Weights,
} from "./types";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

const DEAL_DECIMAL_FIELDS: (keyof DealOut)[] = [
  "monthly_rent_per_unit",
  "monthly_rent_per_bed",
  "vacancy_rate",
  "other_income_annual",
  "opex_annual",
  "expense_growth_rate",
  "rent_growth_rate",
  "turnover_cost_per_unit_or_bed",
  "annual_turnover_rate",
  "purchase_price",
  "closing_costs",
  "loan_amount",
  "interest_rate",
  "exit_cap_rate",
  "selling_costs_rate",
];

const CASH_FLOW_DECIMAL_FIELDS: (keyof AnnualCashFlowOut)[] = [
  "gpr",
  "vacancy_loss",
  "other_income",
  "egi",
  "opex",
  "turnover_expense",
  "noi",
  "debt_service",
  "interest_paid",
  "principal_paid",
  "ending_loan_balance",
  "levered_cash_flow",
  "unlevered_cash_flow",
  "senior_debt_service",
  "balloon_payment",
  "preferred_distribution",
];

const LAYER_DECIMAL_FIELDS: (keyof CapitalStackLayer)[] = [
  "amount",
  "interest_rate",
  "index_rate",
  "spread",
  "rate_cap_cost",
  "origination_fee_rate",
  "preferred_return",
];

const METRICS_DECIMAL_FIELDS: (keyof MetricsOut)[] = [
  "year_one_noi",
  "going_in_cap_rate",
  "year_one_dscr",
  "cash_on_cash",
  "unlevered_irr",
  "levered_irr",
  "equity_multiple",
  "exit_value",
  "net_sale_proceeds",
  "equity_invested",
  "total_distributions",
  "forward_noi",
  "selling_costs",
  "loan_balance_at_exit",
  "year_one_senior_dscr",
  "total_debt",
  "preferred_equity",
  "upfront_financing_costs",
  "preferred_equity_repayment",
];

/** "0.0625" -> 0.0625; null passes through; numbers already-parsed pass through. */
function toNumber(value: unknown): number | null {
  if (value === null || value === undefined) return null;
  if (typeof value === "number") return value;
  const parsed = Number(value);
  return Number.isNaN(parsed) ? null : parsed;
}

function parseFields<T extends object>(raw: T, fields: (keyof T)[]): T {
  const parsed = { ...raw } as Record<string, unknown>;
  for (const field of fields) {
    parsed[field as string] = toNumber((raw as Record<string, unknown>)[field as string]);
  }
  return parsed as T;
}

function parseDealOut(raw: DealOut): DealOut {
  const parsed = parseFields(raw, DEAL_DECIMAL_FIELDS);
  return {
    ...parsed,
    capital_stack: raw.capital_stack
      ? raw.capital_stack.map((layer) => parseFields(layer, LAYER_DECIMAL_FIELDS))
      : null,
  };
}

function parseAnnualCashFlowOut(raw: AnnualCashFlowOut): AnnualCashFlowOut {
  return parseFields(raw, CASH_FLOW_DECIMAL_FIELDS);
}

function parseMetricsOut(raw: MetricsOut): MetricsOut {
  const parsed = parseFields(raw, METRICS_DECIMAL_FIELDS);
  return {
    ...parsed,
    annual_cash_flows: raw.annual_cash_flows.map(parseAnnualCashFlowOut),
  };
}

function parseRankedDealOut(raw: RankedDealOut): RankedDealOut {
  return {
    ...raw,
    deal: parseDealOut(raw.deal),
    metrics: parseMetricsOut(raw.metrics),
    // The API sends null when the deal's IRR didn't converge; -Infinity
    // keeps it sorting last and lets the views show "n/a".
    spread: toNumber(raw.spread) ?? Number.NEGATIVE_INFINITY,
  };
}

/** Parses the named decimal-string fields of a flat response object. */
function numify<T extends object>(raw: T, fields: string[]): T {
  const parsed = { ...raw } as Record<string, unknown>;
  for (const field of fields) parsed[field] = toNumber((raw as Record<string, unknown>)[field]);
  return parsed as T;
}

function parseTreasury(raw: TreasuryOut): TreasuryOut {
  return numify(raw, ["yield"]);
}

function parseHurdle(raw: HurdleOut): HurdleOut {
  return numify(raw, ["treasury_yield", "cap_rate", "noi_growth", "total"]);
}

function parseWeights(raw: Weights): Weights {
  return numify(raw, ["irr", "cash_flow", "risk"]);
}

function parseRiskRanked(raw: RiskRankedDealOut): RiskRankedDealOut {
  return {
    ...raw,
    deal: parseDealOut(raw.deal),
    metrics: parseMetricsOut(raw.metrics),
    hurdle: parseHurdle(raw.hurdle),
    spread: toNumber(raw.spread) ?? 0,
    ltv: toNumber(raw.ltv) ?? 0,
    factors: parseWeights(raw.factors),
    score: toNumber(raw.score) ?? 0,
  };
}

function parseExcluded(raw: ExcludedDealOut): ExcludedDealOut {
  return {
    ...raw,
    deal: parseDealOut(raw.deal),
    metrics: parseMetricsOut(raw.metrics),
    hurdle: parseHurdle(raw.hurdle),
  };
}

export class ApiError extends Error {
  constructor(
    method: string,
    path: string,
    public status: number,
    public body: string,
  ) {
    super(`${method} ${path} failed: ${status} ${body}`);
  }
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const method = options?.method ?? "GET";
  const res = await fetch(`${API_BASE_URL}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    const body = await res.text();
    throw new ApiError(method, path, res.status, body);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export async function listDeals(): Promise<DealOut[]> {
  const raw = await request<DealOut[]>("/deals");
  return raw.map(parseDealOut);
}

export async function getDeal(id: string): Promise<DealOut | null> {
  try {
    const raw = await request<DealOut>(`/deals/${id}`);
    return parseDealOut(raw);
  } catch (err) {
    if (err instanceof ApiError && err.status === 404) return null;
    throw err;
  }
}

export async function createDeal(input: DealCreate): Promise<DealOut> {
  const raw = await request<DealOut>("/deals", {
    method: "POST",
    body: JSON.stringify(input),
  });
  return parseDealOut(raw);
}

export async function updateDeal(id: string, input: DealUpdate): Promise<DealOut> {
  const raw = await request<DealOut>(`/deals/${id}`, {
    method: "PATCH",
    body: JSON.stringify(input),
  });
  return parseDealOut(raw);
}

export async function deleteDeal(id: string): Promise<void> {
  await request<void>(`/deals/${id}`, { method: "DELETE" });
}

export async function getMetrics(id: string): Promise<MetricsOut> {
  const raw = await request<MetricsOut>(`/deals/${id}/metrics`);
  return parseMetricsOut(raw);
}

export async function rank(dealIds: string[], hurdleRate: number): Promise<RankedDealOut[]> {
  if (dealIds.length === 0) return [];
  const raw = await request<RankedDealOut[]>("/rank", {
    method: "POST",
    body: JSON.stringify({ deal_ids: dealIds, hurdle_rate: hurdleRate }),
  });
  return raw.map(parseRankedDealOut);
}

export async function getHurdles(): Promise<HurdleTableOut> {
  const raw = await request<HurdleTableOut>("/reference/hurdles");
  return { treasury: parseTreasury(raw.treasury), hurdles: raw.hurdles.map(parseHurdle) };
}

export async function rankRiskAdjusted(input: RiskRankRequest): Promise<RiskRankResponse> {
  const raw = await request<RiskRankResponse>("/rank/risk-adjusted", {
    method: "POST",
    body: JSON.stringify(input),
  });
  return {
    ...raw,
    treasury: parseTreasury(raw.treasury),
    dscr_minimum: toNumber(raw.dscr_minimum) ?? 0,
    weights: parseWeights(raw.weights),
    ranked: raw.ranked.map(parseRiskRanked),
    excluded: raw.excluded.map(parseExcluded),
  };
}

const SWEEP_POINT_FIELDS = [
  "value",
  "unlevered_irr",
  "levered_irr",
  "cash_on_cash",
  "equity_multiple",
  "min_dscr",
  "exit_value",
];

export async function sweep(
  dealId: string,
  variable: SweepVariable,
  steps = 13,
): Promise<SweepResponse> {
  const raw = await request<SweepResponse>(`/deals/${dealId}/sensitivity`, {
    method: "POST",
    body: JSON.stringify({ variable, steps }),
  });
  return {
    ...raw,
    base_value: toNumber(raw.base_value) ?? 0,
    points: raw.points.map((p) => numify<SweepPoint>(p, SWEEP_POINT_FIELDS)),
  };
}

const DISTRIBUTION_FIELDS = ["mean", "stdev", "p5", "p25", "p50", "p75", "p95"];

function parseDistribution(raw: Distribution | null): Distribution | null {
  return raw ? numify(raw, DISTRIBUTION_FIELDS) : null;
}

export async function monteCarlo(
  dealId: string,
  input: MonteCarloRequest,
): Promise<MonteCarloResponse> {
  const raw = await request<MonteCarloResponse>(`/deals/${dealId}/monte-carlo`, {
    method: "POST",
    body: JSON.stringify(input),
  });
  return {
    ...raw,
    hurdle: toNumber(raw.hurdle),
    unlevered_irr: parseDistribution(raw.unlevered_irr),
    levered_irr: parseDistribution(raw.levered_irr),
    unlevered_histogram: raw.unlevered_histogram.map((b) => numify(b, ["low", "high"])),
    prob_below_hurdle: toNumber(raw.prob_below_hurdle),
    prob_dscr_below_minimum: toNumber(raw.prob_dscr_below_minimum),
  };
}

export function listGeographies(): Promise<GeographyOut[]> {
  return request<GeographyOut[]>("/market-rents/geographies");
}

export async function rentCheck(dealId: string, geography: string): Promise<RentCheckOut> {
  const raw = await request<RentCheckOut>(
    `/deals/${dealId}/rent-check?geography=${encodeURIComponent(geography)}`,
  );
  return numify(raw, [
    "deal_rent",
    "market_rent",
    "variance",
    "market_yoy_growth",
    "deal_rent_growth",
  ]);
}

/**
 * Turns anything a client call can throw into one sentence a user can
 * act on. FastAPI error bodies are {"detail": "..."} (a string for 404s,
 * a list of field errors for 422s); a TypeError from fetch itself means
 * the request never reached the backend at all.
 */
export function describeError(err: unknown): string {
  if (err instanceof ApiError) {
    let detail = err.body;
    try {
      const parsed = JSON.parse(err.body) as { detail?: unknown };
      if (typeof parsed.detail === "string") {
        detail = parsed.detail;
      } else if (Array.isArray(parsed.detail)) {
        detail = parsed.detail
          .map((d: { msg?: string }) => d.msg)
          .filter(Boolean)
          .join("; ");
      }
    } catch {
      // Not JSON (e.g. a proxy's HTML error page) — fall back to status only.
      detail = "";
    }
    return detail ? `Server returned ${err.status}: ${detail}` : `Server returned ${err.status}.`;
  }
  if (err instanceof TypeError) {
    return "Couldn't reach the DealRank API — is the backend running?";
  }
  return err instanceof Error ? err.message : String(err);
}

const REPORT_FILENAMES: Record<"pdf" | "pptx", string> = {
  pdf: "dealrank-comparison.pdf",
  pptx: "dealrank-comparison.pptx",
};

/**
 * GET /reports/pdf and GET /reports/pptx (docs/build-plan.md 6.4).
 * Fetched here rather than linked with a plain <a href> so the download
 * buttons can show a loading state while the server renders the file and
 * a real error message if it fails — a bare link to a 404/422 just
 * navigated the tab to a JSON error body. The bytes are handed to the
 * browser's normal download flow through a temporary object URL.
 */
export async function downloadReport(
  kind: "pdf" | "pptx",
  dealIds: string[],
  hurdleRate: number,
): Promise<void> {
  const url = buildReportUrl(kind, dealIds, hurdleRate);
  const res = await fetch(url);
  if (!res.ok) {
    throw new ApiError("GET", `/reports/${kind}`, res.status, await res.text());
  }
  const blob = await res.blob();
  if (blob.size === 0) {
    throw new Error(`The ${kind.toUpperCase()} report came back empty.`);
  }
  const objectUrl = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = objectUrl;
  link.download = REPORT_FILENAMES[kind];
  document.body.appendChild(link);
  link.click();
  link.remove();
  // Revoke on the next tick so the browser has started the download.
  setTimeout(() => URL.revokeObjectURL(objectUrl), 0);
}

/** The report endpoint URL for a given selection and hurdle rate. */
export function buildReportUrl(
  kind: "pdf" | "pptx",
  dealIds: string[],
  hurdleRate: number,
): string {
  const params = new URLSearchParams();
  for (const id of dealIds) params.append("deal_ids", id);
  params.set("hurdle_rate", String(hurdleRate));
  return `${API_BASE_URL}/reports/${kind}?${params.toString()}`;
}
