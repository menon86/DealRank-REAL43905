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
  DealCreate,
  DealOut,
  DealUpdate,
  MetricsOut,
  RankedDealOut,
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
];

/** "0.0625" -> 0.0625; null passes through; numbers already-parsed pass through. */
function toNumber(value: unknown): number | null {
  if (value === null || value === undefined) return null;
  if (typeof value === "number") return value;
  const parsed = Number(value);
  return Number.isNaN(parsed) ? null : parsed;
}

function parseFields<T extends Record<string, unknown>>(raw: T, fields: (keyof T)[]): T {
  const parsed = { ...raw };
  for (const field of fields) {
    (parsed as Record<string, unknown>)[field as string] = toNumber(raw[field]);
  }
  return parsed;
}

function parseDealOut(raw: DealOut): DealOut {
  return parseFields(raw, DEAL_DECIMAL_FIELDS);
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
    spread: toNumber(raw.spread) ?? 0,
  };
}

class ApiError extends Error {
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
