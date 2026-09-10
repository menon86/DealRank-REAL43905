/**
 * Local/mock data client — see docs/build-plan.md 5.1 ("a typed api.ts...
 * against mocked client"). Implements the same function signatures the
 * real API client will have once Phase 3's FastAPI endpoints exist
 * (docs/build-plan.md section 5's frozen contract), but computes
 * everything in-browser via engine.ts instead of calling fetch(). Swap
 * point for later: replace the bodies of these functions with fetch
 * calls against the deployed API; nothing that imports from this module
 * needs to change shape.
 *
 * Deals persist to localStorage so edits survive a reload during a demo.
 * Seeded with the same three deals as backend/seed.py.
 */

import { computeMetrics } from "./engine";
import type { DealCreate, DealOut, DealUpdate, MetricsOut, RankedDealOut } from "./types";

const STORAGE_KEY = "dealrank.deals.v1";

function seedDeals(): DealOut[] {
  const now = new Date().toISOString();
  return [
    {
      id: "seed-student-housing",
      name: "Campus View Student Housing",
      sub_asset_class: "student_housing",
      leasing_mode: "per_bed",
      unit_count: null,
      monthly_rent_per_unit: null,
      bed_count: 240,
      monthly_rent_per_bed: 750,
      vacancy_rate: 0.06,
      other_income_annual: 36000,
      opex_annual: 620000,
      expense_growth_rate: 0.03,
      rent_growth_rate: 0.03,
      lease_expiration_month: 8,
      turnover_cost_per_unit_or_bed: 350,
      annual_turnover_rate: 0.85,
      purchase_price: 21500000,
      closing_costs: 430000,
      loan_amount: 14000000,
      interest_rate: 0.0625,
      amortization_years: 30,
      hold_period_years: 7,
      exit_cap_rate: 0.058,
      selling_costs_rate: 0.02,
      created_at: now,
      updated_at: now,
    },
    {
      id: "seed-suburban-garden",
      name: "Willowbrook Suburban Garden",
      sub_asset_class: "suburban_garden",
      leasing_mode: "per_unit",
      unit_count: 180,
      monthly_rent_per_unit: 1450,
      bed_count: null,
      monthly_rent_per_bed: null,
      vacancy_rate: 0.05,
      other_income_annual: 54000,
      opex_annual: 980000,
      expense_growth_rate: 0.03,
      rent_growth_rate: 0.025,
      lease_expiration_month: 6,
      turnover_cost_per_unit_or_bed: 900,
      annual_turnover_rate: 0.55,
      purchase_price: 28800000,
      closing_costs: 576000,
      loan_amount: 18700000,
      interest_rate: 0.06,
      amortization_years: 30,
      hold_period_years: 10,
      exit_cap_rate: 0.055,
      selling_costs_rate: 0.02,
      created_at: now,
      updated_at: now,
    },
    {
      id: "seed-urban-midrise",
      name: "Meridian Urban Mid-Rise",
      sub_asset_class: "urban_midrise",
      leasing_mode: "per_unit",
      unit_count: 95,
      monthly_rent_per_unit: 2100,
      bed_count: null,
      monthly_rent_per_bed: null,
      vacancy_rate: 0.07,
      other_income_annual: 42000,
      opex_annual: 870000,
      expense_growth_rate: 0.03,
      rent_growth_rate: 0.02,
      lease_expiration_month: 5,
      turnover_cost_per_unit_or_bed: 1500,
      annual_turnover_rate: 0.5,
      purchase_price: 32000000,
      closing_costs: 640000,
      loan_amount: 20800000,
      interest_rate: 0.0615,
      amortization_years: 30,
      hold_period_years: 10,
      exit_cap_rate: 0.05,
      selling_costs_rate: 0.02,
      created_at: now,
      updated_at: now,
    },
  ];
}

function loadDeals(): DealOut[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return seedDeals();
    const parsed = JSON.parse(raw) as DealOut[];
    if (!Array.isArray(parsed) || parsed.length === 0) return seedDeals();
    return parsed;
  } catch {
    return seedDeals();
  }
}

function saveDeals(deals: DealOut[]): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(deals));
  } catch {
    // localStorage unavailable (private mode, etc.) — demo still works
    // for the current page load, just doesn't persist across reloads.
  }
}

let deals: DealOut[] = loadDeals();

function nextId(): string {
  return `deal-${Math.random().toString(36).slice(2, 10)}`;
}

export async function listDeals(): Promise<DealOut[]> {
  return [...deals];
}

export async function getDeal(id: string): Promise<DealOut | null> {
  return deals.find((d) => d.id === id) ?? null;
}

export async function createDeal(input: DealCreate): Promise<DealOut> {
  const now = new Date().toISOString();
  const deal: DealOut = { ...input, id: nextId(), created_at: now, updated_at: now };
  deals = [...deals, deal];
  saveDeals(deals);
  return deal;
}

export async function updateDeal(id: string, input: DealUpdate): Promise<DealOut> {
  const index = deals.findIndex((d) => d.id === id);
  if (index === -1) throw new Error(`Deal ${id} not found`);
  const updated: DealOut = { ...deals[index], ...input, updated_at: new Date().toISOString() };
  deals = [...deals.slice(0, index), updated, ...deals.slice(index + 1)];
  saveDeals(deals);
  return updated;
}

export async function deleteDeal(id: string): Promise<void> {
  deals = deals.filter((d) => d.id !== id);
  saveDeals(deals);
}

export async function getMetrics(id: string): Promise<MetricsOut> {
  const deal = deals.find((d) => d.id === id);
  if (!deal) throw new Error(`Deal ${id} not found`);
  return computeMetrics(deal);
}

/**
 * Sorted by unlevered_irr - hurdle_rate descending, matching
 * docs/build-plan.md 3.4. Levered IRR is returned for display and never
 * sorted on.
 */
export async function rank(dealIds: string[], hurdleRate: number): Promise<RankedDealOut[]> {
  const selected = dealIds
    .map((id) => deals.find((d) => d.id === id))
    .filter((d): d is DealOut => Boolean(d));

  const withMetrics = selected.map((deal) => {
    const metrics = computeMetrics(deal);
    const spread = (metrics.unlevered_irr ?? -Infinity) - hurdleRate;
    return { deal, metrics, spread };
  });

  withMetrics.sort((a, b) => b.spread - a.spread);

  return withMetrics.map((entry, index) => ({
    deal: entry.deal,
    metrics: entry.metrics,
    spread: entry.spread,
    rank: index + 1,
  }));
}
