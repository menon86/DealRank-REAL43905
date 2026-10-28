/**
 * Capital stack: the layer catalogue, the deal form's editable layer
 * shape and its conversion to/from the API, and the same validation rules
 * the backend enforces (backend/app/engine/financing.py
 * validate_capital_stack), so the form can flag a bad stack before saving.
 */

import type {
  CapitalStackLayer,
  DealOut,
  LayerGroup,
  LayerType,
  PrepaymentType,
  RateType,
} from "./types";
import { fractionToPercentInput } from "./format";

export interface LayerOption {
  type: LayerType;
  group: LayerGroup;
  label: string;
  note: string;
}

export const LAYER_OPTIONS: LayerOption[] = [
  {
    type: "agency_fannie_mae",
    group: "senior",
    label: "Agency – Fannie Mae",
    note: "DUS, Small Loans, student housing program",
  },
  {
    type: "agency_freddie_mac",
    group: "senior",
    label: "Agency – Freddie Mac",
    note: "Optigo conventional, Small Balance Loans, student housing",
  },
  {
    type: "hud_223f",
    group: "senior",
    label: "HUD/FHA 223(f)",
    note: "Buying or refinancing stabilized properties",
  },
  {
    type: "hud_221d4",
    group: "senior",
    label: "HUD/FHA 221(d)(4)",
    note: "New construction or substantial rehab",
  },
  {
    type: "bank_credit_union",
    group: "senior",
    label: "Bank / credit union",
    note: "Lender's own books, usually recourse, often floating",
  },
  {
    type: "life_company",
    group: "senior",
    label: "Life insurance company",
    note: "Low leverage, low rate",
  },
  {
    type: "cmbs",
    group: "senior",
    label: "CMBS / conduit",
    note: "Non-recourse, defeasance or yield maintenance prepayment",
  },
  {
    type: "bridge_debt_fund",
    group: "senior",
    label: "Bridge / debt fund",
    note: "Short-term, floating, value-add or lease-up",
  },
  { type: "construction", group: "senior", label: "Construction loan", note: "Development deals" },
  {
    type: "loan_assumption",
    group: "senior",
    label: "Loan assumption",
    note: "Taking over the seller's existing loan",
  },
  {
    type: "seller_financing",
    group: "senior",
    label: "Seller financing",
    note: "Note from seller to buyer",
  },
  {
    type: "other_senior",
    group: "senior",
    label: "Other (specify)",
    note: "Name this senior loan",
  },

  {
    type: "mezzanine",
    group: "subordinate",
    label: "Mezzanine debt",
    note: "Secured by ownership interests",
  },
  {
    type: "preferred_equity",
    group: "subordinate",
    label: "Preferred equity",
    note: "Paid back before common equity",
  },
  {
    type: "supplemental_loan",
    group: "subordinate",
    label: "Supplemental loan",
    note: "A second agency loan on top of the first",
  },
  {
    type: "seller_carryback_second",
    group: "subordinate",
    label: "Seller carryback second",
    note: "Second mortgage held by the seller",
  },
  {
    type: "other_subordinate",
    group: "subordinate",
    label: "Other (specify)",
    note: "Name this subordinate loan",
  },

  {
    type: "sponsor_gp",
    group: "equity",
    label: "Sponsor / GP equity",
    note: "Operator's own money",
  },
  {
    type: "lp_syndication",
    group: "equity",
    label: "LP syndication",
    note: "Reg D 506(b) / 506(c)",
  },
  {
    type: "jv_partner",
    group: "equity",
    label: "JV partner",
    note: "Institutional or family office",
  },
  { type: "exchange_1031", group: "equity", label: "1031 exchange proceeds", note: "" },
  { type: "dst_tic", group: "equity", label: "DST / TIC", note: "" },
  { type: "opportunity_zone", group: "equity", label: "Opportunity Zone fund", note: "" },
  { type: "all_cash", group: "equity", label: "All cash", note: "The deal has no debt" },
  {
    type: "other_equity",
    group: "equity",
    label: "Other (specify)",
    note: "Name this equity source",
  },
];

export const GROUP_LABELS: Record<LayerGroup, string> = {
  senior: "Senior debt",
  subordinate: "Subordinate / gap",
  equity: "Equity",
};

