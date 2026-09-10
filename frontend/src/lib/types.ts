/**
 * Mirrors the frozen API contract in docs/build-plan.md section 5, and
 * backend/app/models/deal.py field-for-field. Money is a decimal string
 * over the wire; rates are decimal fractions (6% is 0.06). This file is
 * what the real API client (once Phase 3 lands) and the mock client in
 * client.ts both build on — neither should need its own shapes.
 */

export type SubAssetClass = "student_housing" | "suburban_garden" | "urban_midrise";
export type LeasingMode = "per_unit" | "per_bed";

export interface DealInputFields {
  name: string;
  sub_asset_class: SubAssetClass;
  leasing_mode: LeasingMode;

  // Exactly one branch populated per leasing_mode.
  unit_count: number | null;
  monthly_rent_per_unit: number | null;
  bed_count: number | null;
  monthly_rent_per_bed: number | null;

  vacancy_rate: number;
  other_income_annual: number;

  opex_annual: number;
  expense_growth_rate: number;
  rent_growth_rate: number;

  lease_expiration_month: number;
  turnover_cost_per_unit_or_bed: number;
  annual_turnover_rate: number;

  purchase_price: number;
  closing_costs: number;
  loan_amount: number;
  interest_rate: number;
  amortization_years: number;

  hold_period_years: number;
  exit_cap_rate: number;
  selling_costs_rate: number;
}

export type DealCreate = DealInputFields;
export type DealUpdate = Partial<DealInputFields>;

export interface DealOut extends DealInputFields {
  id: string;
  created_at: string;
  updated_at: string;
}

export interface AnnualCashFlowOut {
  year: number;
  gpr: number;
  vacancy_loss: number;
  other_income: number;
  egi: number;
  opex: number;
  turnover_expense: number;
  noi: number;
  debt_service: number;
  interest_paid: number;
  principal_paid: number;
  ending_loan_balance: number;
  levered_cash_flow: number;
  unlevered_cash_flow: number;
}

export interface MetricsOut {
  annual_cash_flows: AnnualCashFlowOut[];
  year_one_noi: number;
  going_in_cap_rate: number;
  year_one_dscr: number | null;
  cash_on_cash: number | null;
  unlevered_irr: number | null;
  levered_irr: number | null;
  equity_multiple: number | null;
  exit_value: number;
  net_sale_proceeds: number;
}

export interface RankedDealOut {
  deal: DealOut;
  metrics: MetricsOut;
  spread: number;
  rank: number;
}

export interface RankRequest {
  deal_ids: string[];
  hurdle_rate: number;
}

export const SUB_ASSET_CLASS_LABELS: Record<SubAssetClass, string> = {
  student_housing: "Student Housing",
  suburban_garden: "Suburban Garden",
  urban_midrise: "Urban Mid-Rise",
};
