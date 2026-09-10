/**
 * TypeScript port of backend/app/engine/{revenue,expenses,debt,waterfall,metrics}.py.
 * Same formulas, same decisions (D1 forward-NOI exit, D2 monthly-amortized
 * debt aggregated to annual, D3 annual turnover) — see docs/build-plan.md
 * section 2. Uses JS `number` instead of Python `Decimal`: fine for a UI
 * demo, not a substitute for the graded backend, which is the source of
 * truth. Exists so the mock client (client.ts) can compute real metrics
 * from whatever a user types into the deal form, instead of only ever
 * showing hardcoded numbers.
 */

import type { AnnualCashFlowOut, DealInputFields, MetricsOut } from "./types";

const MONTHS_PER_YEAR = 12;

// --- revenue.py -------------------------------------------------------

function grossPotentialRent(deal: DealInputFields, year: number): number {
  const count = deal.leasing_mode === "per_unit" ? deal.unit_count! : deal.bed_count!;
  const monthlyRate =
    deal.leasing_mode === "per_unit" ? deal.monthly_rent_per_unit! : deal.monthly_rent_per_bed!;
  const yearOneGpr = count * monthlyRate * MONTHS_PER_YEAR;
  return yearOneGpr * Math.pow(1 + deal.rent_growth_rate, year - 1);
}

function effectiveGrossIncome(
  gpr: number,
  vacancyRate: number,
  otherIncomeAnnual: number,
): { vacancyLoss: number; egi: number } {
  const vacancyLoss = gpr * vacancyRate;
  return { vacancyLoss, egi: gpr - vacancyLoss + otherIncomeAnnual };
}

// --- expenses.py --------------------------------------------------------

function operatingExpenses(deal: DealInputFields, year: number): number {
  return deal.opex_annual * Math.pow(1 + deal.expense_growth_rate, year - 1);
}

function turnoverExpense(deal: DealInputFields, year: number): number {
  const count = deal.leasing_mode === "per_unit" ? deal.unit_count! : deal.bed_count!;
  const yearOneTurnover = deal.turnover_cost_per_unit_or_bed * count * deal.annual_turnover_rate;
  return yearOneTurnover * Math.pow(1 + deal.expense_growth_rate, year - 1);
}

// --- debt.py --------------------------------------------------------------

interface AnnualDebtService {
  year: number;
  interestPaid: number;
  principalPaid: number;
  debtService: number;
  endingBalance: number;
}

function monthlyPayment(
  loanAmount: number,
  annualInterestRate: number,
  amortizationYears: number,
): number {
  if (loanAmount === 0) return 0;
  const n = amortizationYears * MONTHS_PER_YEAR;
  const r = annualInterestRate / MONTHS_PER_YEAR;
  if (r === 0) return loanAmount / n;
  const factor = Math.pow(1 + r, n);
  return (loanAmount * r * factor) / (factor - 1);
}

function amortizationSchedule(deal: DealInputFields): AnnualDebtService[] {
  const payment = monthlyPayment(deal.loan_amount, deal.interest_rate, deal.amortization_years);
  const monthlyRate = deal.interest_rate / MONTHS_PER_YEAR;

  const schedule: AnnualDebtService[] = [];
  let balance = deal.loan_amount;

  for (let year = 1; year <= deal.hold_period_years; year++) {
    let yearInterest = 0;
    let yearPrincipal = 0;

    for (let m = 0; m < MONTHS_PER_YEAR; m++) {
      if (balance <= 0) break;
      const interest = balance * monthlyRate;
      let principal = payment - interest;
      if (principal > balance) principal = balance;
      balance -= principal;
      yearInterest += interest;
      yearPrincipal += principal;
    }

    schedule.push({
      year,
      interestPaid: yearInterest,
      principalPaid: yearPrincipal,
      debtService: yearInterest + yearPrincipal,
      endingBalance: balance,
    });
  }

  return schedule;
}

// --- waterfall.py -----------------------------------------------------

interface NoiBuildingBlocks {
  gpr: number;
  vacancyLoss: number;
  egi: number;
  opex: number;
  turnover: number;
  noi: number;
}

function noiForYear(deal: DealInputFields, year: number): NoiBuildingBlocks {
  const gpr = grossPotentialRent(deal, year);
  const { vacancyLoss, egi } = effectiveGrossIncome(
    gpr,
    deal.vacancy_rate,
    deal.other_income_annual,
  );
  const opex = operatingExpenses(deal, year);
  const turnover = turnoverExpense(deal, year);
  return { gpr, vacancyLoss, egi, opex, turnover, noi: egi - opex - turnover };
}

interface WaterfallResult {
  annualCashFlows: AnnualCashFlowOut[];
  exitValue: number;
  netSaleProceeds: number;
}