const OPTION_BY_TYPE = Object.fromEntries(LAYER_OPTIONS.map((o) => [o.type, o])) as Record<
  LayerType,
  LayerOption
>;

export function layerOption(type: LayerType): LayerOption {
  return OPTION_BY_TYPE[type];
}

export function layerGroup(type: LayerType): LayerGroup {
  return OPTION_BY_TYPE[type].group;
}

export function isOtherType(type: LayerType): boolean {
  return type === "other_senior" || type === "other_subordinate" || type === "other_equity";
}

/** Senior debt and every subordinate type except preferred equity. */
export function isDebtType(type: LayerType): boolean {
  const group = layerGroup(type);
  return group === "senior" || (group === "subordinate" && type !== "preferred_equity");
}

/** "Other" layers show the name the user typed; others their type, plus any label. */
export function layerDisplayName(type: LayerType, label: string | null): string {
  const trimmed = (label ?? "").trim();
  const option = layerOption(type);
  if (isOtherType(type)) return trimmed || `Other ${GROUP_LABELS[option.group].toLowerCase()}`;
  return trimmed ? `${option.label} (${trimmed})` : option.label;
}

// ---------------------------------------------------------------------------
// Prepayment and FHA mortgage insurance: typical terms by loan type. These
// are starting values the user can change, not rules.
// ---------------------------------------------------------------------------

export const PREPAYMENT_LABELS: Record<PrepaymentType, string> = {
  none: "None / open",
  step_down: "Step-down (% of balance by year)",
  yield_maintenance: "Yield maintenance",
  defeasance: "Defeasance",
};

/** HUD loans, and an assumed loan (which may be an existing HUD loan). */
export function allowsMortgageInsurance(type: LayerType): boolean {
  return type === "hud_223f" || type === "hud_221d4" || type === "loan_assumption";
}

interface TypeDefaults {
  prepayment_type: PrepaymentType;
  prepayment_schedule: string;
  mip_annual_pct: string;
  mip_upfront_pct: string;
  amortization_years?: string;
  term_years?: string;
}

const HUD_STEP_DOWN = "10, 9, 8, 7, 6, 5, 4, 3, 2, 1";
// FHA multifamily MIP: 0.25% annual and upfront for 223(f) and 221(d)(4)
// applications from Oct 1, 2025 (HUD final notice, Federal Register,
// Sept 23, 2025). Older loans carry higher rates; the field is editable.
const HUD_MIP = "0.25";

export function typeDefaults(type: LayerType): TypeDefaults {
  const none = { prepayment_schedule: "", mip_annual_pct: "0", mip_upfront_pct: "0" };
  switch (type) {
    case "agency_fannie_mae":
    case "agency_freddie_mac":
    case "life_company":
    case "supplemental_loan":
      return { ...none, prepayment_type: "yield_maintenance", term_years: "10" };
    case "cmbs":
      return { ...none, prepayment_type: "defeasance", term_years: "10" };
    case "bank_credit_union":
      return { ...none, prepayment_type: "step_down", prepayment_schedule: "5, 4, 3, 2, 1" };
    case "hud_223f":
      return {
        prepayment_type: "step_down",
        prepayment_schedule: HUD_STEP_DOWN,
        mip_annual_pct: HUD_MIP,
        mip_upfront_pct: HUD_MIP,
        amortization_years: "35",
        term_years: "35",
      };
    case "hud_221d4":
      return {
        prepayment_type: "step_down",
        prepayment_schedule: HUD_STEP_DOWN,
        mip_annual_pct: HUD_MIP,
        mip_upfront_pct: HUD_MIP,
        amortization_years: "40",
        term_years: "40",
      };
    default:
      return { ...none, prepayment_type: "none" };
  }
}

function needsTreasury(prepayment: PrepaymentType): boolean {
  return prepayment === "yield_maintenance" || prepayment === "defeasance";
}

/**
 * Fills a blank Treasury rate with the market rate (percent string) on every
 * layer whose prepayment needs one; layers the user already filled are kept.
 */
export function withDefaultTreasury(layers: LayerForm[], treasuryPct: string): LayerForm[] {
  if (treasuryPct === "") return layers;
  return layers.map((layer) =>
    isDebtType(layer.type) &&
    needsTreasury(layer.prepayment_type) &&
    layer.prepayment_treasury_pct.trim() === ""
      ? { ...layer, prepayment_treasury_pct: treasuryPct }
      : layer,
  );
}

