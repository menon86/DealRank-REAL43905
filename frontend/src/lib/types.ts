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
  /** Purchase price + closing costs − loan amount. */
  equity_invested: number;
  /** Sum of every year's levered cash flow plus net sale proceeds. */
  total_distributions: number;
  /** NOI for year hold_period_years + 1, the basis of exit value. */
  forward_noi: number;
  selling_costs: number;
  loan_balance_at_exit: number;
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

// ---------------------------------------------------------------------------
// Deliverable 3: risk-adjusted ranking, sensitivity, market check
// ---------------------------------------------------------------------------

export interface TreasuryOut {
  yield: number;
  as_of: string | null;
  /** "fred" (live) | "fallback" (configured default, lookup failed) | "override" */
  source: string;
}

export interface HurdleOut {
  sub_asset_class: SubAssetClass;
  treasury_yield: number;
  spread_bps: number;
  /** Treasury + spread. */
  cap_rate: number;
  noi_growth: number;
  /** cap_rate + noi_growth: the hurdle an unlevered IRR is compared to. */
  total: number;
  survey_source: string;
  survey_quarter: string;
  effective_date: string;
}

export interface HurdleTableOut {
  treasury: TreasuryOut;
  hurdles: HurdleOut[];
}

export interface Weights {
  irr: number;
  cash_flow: number;
  risk: number;
}

export type PrimaryGoal = "total_return" | "cash_flow" | "preservation";

export interface Questionnaire {
  primary_goal: PrimaryGoal;
  risk_tolerance: number;
  income_need: number;
}

export interface RiskRankRequest {
  deal_ids: string[];
  dscr_minimum: number;
  treasury_yield?: number | null;
  weights?: Weights | null;
  answers?: Questionnaire | null;
}

export interface RiskRankedDealOut {
  rank: number;
  deal: DealOut;
  metrics: MetricsOut;
  hurdle: HurdleOut;
  spread: number;
  ltv: number;
  factors: Weights;
  score: number;
}

export interface ExcludedDealOut {
  deal: DealOut;
  metrics: MetricsOut;
  hurdle: HurdleOut;
  reason: string;
}

export interface RiskRankResponse {
  treasury: TreasuryOut;
  dscr_minimum: number;
  weights: Weights;
  ranked: RiskRankedDealOut[];
  excluded: ExcludedDealOut[];
  basis_note: string;
}

export type SweepVariable = "exit_cap_rate" | "rent_growth_rate";

export interface SweepPoint {
  value: number;
  unlevered_irr: number | null;
  levered_irr: number | null;
  cash_on_cash: number | null;
  equity_multiple: number | null;
  min_dscr: number | null;
  exit_value: number;
}

export interface SweepResponse {
  variable: SweepVariable;
  base_value: number;
  points: SweepPoint[];
}

export interface MonteCarloRequest {
  simulations: number;
  seed?: number | null;
  exit_cap_sd: number;
  rent_growth_sd: number;
  vacancy_sd: number;
  hurdle?: number | null;
  dscr_minimum: number;
}

export interface Distribution {
  mean: number;
  stdev: number;
  p5: number;
  p25: number;
  p50: number;
  p75: number;
  p95: number;
}

export interface HistogramBin {
  low: number;
  high: number;
  count: number;
}

export interface MonteCarloResponse {
  simulations: number;
  converged: number;
  seed: number | null;
  hurdle: number | null;
  /** "user" | "risk_adjusted" */
  hurdle_source: string;
  unlevered_irr: Distribution | null;
  levered_irr: Distribution | null;
  unlevered_histogram: HistogramBin[];
  prob_below_hurdle: number | null;
  prob_dscr_below_minimum: number | null;
}

export type RentCheckStatus = "ok" | "caution" | "flag" | "not_comparable" | "no_data";

export interface RentCheckOut {
  status: RentCheckStatus;
  geography: string;
  deal_rent: number | null;
  market_rent: number | null;
  market_period: string | null;
  source: string | null;
  variance: number | null;
  market_yoy_growth: number | null;
  deal_rent_growth: number;
  note: string;
}

export interface GeographyOut {
  geography: string;
  source: string;
  latest_period: string;
}