function project(deal: DealInputFields): WaterfallResult {
  const debtSchedule = amortizationSchedule(deal);

  const annualCashFlows: AnnualCashFlowOut[] = [];
  for (let year = 1; year <= deal.hold_period_years; year++) {
    const { gpr, vacancyLoss, egi, opex, turnover, noi } = noiForYear(deal, year);
    const debtYear = debtSchedule[year - 1];
    const leveredCf = noi - debtYear.debtService;

    annualCashFlows.push({
      year,
      gpr,
      vacancy_loss: vacancyLoss,
      other_income: deal.other_income_annual,
      egi,
      opex,
      turnover_expense: turnover,
      noi,
      debt_service: debtYear.debtService,
      interest_paid: debtYear.interestPaid,
      principal_paid: debtYear.principalPaid,
      ending_loan_balance: debtYear.endingBalance,
      levered_cash_flow: leveredCf,
      unlevered_cash_flow: noi,
    });
  }

  // D1: exit value uses forward (year N+1) NOI over the exit cap rate.
  const { noi: forwardNoi } = noiForYear(deal, deal.hold_period_years + 1);
  const exitValue = forwardNoi / deal.exit_cap_rate;

  const endingBalance = debtSchedule.length
    ? debtSchedule[debtSchedule.length - 1].endingBalance
    : 0;
  const sellingCosts = exitValue * deal.selling_costs_rate;
  const netSaleProceeds = exitValue - sellingCosts - endingBalance;

  return { annualCashFlows, exitValue, netSaleProceeds };
}

// --- metrics.py -------------------------------------------------------

/**
 * Minimal IRR solver (Newton's method with a bisection fallback), playing
 * the role numpy-financial plays in the Python engine. Returns null
 * rather than throwing when it doesn't converge.
 */
function irr(cashFlows: number[]): number | null {
  const npv = (rate: number) =>
    cashFlows.reduce((sum, cf, t) => sum + cf / Math.pow(1 + rate, t), 0);
  const dNpv = (rate: number) =>
    cashFlows.reduce((sum, cf, t) => sum - (t * cf) / Math.pow(1 + rate, t + 1), 0);

  let rate = 0.1;
  for (let i = 0; i < 100; i++) {
    const value = npv(rate);
    const derivative = dNpv(rate);
    if (Math.abs(derivative) < 1e-12) break;
    const next = rate - value / derivative;
    if (!Number.isFinite(next) || next <= -0.999999) break;
    if (Math.abs(next - rate) < 1e-10) {
      return Math.abs(npv(next)) < 1e-4 ? next : null;
    }
    rate = next;
  }

  // Bisection fallback over a wide, sane range.
  let lo = -0.9999;
  let hi = 10;
  const npvLo = npv(lo);
  const npvHi = npv(hi);
  if (Number.isNaN(npvLo) || Number.isNaN(npvHi) || npvLo * npvHi > 0) return null;
  for (let i = 0; i < 200; i++) {
    const mid = (lo + hi) / 2;
    const npvMid = npv(mid);
    if (Math.abs(npvMid) < 1e-6) return mid;
    if (npvLo * npvMid < 0) hi = mid;
    else lo = mid;
  }
  return (lo + hi) / 2;
}

function equityInvested(deal: DealInputFields): number {
  return deal.purchase_price + deal.closing_costs - deal.loan_amount;
}

export function computeMetrics(deal: DealInputFields): MetricsOut {
  const result = project(deal);
  const flows = result.annualCashFlows;
  const yearOne = flows[0];
  const equity = equityInvested(deal);

  const capRate = yearOne.noi / deal.purchase_price;
  const yearOneDscr = yearOne.debt_service === 0 ? null : yearOne.noi / yearOne.debt_service;
  const cashOnCash = equity !== 0 ? yearOne.levered_cash_flow / equity : null;

  const leveredStream = [-equity, ...flows.map((cf) => cf.levered_cash_flow)];
  leveredStream[leveredStream.length - 1] += result.netSaleProceeds;
  const leveredIrr = irr(leveredStream);

  const unleveredOutlay = deal.purchase_price + deal.closing_costs;
  const unleveredExitProceeds = result.exitValue - result.exitValue * deal.selling_costs_rate;
  const unleveredStream = [-unleveredOutlay, ...flows.map((cf) => cf.unlevered_cash_flow)];
  unleveredStream[unleveredStream.length - 1] += unleveredExitProceeds;
  const unleveredIrr = irr(unleveredStream);

  const totalLeveredCf = flows.reduce((sum, cf) => sum + cf.levered_cash_flow, 0);
  const equityMultiple = equity !== 0 ? (totalLeveredCf + result.netSaleProceeds) / equity : null;

  return {
    annual_cash_flows: flows,
    year_one_noi: yearOne.noi,
    going_in_cap_rate: capRate,
    year_one_dscr: yearOneDscr,
    cash_on_cash: cashOnCash,
    unlevered_irr: unleveredIrr,
    levered_irr: leveredIrr,
    equity_multiple: equityMultiple,
    exit_value: result.exitValue,
    net_sale_proceeds: result.netSaleProceeds,
  };
}