/** "5, 4, 3-2 1" -> [0.05, 0.04, 0.03, 0.02, 0.01]; null if any entry isn't a number. */
export function parseStepDown(value: string): number[] | null {
  const parts = value.split(/[\s,;/-]+/).filter((p) => p !== "");
  const rates = parts.map((p) => Number(p) / 100);
  return rates.every((r) => Number.isFinite(r)) ? rates : null;
}

// ---------------------------------------------------------------------------
// Form shape: every number is the raw input string, rates in percent.
// ---------------------------------------------------------------------------

export type AmountMode = "dollars" | "percent";

export interface LayerForm {
  key: string;
  type: LayerType;
  label: string;
  amountMode: AmountMode;
  amount: string;
  /** % of total cost (price + closing costs), used when amountMode is "percent". */
  amountPct: string;
  rate_type: RateType;
  interest_rate_pct: string;
  index_name: string;
  index_rate_pct: string;
  spread_bps: string;
  io_months: string;
  /** Blank = interest-only for the whole term. */
  amortization_years: string;
  /** Blank = no maturity before the exit. */
  term_years: string;
  recourse: "" | "recourse" | "non_recourse";
  rate_cap_cost: string;
  origination_fee_pct: string;
  preferred_return_pct: string;
  prepayment_type: PrepaymentType;
  /** Step-down percentages by loan year, e.g. "5, 4, 3, 2, 1". */
  prepayment_schedule: string;
  prepayment_treasury_pct: string;
  mip_annual_pct: string;
  mip_upfront_pct: string;
  expanded: boolean;
}

let keyCounter = 0;
function nextKey(): string {
  keyCounter += 1;
  return `layer-${keyCounter}`;
}

export function blankLayer(type: LayerType): LayerForm {
  const debt = isDebtType(type);
  const defaults = typeDefaults(type);
  return {
    key: nextKey(),
    type,
    label: "",
    amountMode: "dollars",
    amount: "",
    amountPct: "",
    rate_type: type === "bridge_debt_fund" ? "floating" : "fixed",
    interest_rate_pct: "",
    index_name: "SOFR",
    index_rate_pct: "",
    spread_bps: "",
    io_months: "0",
    amortization_years: defaults.amortization_years ?? (debt && type !== "mezzanine" ? "30" : ""),
    term_years: defaults.term_years ?? "",
    recourse: "",
    rate_cap_cost: "0",
    origination_fee_pct: "0",
    preferred_return_pct: "",
    prepayment_type: debt ? defaults.prepayment_type : "none",
    prepayment_schedule: defaults.prepayment_schedule,
    prepayment_treasury_pct: "",
    mip_annual_pct: defaults.mip_annual_pct,
    mip_upfront_pct: defaults.mip_upfront_pct,
    expanded: debt || type === "preferred_equity",
  };
}

function pct(value: number | null): string {
  return value === null ? "" : fractionToPercentInput(value);
}

export function layerToForm(layer: CapitalStackLayer): LayerForm {
  return {
    key: nextKey(),
    type: layer.type,
    label: layer.label ?? "",
    amountMode: "dollars",
    amount: String(layer.amount),
    amountPct: "",
    rate_type: layer.rate_type,
    interest_rate_pct: pct(layer.interest_rate),
    index_name: layer.index_name ?? "",
    index_rate_pct: pct(layer.index_rate),
    spread_bps: layer.spread === null ? "" : String(Number((layer.spread * 10000).toFixed(4))),
    io_months: String(layer.io_months),
    amortization_years: layer.amortization_years?.toString() ?? "",
    term_years: layer.term_years?.toString() ?? "",
    recourse: layer.recourse === null ? "" : layer.recourse ? "recourse" : "non_recourse",
    rate_cap_cost: String(layer.rate_cap_cost),
    origination_fee_pct: pct(layer.origination_fee_rate),
    preferred_return_pct: pct(layer.preferred_return),
    prepayment_type: layer.prepayment_type ?? "none",
    prepayment_schedule: (layer.prepayment_schedule ?? [])
      .map((r) => String(Number((r * 100).toFixed(4))))
      .join(", "),
    prepayment_treasury_pct: pct(layer.prepayment_treasury_rate ?? null),
    mip_annual_pct: pct(layer.mip_annual_rate ?? 0),
    mip_upfront_pct: pct(layer.mip_upfront_rate ?? 0),
    expanded: false,
  };
}

/**
 * The form's starting stack for an existing deal. A deal saved before
 * capital stacks existed gets its single loan as an "Other" senior layer
 * (its type was never recorded) plus a sponsor equity layer.
 */
export function initialLayers(deal: DealOut | null, defaults: () => LayerForm[]): LayerForm[] {
  if (!deal) return defaults();
  if (deal.capital_stack && deal.capital_stack.length > 0) {
    return deal.capital_stack.map(layerToForm);
  }
  const equity = { ...blankLayer("sponsor_gp"), amount: "0" };
  if (deal.loan_amount <= 0) {
    return [
      { ...blankLayer("all_cash"), amount: String(deal.purchase_price + deal.closing_costs) },
    ];
  }
  return [
    {
      ...blankLayer("other_senior"),
      label: "Senior loan",
      amount: String(deal.loan_amount),
      interest_rate_pct: pct(deal.interest_rate),
      amortization_years: String(deal.amortization_years),
    },
    equity,
  ];
}

function num(value: string): number | null {
  const parsed = Number(value);
  return value.trim() !== "" && Number.isFinite(parsed) ? parsed : null;
}

/** Resolved dollar amount, whichever way the user entered it. */
export function layerAmount(layer: LayerForm, totalCost: number): number {
  if (layer.amountMode === "percent") return ((num(layer.amountPct) ?? 0) / 100) * totalCost;
  return num(layer.amount) ?? 0;
}

/** All-in annual rate as a fraction: fixed rate, or index + spread. */
export function layerRate(layer: LayerForm): number {
  if (layer.rate_type === "floating") {
    return (num(layer.index_rate_pct) ?? 0) / 100 + (num(layer.spread_bps) ?? 0) / 10000;
  }
  return (num(layer.interest_rate_pct) ?? 0) / 100;
}

export function formToLayer(layer: LayerForm, totalCost: number): CapitalStackLayer {
  const debt = isDebtType(layer.type);
  const floating = debt && layer.rate_type === "floating";
  const pctToFraction = (v: string) => (num(v) === null ? null : (num(v) as number) / 100);
  return {
    type: layer.type,
    label: layer.label.trim() || null,
    amount: Math.round(layerAmount(layer, totalCost) * 100) / 100,
    rate_type: debt ? layer.rate_type : "fixed",
    interest_rate: debt && !floating ? pctToFraction(layer.interest_rate_pct) : null,
    index_name: floating ? layer.index_name.trim() || null : null,
    index_rate: floating ? pctToFraction(layer.index_rate_pct) : null,
    spread:
      floating && num(layer.spread_bps) !== null ? (num(layer.spread_bps) as number) / 10000 : null,
    io_months: debt ? (num(layer.io_months) ?? 0) : 0,
    amortization_years: debt ? num(layer.amortization_years) : null,
    term_years: debt ? num(layer.term_years) : null,
    recourse: debt && layer.recourse !== "" ? layer.recourse === "recourse" : null,
    rate_cap_cost: floating ? (num(layer.rate_cap_cost) ?? 0) : 0,
    origination_fee_rate:
      layerGroup(layer.type) !== "equity" ? (pctToFraction(layer.origination_fee_pct) ?? 0) : 0,
    preferred_return:
      layer.type === "preferred_equity" ? pctToFraction(layer.preferred_return_pct) : null,
    prepayment_type: debt ? layer.prepayment_type : "none",
    prepayment_schedule:
      debt && layer.prepayment_type === "step_down"
        ? (parseStepDown(layer.prepayment_schedule) ?? [])
        : [],
    prepayment_treasury_rate:
      debt &&
      (layer.prepayment_type === "yield_maintenance" || layer.prepayment_type === "defeasance")
        ? pctToFraction(layer.prepayment_treasury_pct)
        : null,
    mip_annual_rate: allowsMortgageInsurance(layer.type)
      ? (pctToFraction(layer.mip_annual_pct) ?? 0)
      : 0,
    mip_upfront_rate: allowsMortgageInsurance(layer.type)
      ? (pctToFraction(layer.mip_upfront_pct) ?? 0)
      : 0,
  };
}

// ---------------------------------------------------------------------------
// Validation (mirrors backend validate_capital_stack, plus field checks)
// ---------------------------------------------------------------------------

export function validateLayers(layers: LayerForm[], totalCost: number): string[] {
  const errors: string[] = [];
  const seniors = layers.filter((l) => layerGroup(l.type) === "senior");
  const equity = layers.filter((l) => layerGroup(l.type) === "equity");
  const allCash = layers.some((l) => l.type === "all_cash");

  if (allCash) {
    if (layers.some((l) => isDebtType(l.type))) {
      errors.push("An all-cash deal can't also have debt layers.");
    }
  } else if (seniors.length === 0) {
    errors.push(
      "Add exactly one senior debt layer, or an All cash equity layer if the deal has no debt.",
    );
  } else if (seniors.length > 1) {
    errors.push("Only one senior debt layer is allowed.");
  }
  if (equity.length === 0) errors.push("Add at least one equity layer.");

  layers.forEach((layer, i) => {
    const name = `Layer ${i + 1} (${layerDisplayName(layer.type, layer.label)})`;
    const amount = layerAmount(layer, totalCost);
    if (isOtherType(layer.type) && layer.label.trim() === "") {
      errors.push(`Layer ${i + 1}: give this Other layer a name.`);
    }
    if (amount < 0) errors.push(`${name}: amount can't be negative.`);

    if (layer.type === "preferred_equity") {
      if (amount <= 0) errors.push(`${name}: enter an amount above zero.`);
      const pref = num(layer.preferred_return_pct);
      if (pref === null || pref < 0 || pref > 100)
        errors.push(`${name}: enter a preferred return.`);
    }
    if (!isDebtType(layer.type)) return;

    if (amount <= 0) errors.push(`${name}: enter an amount above zero.`);
    if (layer.rate_type === "floating") {
      const indexRate = num(layer.index_rate_pct);
      const spread = num(layer.spread_bps);
      if (indexRate === null || spread === null) {
        errors.push(`${name}: floating-rate layers need an index rate and a spread.`);
      } else {
        if (indexRate < 0 || indexRate > 100) {
          errors.push(`${name}: the index rate must be between 0 and 100%.`);
        }
        if (spread < 0) errors.push(`${name}: the spread can't be negative.`);
      }
    } else {
      const rate = num(layer.interest_rate_pct);
      if (rate === null || rate < 0 || rate > 100) errors.push(`${name}: enter an interest rate.`);
    }
    const io = num(layer.io_months) ?? 0;
    const term = num(layer.term_years);
    const amort = num(layer.amortization_years);
    if (io < 0 || !Number.isInteger(io))
      errors.push(`${name}: interest-only months must be a whole number.`);
    else if (io > MAX_IO_MONTHS)
      errors.push(`${name}: interest-only months can't exceed ${MAX_IO_MONTHS}.`);
    if (term !== null && (term <= 0 || term > 50 || !Number.isInteger(term))) {
      errors.push(`${name}: term must be 1–50 whole years.`);
    }
    if (amort !== null && (amort <= 0 || amort > 50 || !Number.isInteger(amort))) {
      errors.push(`${name}: amortization must be 1–50 whole years.`);
    }
    if (term !== null && io > term * 12)
      errors.push(`${name}: interest-only months can't exceed the term.`);
    if (amort !== null && io >= amort * 12) {
      errors.push(`${name}: the amortization period must be longer than the interest-only period.`);
    }

    if (layer.prepayment_type === "step_down") {
      const steps = parseStepDown(layer.prepayment_schedule);
      if (steps === null || steps.length === 0) {
        errors.push(`${name}: enter the step-down percentages by year, e.g. 5, 4, 3, 2, 1.`);
      } else if (steps.some((r) => r < 0 || r > 1)) {
        errors.push(`${name}: step-down percentages must be between 0 and 100.`);
      }
    } else if (
      layer.prepayment_type === "yield_maintenance" ||
      layer.prepayment_type === "defeasance"
    ) {
      if (term === null) {
        errors.push(`${name}: yield maintenance and defeasance need a term / maturity.`);
      }
      const treasury = num(layer.prepayment_treasury_pct);
      if (treasury === null || treasury < 0 || treasury > 100) {
        errors.push(`${name}: enter the Treasury rate for the prepayment calculation.`);
      }
    }
    if (allowsMortgageInsurance(layer.type)) {
      for (const [label, value] of [
        ["annual", layer.mip_annual_pct],
        ["upfront", layer.mip_upfront_pct],
      ]) {
        const mip = num(value);
        if (value.trim() !== "" && (mip === null || mip < 0 || mip > 5)) {
          errors.push(`${name}: ${label} mortgage insurance must be between 0 and 5%.`);
        }
      }
    }
  });

  if (totalCost > 0 && !commonEquityOk(layers, totalCost)) {
    errors.push(
      "Debt and preferred equity must leave at least 5% of total cost (price, closing costs " +
        "and upfront financing costs) as common equity.",
    );
  }
  return errors;
}

/** Longest interest-only period the backend accepts, in months. */
export const MAX_IO_MONTHS = 600;
/** Mirrors backend MIN_COMMON_EQUITY_SHARE (engine/financing.py). */
export const MIN_COMMON_EQUITY_SHARE = 0.05;

/**
 * Mirrors backend common_equity_errors: total cost is price + closing costs
 * (`priceAndClosing`, the same base "% of total cost" amounts use) plus every
 * layer's upfront financing cost (origination fee, rate cap, upfront MIP);
 * common equity = total cost − all debt − preferred equity, and must be at
 * least 5% of total cost.
 */
export function commonEquityOk(layers: LayerForm[], priceAndClosing: number): boolean {
  const upfront = layers.reduce((sum, l) => sum + upfrontCost(l, priceAndClosing), 0);
  const total = priceAndClosing + upfront;
  const financed = layers
    .filter((l) => isDebtType(l.type) || l.type === "preferred_equity")
    .reduce((sum, l) => sum + layerAmount(l, priceAndClosing), 0);
  return total - financed >= total * MIN_COMMON_EQUITY_SHARE;
}

// ---------------------------------------------------------------------------
// Live estimates for the form's summary card
// ---------------------------------------------------------------------------

function levelPayment(principal: number, annualRate: number, months: number): number {
  if (principal <= 0 || months <= 0) return 0;
  const r = annualRate / 12;
  if (r === 0) return principal / months;
  const f = Math.pow(1 + r, months);
  return (principal * r * f) / (f - 1);
}

/** Origination fee, rate cap and upfront mortgage insurance, paid at closing. */
export function upfrontCost(layer: LayerForm, totalCost: number): number {
  if (layerGroup(layer.type) === "equity") return 0;
  const amount = layerAmount(layer, totalCost);
  const fee = ((num(layer.origination_fee_pct) ?? 0) / 100) * amount;
  const cap =
    isDebtType(layer.type) && layer.rate_type === "floating" ? (num(layer.rate_cap_cost) ?? 0) : 0;
  const mip = allowsMortgageInsurance(layer.type)
    ? ((num(layer.mip_upfront_pct) ?? 0) / 100) * amount
    : 0;
  return fee + cap + mip;
}

/** Year 1 debt service for one debt layer, month by month (I/O then amortizing). */
export function yearOneDebtService(layer: LayerForm, totalCost: number): number {
  if (!isDebtType(layer.type)) return 0;
  const amount = layerAmount(layer, totalCost);
  const rate = layerRate(layer);
  const io = num(layer.io_months) ?? 0;
  const amort = num(layer.amortization_years);
  const term = num(layer.term_years);
  const mipRate = allowsMortgageInsurance(layer.type) ? (num(layer.mip_annual_pct) ?? 0) / 100 : 0;
  let balance = amount;
  let payment: number | null = null;
  let total = 0;
  for (let month = 1; month <= 12; month += 1) {
    if (balance <= 0) break;
    const interest = (balance * rate) / 12;
    // FHA mortgage insurance on the opening balance, paid with debt service.
    total += (balance * mipRate) / 12;
    let principal = 0;
    if (amort !== null && month > io) {
      payment ??= levelPayment(balance, rate, amort * 12 - io);
      principal = Math.min(payment - interest, balance);
    }
    balance -= principal;
    total += interest + principal;
    if (term !== null && month === term * 12) balance = 0;
  }
  return total;
}
