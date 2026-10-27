import { useEffect, useRef, useState } from "react";
import {
  LAYER_OPTIONS,
  blankLayer,
  formToLayer,
  initialLayers,
  layerAmount,
  layerGroup,
  validateLayers,
  withDefaultTreasury,
} from "../lib/capitalStack";
import type { LayerForm } from "../lib/capitalStack";
import {
  describeError,
  downloadImportTemplate,
  getHurdles,
  importSpreadsheet,
} from "../lib/client";
import { fractionToPercentInput, percentInputToFraction } from "../lib/format";
import { SUB_ASSET_CLASS_LABELS } from "../lib/types";
import type { DealCreate, DealOut, ImportProposal, LeasingMode, SubAssetClass } from "../lib/types";
import { CapitalStackEditor } from "./CapitalStackEditor";
import { ImportReview } from "./ImportReview";
import type { ConfirmedImport } from "./ImportReview";
import { NumberInput } from "./NumberInput";

interface UnitMixTier {
  id: string;
  name: string;
  units: string;
  bedsPerUnit: string;
  avgSqFt: string;
  rent: string;
}

interface FormState {
  name: string;
  sub_asset_class: SubAssetClass;
  leasing_mode: LeasingMode;
  unit_count: string;
  monthly_rent_per_unit: string;
  bed_count: string;
  monthly_rent_per_bed: string;
  vacancy_rate_pct: string;
  other_income_annual: string;
  other_income_growth_rate_pct: string;
  credit_loss_rate_pct: string;
  management_fee_rate_pct: string;
  replacement_reserve_per_unit_or_bed: string;
  opex_annual: string;
  expense_growth_rate_pct: string;
  rent_growth_rate_pct: string;
  lease_expiration_month: string;
  turnover_cost_per_unit_or_bed: string;
  annual_turnover_rate_pct: string;
  purchase_price: string;
  closing_costs: string;
  // Only kept so a deal saved before capital stacks keeps its loan's
  // amortization if the user picks an all-cash or interest-only stack.
  amortization_years: string;
  hold_period_years: string;
  exit_cap_rate_pct: string;
  selling_costs_rate_pct: string;

  // Suburban Garden specific
  surface_parking_stalls: string;
  covered_parking_stalls: string;
  parking_monthly_rate: string;
  parking_occupancy_pct: string;
  storage_units: string;
  storage_monthly_fee: string;
  pet_monthly_fee: string;
  pet_penetration_pct: string;

  // Student Housing specific
  tech_package_monthly_fee: string;
  furniture_package_monthly_fee: string;

  // Urban Mid-Rise specific
  garage_parking_stalls: string;
  garage_monthly_rate: string;
  commercial_retail_sqft: string;
  commercial_rent_sqft_annual: string;
}

const DEFAULT_UNIT_MIX: UnitMixTier[] = [
  { id: "studio", name: "Studio", units: "20", bedsPerUnit: "1", avgSqFt: "520", rent: "1250" },
  { id: "1bed", name: "1 Bed / 1 Bath", units: "50", bedsPerUnit: "1", avgSqFt: "710", rent: "1450" },
  { id: "2bed", name: "2 Bed / 2 Bath", units: "60", bedsPerUnit: "2", avgSqFt: "960", rent: "1850" },
  { id: "3bed", name: "3 Bed / 2 Bath", units: "15", bedsPerUnit: "3", avgSqFt: "1220", rent: "2250" },
  { id: "4bed_plus", name: "4+ Bed", units: "5", bedsPerUnit: "4", avgSqFt: "1450", rent: "2600" },
];

const DEFAULTS: FormState = {
  name: "",
  sub_asset_class: "suburban_garden",
  leasing_mode: "per_unit",
  unit_count: "150",
  monthly_rent_per_unit: "1650",
  bed_count: "",
  monthly_rent_per_bed: "",
  vacancy_rate_pct: "5",
  other_income_annual: "48000",
  other_income_growth_rate_pct: "0",
  credit_loss_rate_pct: "0",
  management_fee_rate_pct: "0",
  replacement_reserve_per_unit_or_bed: "0",
  opex_annual: "650000",
  expense_growth_rate_pct: "3",
  rent_growth_rate_pct: "3",
  lease_expiration_month: "6",
  turnover_cost_per_unit_or_bed: "750",
  annual_turnover_rate_pct: "50",
  purchase_price: "22000000",
  closing_costs: "440000",
  amortization_years: "30",
  hold_period_years: "10",
  exit_cap_rate_pct: "5.75",
  selling_costs_rate_pct: "2",

  surface_parking_stalls: "180",
  covered_parking_stalls: "40",
  parking_monthly_rate: "50",
  parking_occupancy_pct: "85",
  storage_units: "30",
  storage_monthly_fee: "65",
  pet_monthly_fee: "35",
  pet_penetration_pct: "35",

  tech_package_monthly_fee: "55",
  furniture_package_monthly_fee: "40",

  garage_parking_stalls: "110",
  garage_monthly_rate: "150",
  commercial_retail_sqft: "4500",
  commercial_rent_sqft_annual: "32",
};

/** A new deal starts with a typical agency loan plus sponsor equity. */
function defaultLayers(): LayerForm[] {
  return [
    {
      ...blankLayer("agency_fannie_mae"),
      amount: "14300000",
      interest_rate_pct: "6.25",
      amortization_years: "30",
      term_years: "10",
      recourse: "non_recourse",
    },
    { ...blankLayer("sponsor_gp"), amount: "8140000" },
  ];
}

function dealToFormState(deal: DealOut): FormState {
  return {
    ...DEFAULTS,
    name: deal.name,
    sub_asset_class: deal.sub_asset_class,
    leasing_mode: deal.leasing_mode,
    unit_count: deal.unit_count?.toString() ?? "",
    monthly_rent_per_unit: deal.monthly_rent_per_unit?.toString() ?? "",
    bed_count: deal.bed_count?.toString() ?? "",
    monthly_rent_per_bed: deal.monthly_rent_per_bed?.toString() ?? "",
    vacancy_rate_pct: fractionToPercentInput(deal.vacancy_rate),
    other_income_annual: deal.other_income_annual.toString(),
    other_income_growth_rate_pct: fractionToPercentInput(deal.other_income_growth_rate),
    credit_loss_rate_pct: fractionToPercentInput(deal.credit_loss_rate),
    management_fee_rate_pct: fractionToPercentInput(deal.management_fee_rate),
    replacement_reserve_per_unit_or_bed: deal.replacement_reserve_per_unit_or_bed.toString(),
    opex_annual: deal.opex_annual.toString(),
    expense_growth_rate_pct: fractionToPercentInput(deal.expense_growth_rate),
    rent_growth_rate_pct: fractionToPercentInput(deal.rent_growth_rate),
    lease_expiration_month: deal.lease_expiration_month.toString(),
    turnover_cost_per_unit_or_bed: deal.turnover_cost_per_unit_or_bed.toString(),
    annual_turnover_rate_pct: fractionToPercentInput(deal.annual_turnover_rate),
    purchase_price: deal.purchase_price.toString(),
    closing_costs: deal.closing_costs.toString(),
    amortization_years: deal.amortization_years.toString(),
    hold_period_years: deal.hold_period_years.toString(),
    exit_cap_rate_pct: fractionToPercentInput(deal.exit_cap_rate),
    selling_costs_rate_pct: fractionToPercentInput(deal.selling_costs_rate),
  };
}

/** Spreadsheet import keys that describe the capital stack, not the form. */
const FINANCING_KEYS = new Set([
  "senior_loan_type",
  "loan_amount",
  "rate_type",
  "interest_rate_pct",
  "index_name",
  "index_rate_pct",
  "spread_bps",
  "io_months",
  "amortization_years",
  "term_years",
  "recourse",
  "origination_fee_pct",
  "rate_cap_cost",
  "mezzanine_loan_amount",
  "mezzanine_interest_rate_pct",
  "preferred_equity_amount",
  "preferred_return_pct",
]);

/**
 * Builds the capital stack from imported financing values: the senior
 * loan, plus mezzanine and preferred equity layers when their amounts are
 * above zero. Equity layers already on the form are kept (a sponsor layer
 * is added if there are none). Also reads the older template's
 * loan_structure / io_period_years / sofr_base_rate_pct / loan_term_years.
 */
function layersFromFinancingCsv(data: Record<string, string>, current: LayerForm[]): LayerForm[] {
  const n = (key: string) => (data[key] ?? "").trim();
  const positive = (key: string) => Number(n(key)) > 0;

  const seniorType = n("senior_loan_type") as LayerForm["type"];
  const knownSenior = LAYER_OPTIONS.some((o) => o.type === seniorType && o.group === "senior");
  const floating = n("rate_type") === "floating" || n("loan_structure") === "floating_rate";
  const ioMonths =
    n("io_months") || (n("io_period_years") ? String(Number(n("io_period_years")) * 12) : "0");

  const senior: LayerForm = {
    ...blankLayer(knownSenior ? seniorType : "other_senior"),
    label: knownSenior ? "" : "Senior loan",
    amount: n("loan_amount"),
    rate_type: floating ? "floating" : "fixed",
    interest_rate_pct: n("interest_rate_pct"),
    index_name: n("index_name") || "SOFR",
    index_rate_pct: n("index_rate_pct") || n("sofr_base_rate_pct"),
    spread_bps: n("spread_bps"),
    io_months: ioMonths,
    amortization_years: n("amortization_years") || "30",
    term_years: n("term_years") || n("loan_term_years"),
    recourse: n("recourse") === "recourse" || n("recourse") === "non_recourse" ? (n("recourse") as LayerForm["recourse"]) : "",
    origination_fee_pct: n("origination_fee_pct") || "0",
    rate_cap_cost: n("rate_cap_cost") || "0",
  };
  const next: LayerForm[] = [senior];
  if (positive("mezzanine_loan_amount")) {
    next.push({
      ...blankLayer("mezzanine"),
      amount: n("mezzanine_loan_amount"),
      interest_rate_pct: n("mezzanine_interest_rate_pct"),
    });
  }
  if (positive("preferred_equity_amount")) {
    next.push({
      ...blankLayer("preferred_equity"),
      amount: n("preferred_equity_amount"),
      preferred_return_pct: n("preferred_return_pct"),
    });
  }
  const equity = current.filter((l) => layerGroup(l.type) === "equity" && l.type !== "all_cash");
  return [...next, ...(equity.length > 0 ? equity : [blankLayer("sponsor_gp")])];
}

type FieldErrors = Partial<Record<keyof FormState, string>>;

/** Ancillary-income inputs that can't be negative, and the ones that are percentages. */
const ANCILLARY_AMOUNTS: (keyof FormState)[] = [
  "surface_parking_stalls",
  "covered_parking_stalls",
  "parking_monthly_rate",
  "storage_units",
  "storage_monthly_fee",
  "pet_monthly_fee",
  "tech_package_monthly_fee",
  "furniture_package_monthly_fee",
  "garage_parking_stalls",
  "garage_monthly_rate",
  "commercial_retail_sqft",
  "commercial_rent_sqft_annual",
];
const ANCILLARY_PERCENTS: (keyof FormState)[] = ["parking_occupancy_pct", "pet_penetration_pct"];

/** Negative or out-of-range entries in the unit mix and the ancillary-income helpers. */
function validateExtras(form: FormState, unitMix: UnitMixTier[]): string[] {
  const problems: string[] = [];
  for (const key of ANCILLARY_AMOUNTS) {
    const value = parseNumber(form[key] as string);
    if (!isBlank(form[key] as string) && (value === null || value < 0)) {
      problems.push(`${key.replace(/_/g, " ")} can't be negative.`);
    }
  }
  for (const key of ANCILLARY_PERCENTS) {
    const value = parseNumber(form[key] as string);
    if (!isBlank(form[key] as string) && (value === null || value < 0 || value > 100)) {
      problems.push(`${key.replace(/_/g, " ")} must be between 0 and 100.`);
    }
  }
  for (const tier of unitMix) {
    for (const [label, raw] of [
      ["units", tier.units],
      ["avg sq ft", tier.avgSqFt],
      ["rent", tier.rent],
    ] as const) {
      const value = parseNumber(raw);
      if (value === null || value < 0) {
        problems.push(`Unit mix "${tier.name}": ${label} can't be negative.`);
      }
    }
    const beds = parseNumber(tier.bedsPerUnit);
    if (beds === null || beds < 1) {
      problems.push(`Unit mix "${tier.name}": beds per unit must be at least 1.`);
    }
  }
  return problems;
}

function isBlank(value: string): boolean {
  return value.trim() === "";
}

function parseNumber(value: string): number | null {
  const parsed = Number(value);
  return value.trim() !== "" && Number.isFinite(parsed) ? parsed : null;
}

function validate(form: FormState): FieldErrors {
  const errors: FieldErrors = {};
  const isPerUnit = form.leasing_mode === "per_unit";

  if (isBlank(form.name)) errors.name = "Name is required.";
  else if (form.name.trim().length > 255) errors.name = "Keep the name under 256 characters.";

  if (isPerUnit) {
    const units = parseNumber(form.unit_count);
    if (units === null || units <= 0) errors.unit_count = "Enter a positive unit count.";
    const rent = parseNumber(form.monthly_rent_per_unit);
    if (rent === null || rent <= 0) errors.monthly_rent_per_unit = "Enter a positive rent.";
  } else {
    const beds = parseNumber(form.bed_count);
    if (beds === null || beds <= 0) errors.bed_count = "Enter a positive bed count.";
    const rent = parseNumber(form.monthly_rent_per_bed);
    if (rent === null || rent <= 0) errors.monthly_rent_per_bed = "Enter a positive rent.";
  }

  const vacancy = parseNumber(form.vacancy_rate_pct);
  if (vacancy === null || vacancy < 0 || vacancy > 100) {
    errors.vacancy_rate_pct = "Enter a percentage between 0 and 100.";
  }

  if (!isBlank(form.other_income_annual)) {
    const otherIncome = parseNumber(form.other_income_annual);
    if (otherIncome === null || otherIncome < 0) {
      errors.other_income_annual = "Enter a non-negative amount.";
    }
  }

  const opex = parseNumber(form.opex_annual);
  if (opex === null || opex < 0) errors.opex_annual = "Enter a non-negative amount.";

  const expenseGrowth = parseNumber(form.expense_growth_rate_pct);
  if (expenseGrowth === null || expenseGrowth < 0 || expenseGrowth > 100) {
    errors.expense_growth_rate_pct = "Enter a percentage from 0 to 100.";
  }
  const otherGrowth = parseNumber(form.other_income_growth_rate_pct);
  if (otherGrowth === null || otherGrowth <= -100 || otherGrowth > 100) {
    errors.other_income_growth_rate_pct = "Enter a percentage above -100 and up to 100.";
  }
  const creditLoss = parseNumber(form.credit_loss_rate_pct);
  if (creditLoss === null || creditLoss < 0 || creditLoss > 100) {
    errors.credit_loss_rate_pct = "Enter a percentage between 0 and 100.";
  }
  const mgmtFee = parseNumber(form.management_fee_rate_pct);
  if (mgmtFee === null || mgmtFee < 0 || mgmtFee > 100) {
    errors.management_fee_rate_pct = "Enter a percentage between 0 and 100.";
  }
  const reserve = parseNumber(form.replacement_reserve_per_unit_or_bed);
  if (reserve === null || reserve < 0) {
    errors.replacement_reserve_per_unit_or_bed = "Enter a non-negative amount.";
  }
  const rentGrowth = parseNumber(form.rent_growth_rate_pct);
  if (rentGrowth === null || rentGrowth <= -100 || rentGrowth > 100) {
    errors.rent_growth_rate_pct = "Enter a percentage above -100 and up to 100.";
  }

  const month = parseNumber(form.lease_expiration_month);
  if (month === null || month < 1 || month > 12 || !Number.isInteger(month)) {
    errors.lease_expiration_month = "Enter a month from 1 to 12.";
  }

  const turnoverCost = parseNumber(form.turnover_cost_per_unit_or_bed);
  if (turnoverCost === null || turnoverCost < 0) {
    errors.turnover_cost_per_unit_or_bed = "Enter a non-negative amount.";
  }
  const turnoverRate = parseNumber(form.annual_turnover_rate_pct);
  if (turnoverRate === null || turnoverRate < 0 || turnoverRate > 100) {
    errors.annual_turnover_rate_pct = "Enter a percentage between 0 and 100.";
  }

  const price = parseNumber(form.purchase_price);
  if (price === null || price <= 0) errors.purchase_price = "Enter a positive amount.";

  const closingCosts = parseNumber(form.closing_costs);
  if (closingCosts === null || closingCosts < 0) {
    errors.closing_costs = "Enter a non-negative amount.";
  }

  const holdYears = parseNumber(form.hold_period_years);
  if (holdYears === null || holdYears <= 0 || holdYears > 30 || !Number.isInteger(holdYears)) {
    errors.hold_period_years = "Enter a whole number of years from 1 to 30.";
  }

  const exitCap = parseNumber(form.exit_cap_rate_pct);
  if (exitCap === null || exitCap <= 0 || exitCap > 100) {
    errors.exit_cap_rate_pct = "Enter a percentage above 0 and up to 100.";
  }

  const sellingCosts = parseNumber(form.selling_costs_rate_pct);
  if (sellingCosts === null || sellingCosts < 0 || sellingCosts >= 100) {
    errors.selling_costs_rate_pct = "Enter a percentage from 0 up to (not including) 100.";
  }

  return errors;
}

interface DealFormProps {
  initial: DealOut | null;
  onSave: (input: DealCreate) => Promise<void>;
  onCancel: () => void;
}

export function DealForm({ initial, onSave, onCancel }: DealFormProps) {
  const [form, setForm] = useState<FormState>(initial ? dealToFormState(initial) : DEFAULTS);
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [unitMix, setUnitMix] = useState<UnitMixTier[]>(
    initial?.unit_mix
      ? initial.unit_mix.map((t) => ({
          id: t.id,
          name: t.name,
          units: t.units.toString(),
          bedsPerUnit: t.beds_per_unit.toString(),
          avgSqFt: t.avg_sqft.toString(),
          rent: t.rent.toString(),
        }))
      : DEFAULT_UNIT_MIX,
  );
  const [showUnitMix, setShowUnitMix] = useState<boolean>(true);
  const [importNotice, setImportNotice] = useState<{ message: string; type: "success" | "error" } | null>(null);
  const [layers, setLayers] = useState<LayerForm[]>(() => initialLayers(initial, defaultLayers));
  const [stackErrors, setStackErrors] = useState<string[]>([]);
  // The 10-Year Treasury (live, or the configured fallback) pre-fills the
  // Treasury rate on yield maintenance / defeasance layers. If it can't be
  // fetched the user just types one in.
  const [treasuryPct, setTreasuryPct] = useState("");

  useEffect(() => {
    let cancelled = false;
    getHurdles()
      .then((table) => {
        if (cancelled) return;
        const pct = String(Number((table.treasury.yield * 100).toFixed(2)));
        setTreasuryPct(pct);
        setLayers((prev) => withDefaultTreasury(prev, pct));
      })
      .catch(() => {
        /* no market rate available; the field stays for the user to fill */
      });
    return () => {
      cancelled = true;
    };
  }, []);

  function updateLayers(next: LayerForm[]) {
    setLayers(next);
    setStackErrors([]);
  }

  const importFileInputRef = useRef<HTMLInputElement | null>(null);
  const [importing, setImporting] = useState(false);
  const [proposal, setProposal] = useState<ImportProposal | null>(null);

  function set<K extends keyof FormState>(key: K, value: FormState[K]) {
    setForm((prev) => ({ ...prev, [key]: value }));
    setFieldErrors((prev) => {
      if (!(key in prev)) return prev;
      const next = { ...prev };
      delete next[key];
      return next;
    });
  }

  function fieldError(key: keyof FormState) {
    return fieldErrors[key] ? <span className="field-error-text">{fieldErrors[key]}</span> : null;
  }

  // --- Unit Mix Computations ---
  const totalMixUnits = unitMix.reduce((acc, row) => acc + (Number(row.units) || 0), 0);
  const totalMixBeds = unitMix.reduce(
    (acc, row) => acc + (Number(row.units) || 0) * (Number(row.bedsPerUnit) || 1),
    0
  );
  const totalMonthlyGpr = unitMix.reduce(
    (acc, row) => acc + (Number(row.units) || 0) * (Number(row.rent) || 0),
    0
  );
  const weightedAvgRentPerUnit = totalMixUnits > 0 ? totalMonthlyGpr / totalMixUnits : 0;
  const totalMixSqFt = unitMix.reduce(
    (acc, row) => acc + (Number(row.units) || 0) * (Number(row.avgSqFt) || 0),
    0
  );
  const weightedAvgRentPerSqFt = totalMixSqFt > 0 ? totalMonthlyGpr / totalMixSqFt : 0;

  function updateUnitMixRow(id: string, field: keyof UnitMixTier, val: string) {
    setUnitMix((prev) =>
      prev.map((row) => (row.id === id ? { ...row, [field]: val } : row))
    );
  }

  function syncUnitMixToDeal() {
    if (form.leasing_mode === "per_unit") {
      set("unit_count", totalMixUnits.toString());
      set("monthly_rent_per_unit", weightedAvgRentPerUnit.toFixed(2));
    } else {
      set("bed_count", totalMixBeds.toString());
      const avgRentPerBed = totalMixBeds > 0 ? totalMonthlyGpr / totalMixBeds : 0;
      set("monthly_rent_per_bed", avgRentPerBed.toFixed(2));
    }
    setImportNotice({
      message: `Synchronized unit mix: ${totalMixUnits} units (${totalMixBeds} beds) at $${Math.round(weightedAvgRentPerUnit)}/mo average into deal GPR.`,
      type: "success",
    });
  }

  // --- Asset-Class Specific Calculations ---
  function calculateSuburbanGardenAncillary() {
    const surfaceStalls = Number(form.surface_parking_stalls) || 0;
    const coveredStalls = Number(form.covered_parking_stalls) || 0;
    const parkingRate = Number(form.parking_monthly_rate) || 0;
    const parkingOcc = (Number(form.parking_occupancy_pct) || 0) / 100;
    const annualParking = (surfaceStalls + coveredStalls) * parkingRate * parkingOcc * 12;

    const storageCount = Number(form.storage_units) || 0;
    const storageFee = Number(form.storage_monthly_fee) || 0;
    const annualStorage = storageCount * storageFee * 12;

    const units = Number(form.unit_count) || 0;
    const petFee = Number(form.pet_monthly_fee) || 0;
    const petPenetration = (Number(form.pet_penetration_pct) || 0) / 100;
    const annualPets = units * petPenetration * petFee * 12;

    const totalAncillary = Math.round(annualParking + annualStorage + annualPets);
    set("other_income_annual", totalAncillary.toString());
    setImportNotice({
      message: `Calculated Suburban Garden ancillary income: $${totalAncillary.toLocaleString()}/yr (Parking: $${Math.round(annualParking).toLocaleString()}, Storage: $${Math.round(annualStorage).toLocaleString()}, Pets: $${Math.round(annualPets).toLocaleString()}).`,
      type: "success",
    });
  }

  function calculateStudentHousingAncillary() {
    const beds = Number(form.bed_count) || (Number(form.unit_count) || 0) * 2;
    const techFee = Number(form.tech_package_monthly_fee) || 0;
    const furnitureFee = Number(form.furniture_package_monthly_fee) || 0;
    const annualPackages = Math.round(beds * (techFee + furnitureFee) * 12);

    set("other_income_annual", annualPackages.toString());
    setImportNotice({
      message: `Calculated Student Housing package fees: $${annualPackages.toLocaleString()}/yr across ${beds} beds.`,
      type: "success",
    });
  }

  function calculateUrbanMidRiseAncillary() {
    const garageStalls = Number(form.garage_parking_stalls) || 0;
    const garageRate = Number(form.garage_monthly_rate) || 0;
    const annualParking = garageStalls * garageRate * 12;

    const retailSqFt = Number(form.commercial_retail_sqft) || 0;
    const retailRent = Number(form.commercial_rent_sqft_annual) || 0;
    const annualRetail = retailSqFt * retailRent;

    const totalAncillary = Math.round(annualParking + annualRetail);
    set("other_income_annual", totalAncillary.toString());
    setImportNotice({
      message: `Calculated Urban Mid-Rise ancillary income: $${totalAncillary.toLocaleString()}/yr (Garage: $${Math.round(annualParking).toLocaleString()}, Retail NNN: $${Math.round(annualRetail).toLocaleString()}).`,
      type: "success",
    });
  }

  // --- Capital Stack ---
  const purchasePriceVal = Number(form.purchase_price) || 0;
  const closingCostsVal = Number(form.closing_costs) || 0;
  // "% of total cost" amounts are a share of price + closing costs.
  const totalCost = purchasePriceVal + closingCostsVal;

  // --- Spreadsheet import ---
  async function handleImportFile(file: File) {
    setImporting(true);
    setImportNotice(null);
    try {
      setProposal(await importSpreadsheet(file));
    } catch (err) {
      setImportNotice({
        message: `Couldn't read "${file.name}". ${describeError(err)}`,
        type: "error",
      });
    } finally {
      setImporting(false);
    }
  }

  async function handleDownloadTemplate() {
    try {
      await downloadImportTemplate();
    } catch (err) {
      setImportNotice({
        message: `Couldn't download the template. ${describeError(err)}`,
        type: "error",
      });
    }
  }

  /** Fills the form from the values the user confirmed on the review screen. */
  function applyImport({ values, unitMix: importedMix }: ConfirmedImport) {
    const next: FormState = { ...form };
    const formKeys = new Set(Object.keys(DEFAULTS));
    for (const [key, value] of Object.entries(values)) {
      if (formKeys.has(key)) (next as unknown as Record<string, string>)[key] = value;
    }
    if (importedMix) {
      // Units and average rent come from the mix unless the file gave them.
      const units = importedMix.reduce((acc, r) => acc + (Number(r.units) || 0), 0);
      const beds = importedMix.reduce(
        (acc, r) => acc + (Number(r.units) || 0) * (Number(r.bedsPerUnit) || 1),
        0,
      );
      const gpr = importedMix.reduce(
        (acc, r) => acc + (Number(r.units) || 0) * (Number(r.rent) || 0),
        0,
      );
      if (next.leasing_mode === "per_unit") {
        if (!values.unit_count) next.unit_count = units.toString();
        if (!values.monthly_rent_per_unit && units > 0) {
          next.monthly_rent_per_unit = (gpr / units).toFixed(2);
        }
      } else {
        if (!values.bed_count) next.bed_count = beds.toString();
        if (!values.monthly_rent_per_bed && beds > 0) {
          next.monthly_rent_per_bed = (gpr / beds).toFixed(2);
        }
      }
      setUnitMix(importedMix);
    }
    setForm(next);
    setFieldErrors({});

    const financing = Object.fromEntries(
      Object.entries(values).filter(([key]) => FINANCING_KEYS.has(key)),
    );
    if (Object.keys(financing).length > 0) {
      updateLayers(withDefaultTreasury(layersFromFinancingCsv(financing, layers), treasuryPct));
    }

    const count = Object.keys(values).length;
    setProposal(null);
    setImportNotice({
      message: `Filled ${count} field${count === 1 ? "" : "s"}${importedMix ? ` and ${importedMix.length} unit mix rows` : ""} from the spreadsheet. Review the form, then save.`,
      type: "success",
    });
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (submitting) return;

    const errors = validate(form);
    setFieldErrors(errors);
    const layerErrors = validateLayers(layers, totalCost);
    const seniorLayer = layers.find((layer) => layerGroup(layer.type) === "senior");
    if (seniorLayer && layerAmount(seniorLayer, totalCost) > purchasePriceVal) {
      layerErrors.push("The senior loan can't exceed the purchase price.");
    }
    setStackErrors(layerErrors);
    const extraErrors = validateExtras(form, unitMix);
    setSubmitError(extraErrors.length > 0 ? extraErrors.join(" ") : null);
    if (Object.keys(errors).length > 0 || layerErrors.length > 0 || extraErrors.length > 0) return;

    // The backend overwrites loan_amount / interest_rate /
    // amortization_years from the senior layer; send the same values so
    // the payload is self-consistent either way.
    const capitalStack = layers.map((layer) => formToLayer(layer, totalCost));
    const senior = capitalStack.find((layer) => layerGroup(layer.type) === "senior");
    const seniorRate = senior
      ? senior.rate_type === "floating"
        ? (senior.index_rate ?? 0) + (senior.spread ?? 0)
        : senior.interest_rate ?? 0
      : 0;

    const isPerUnit = form.leasing_mode === "per_unit";
    const input: DealCreate = {
      name: form.name.trim(),
      sub_asset_class: form.sub_asset_class,
      leasing_mode: form.leasing_mode,
      unit_count: isPerUnit ? Number(form.unit_count) : null,
      monthly_rent_per_unit: isPerUnit ? Number(form.monthly_rent_per_unit) : null,
      bed_count: isPerUnit ? null : Number(form.bed_count),
      monthly_rent_per_bed: isPerUnit ? null : Number(form.monthly_rent_per_bed),
      vacancy_rate: percentInputToFraction(form.vacancy_rate_pct),
      other_income_annual: Number(form.other_income_annual) || 0,
      other_income_growth_rate: percentInputToFraction(form.other_income_growth_rate_pct),
      credit_loss_rate: percentInputToFraction(form.credit_loss_rate_pct),
      management_fee_rate: percentInputToFraction(form.management_fee_rate_pct),
      replacement_reserve_per_unit_or_bed: Number(form.replacement_reserve_per_unit_or_bed) || 0,
      unit_mix: unitMix.map((t) => ({
        id: t.id,
        name: t.name,
        units: Math.round(Number(t.units) || 0),
        beds_per_unit: Math.max(1, Math.round(Number(t.bedsPerUnit) || 1)),
        avg_sqft: Math.round(Number(t.avgSqFt) || 0),
        rent: Number(t.rent) || 0,
      })),
      opex_annual: Number(form.opex_annual) || 0,
      expense_growth_rate: percentInputToFraction(form.expense_growth_rate_pct),
      rent_growth_rate: percentInputToFraction(form.rent_growth_rate_pct),
      lease_expiration_month: Number(form.lease_expiration_month) || 1,
      turnover_cost_per_unit_or_bed: Number(form.turnover_cost_per_unit_or_bed) || 0,
      annual_turnover_rate: percentInputToFraction(form.annual_turnover_rate_pct),
      purchase_price: Number(form.purchase_price) || 0,
      closing_costs: Number(form.closing_costs) || 0,
      loan_amount: senior?.amount ?? 0,
      interest_rate: seniorRate,
      amortization_years: senior?.amortization_years ?? (Number(form.amortization_years) || 30),
      capital_stack: capitalStack,
      hold_period_years: Number(form.hold_period_years) || 0,
      exit_cap_rate: percentInputToFraction(form.exit_cap_rate_pct),
      selling_costs_rate: percentInputToFraction(form.selling_costs_rate_pct),
    };

    setSubmitting(true);
    setSubmitError(null);
    try {
      await onSave(input);
    } catch (err) {
      // Keep the form open with the user's input and say what went wrong.
      setSubmitError(`Couldn't save the deal. ${describeError(err)}`);
      setSubmitting(false);
    }
  }

  const isPerUnit = form.leasing_mode === "per_unit";

  return (
    <form className="card" onSubmit={handleSubmit}>
      <h2>{initial ? "Edit deal" : "New deal"}</h2>

      <div className="import-toolbar">
        <div className="import-toolbar-title">
          <span>Import from a spreadsheet</span>
          <span className="import-toolbar-hint">
            Use the template or your own Excel model. You review every value before it&apos;s filled in.
          </span>
        </div>
        <div className="import-actions">
          <input
            type="file"
            ref={importFileInputRef}
            style={{ display: "none" }}
            accept=".xlsx,.xlsm,.csv,.tsv"
            onChange={(e) => {
              const file = e.target.files?.[0];
              // Reset so picking the same file again still fires onChange.
              e.target.value = "";
              if (file) void handleImportFile(file);
            }}
          />
          <button
            type="button"
            className="import-btn"
            disabled={importing}
            onClick={() => importFileInputRef.current?.click()}
          >
            {importing ? "Reading…" : "Import spreadsheet"}
          </button>
          <button type="button" className="import-btn" onClick={handleDownloadTemplate}>
            Download template
          </button>
        </div>
      </div>

      {proposal && (
        <ImportReview
          proposal={proposal}
          onApply={applyImport}
          onCancel={() => setProposal(null)}
        />
      )}

      {importNotice && (
        <div className={`import-alert ${importNotice.type}`}>
          <span>{importNotice.message}</span>
          <button
            type="button"
            style={{ background: "none", border: "none", cursor: "pointer", fontWeight: "bold" }}
            onClick={() => setImportNotice(null)}
          >
            ✕
          </button>
        </div>
      )}

      {/* Basic Info */}
      <h3>Basics</h3>
      <div className="field-grid">
        <div className="field">
          <label htmlFor="name">Deal name</label>
          <input
            id="name"
            value={form.name}
            onChange={(e) => set("name", e.target.value)}
            maxLength={255}
            placeholder="e.g. Campus View Student Housing"
            aria-invalid={!!fieldErrors.name}
          />
          {fieldError("name")}
        </div>
        <div className="field">
          <label htmlFor="sub_asset_class">Sub-asset class</label>
          <select
            id="sub_asset_class"
            value={form.sub_asset_class}
            onChange={(e) => set("sub_asset_class", e.target.value as SubAssetClass)}
          >
            {Object.entries(SUB_ASSET_CLASS_LABELS).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Asset-Class Specific Custom Inputs */}
      <div className="housing-custom-card">
        <div className="housing-custom-header">
          <h4>
            <span>⚙️</span>
            <span>Asset-Class Tailored Inputs</span>
            <span className="badge-asset-class">{SUB_ASSET_CLASS_LABELS[form.sub_asset_class]}</span>
          </h4>
        </div>

        {form.sub_asset_class === "suburban_garden" && (
          <>
            <p className="housing-helper-note">
              Suburban Garden properties capture ancillary revenue from parking spaces, garages, storage lockers, pet rent, and RUBS utility reimbursements.
            </p>
            <div className="field-grid">
              <div className="field">
                <label>Surface Parking Stalls</label>
                <NumberInput
                  value={form.surface_parking_stalls}
                  onChange={(v) => set("surface_parking_stalls", v)}
                />
              </div>
              <div className="field">
                <label>Covered/Garage Stalls</label>
                <NumberInput
                  value={form.covered_parking_stalls}
                  onChange={(v) => set("covered_parking_stalls", v)}
                />
              </div>
              <div className="field">
                <label>Monthly Parking Fee ($/stall)</label>
                <NumberInput
                  value={form.parking_monthly_rate}
                  onChange={(v) => set("parking_monthly_rate", v)}
                />
              </div>
              <div className="field">
                <label>Parking Occupancy (%)</label>
                <input
                  type="number"
                  min="0"
                  value={form.parking_occupancy_pct}
                  onChange={(e) => set("parking_occupancy_pct", e.target.value)}
                />
              </div>
              <div className="field">
                <label>Storage Units</label>
                <NumberInput
                  value={form.storage_units}
                  onChange={(v) => set("storage_units", v)}
                />
              </div>
              <div className="field">
                <label>Storage Fee ($/mo)</label>
                <NumberInput
                  value={form.storage_monthly_fee}
                  onChange={(v) => set("storage_monthly_fee", v)}
                />
              </div>
              <div className="field">
                <label>Monthly Pet Fee ($/unit)</label>
                <NumberInput
                  value={form.pet_monthly_fee}
                  onChange={(v) => set("pet_monthly_fee", v)}
                />
              </div>
              <div className="field">
                <label>Pet Penetration Rate (%)</label>
                <input
                  type="number"
                  min="0"
                  value={form.pet_penetration_pct}
                  onChange={(e) => set("pet_penetration_pct", e.target.value)}
                />
              </div>
            </div>
            <div style={{ marginTop: "12px", textAlign: "right" }}>
              <button
                type="button"
                className="sync-action-btn"
                onClick={calculateSuburbanGardenAncillary}
              >
                Apply Parking &amp; Ancillary to Other Income
              </button>
            </div>
          </>
        )}

        {form.sub_asset_class === "student_housing" && (
          <>
            <p className="housing-helper-note">
              Student Housing underwrites on a per-bed basis with August turn concentration and mandatory fee packages (Wi-Fi/tech and furniture).
            </p>
            <div className="field-grid">
              <div className="field">
                <label>Tech &amp; Wi-Fi Package ($/bed/mo)</label>
                <NumberInput
                  value={form.tech_package_monthly_fee}
                  onChange={(v) => set("tech_package_monthly_fee", v)}
                />
              </div>
              <div className="field">
                <label>Furniture Package ($/bed/mo)</label>
                <NumberInput
                  value={form.furniture_package_monthly_fee}
                  onChange={(v) => set("furniture_package_monthly_fee", v)}
                />
              </div>
            </div>
            <div style={{ marginTop: "12px", textAlign: "right" }}>
              <button
                type="button"
                className="sync-action-btn"
                onClick={calculateStudentHousingAncillary}
              >
                Apply Package Fees to Other Income
              </button>
            </div>
          </>
        )}

        {form.sub_asset_class === "urban_midrise" && (
          <>
            <p className="housing-helper-note">
              Urban Mid-Rise properties feature structured subterranean parking garages, premium stall rents, and ground-floor commercial/retail spaces.
            </p>
            <div className="field-grid">
              <div className="field">
                <label>Structured Garage Stalls</label>
                <NumberInput
                  value={form.garage_parking_stalls}
                  onChange={(v) => set("garage_parking_stalls", v)}
                />
              </div>
              <div className="field">
                <label>Monthly Garage Rate ($/stall)</label>
                <NumberInput
                  value={form.garage_monthly_rate}
                  onChange={(v) => set("garage_monthly_rate", v)}
                />
              </div>
              <div className="field">
                <label>Ground-Floor Retail Sq Ft</label>
                <NumberInput
                  value={form.commercial_retail_sqft}
                  onChange={(v) => set("commercial_retail_sqft", v)}
                />
              </div>
              <div className="field">
                <label>Retail Rent ($/sqft NNN annual)</label>
                <NumberInput
                  value={form.commercial_rent_sqft_annual}
                  onChange={(v) => set("commercial_rent_sqft_annual", v)}
                />
              </div>
            </div>
            <div style={{ marginTop: "12px", textAlign: "right" }}>
              <button
                type="button"
                className="sync-action-btn"
                onClick={calculateUrbanMidRiseAncillary}
              >
                Apply Garage &amp; Retail to Other Income
              </button>
            </div>
          </>
        )}
      </div>

      {/* Unit Mix Matrix */}
      <div className="unit-mix-wrapper">
        <div className="unit-mix-header">
          <h4>🏢 Unit Mix Matrix (Studio, 1, 2, 3, 4+ Beds)</h4>
          <button
            type="button"
            className="import-btn"
            style={{ fontSize: "11px", padding: "4px 8px" }}
            onClick={() => setShowUnitMix(!showUnitMix)}
          >
            {showUnitMix ? "Hide Table" : "Show Table"}
          </button>
        </div>

        {showUnitMix && (
          <>
            <table className="unit-mix-table">
              <thead>
                <tr>
                  <th>Unit Type</th>
                  <th style={{ width: "90px" }}>Units</th>
                  <th style={{ width: "90px" }}>Beds/Unit</th>
                  <th style={{ width: "100px" }}>Avg Sq Ft</th>
                  <th style={{ width: "120px" }}>Monthly Rent ($)</th>
                  <th style={{ width: "120px" }}>Monthly GPR ($)</th>
                </tr>
              </thead>
              <tbody>
                {unitMix.map((row) => {
                  const uCount = Number(row.units) || 0;
                  const uRent = Number(row.rent) || 0;
                  const rowGpr = uCount * uRent;
                  return (
                    <tr key={row.id}>
                      <td style={{ fontWeight: 600 }}>{row.name}</td>
                      <td>
                        <NumberInput
                          value={row.units}
                          onChange={(v) => updateUnitMixRow(row.id, "units", v)}
                        />
                      </td>
                      <td>
                        <input
                          type="number"
                          min="1"
                          value={row.bedsPerUnit}
                          onChange={(e) => updateUnitMixRow(row.id, "bedsPerUnit", e.target.value)}
                        />
                      </td>
                      <td>
                        <NumberInput
                          value={row.avgSqFt}
                          onChange={(v) => updateUnitMixRow(row.id, "avgSqFt", v)}
                        />
                      </td>
                      <td>
                        <NumberInput
                          value={row.rent}
                          onChange={(v) => updateUnitMixRow(row.id, "rent", v)}
                        />
                      </td>
                      <td style={{ fontWeight: 600, color: "#1e293b" }}>
                        ${rowGpr.toLocaleString()}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>

            <div className="unit-mix-summary-bar">
              <div className="unit-mix-summary-item">
                <span className="label">Total Units:</span>
                <span className="val">{totalMixUnits}</span>
              </div>
              <div className="unit-mix-summary-item">
                <span className="label">Total Beds:</span>
                <span className="val">{totalMixBeds}</span>
              </div>
              <div className="unit-mix-summary-item">
                <span className="label">Monthly GPR:</span>
                <span className="val">${totalMonthlyGpr.toLocaleString()}</span>
              </div>
              <div className="unit-mix-summary-item">
                <span className="label">Avg Rent/Unit:</span>
                <span className="val">${Math.round(weightedAvgRentPerUnit).toLocaleString()}</span>
              </div>
              <div className="unit-mix-summary-item">
                <span className="label">Avg Rent/SqFt:</span>
                <span className="val">${weightedAvgRentPerSqFt.toFixed(2)}/sf</span>
              </div>
              <div style={{ marginLeft: "auto" }}>
                <button
                  type="button"
                  className="sync-action-btn"
                  onClick={syncUnitMixToDeal}
                >
                  Apply Unit Mix to Deal
                </button>
              </div>
            </div>
          </>
        )}
      </div>

      {/* Leasing Mode & Roll-Up GPR */}
      <h3>Leasing &amp; GPR</h3>
      <div className="leasing-toggle">
        <button
          type="button"
          className={isPerUnit ? "active" : ""}
          onClick={() => set("leasing_mode", "per_unit")}
        >
          Per unit
        </button>
        <button
          type="button"
          className={!isPerUnit ? "active" : ""}
          onClick={() => set("leasing_mode", "per_bed")}
        >
          Per bed
        </button>
      </div>
      <div className="field-grid">
        {isPerUnit ? (
          <>
            <div className="field">
              <label htmlFor="unit_count">Unit count</label>
              <NumberInput
                id="unit_count"
                value={form.unit_count}
                onChange={(v) => set("unit_count", v)}
                aria-invalid={!!fieldErrors.unit_count}
              />
              {fieldError("unit_count")}
            </div>
            <div className="field">
              <label htmlFor="monthly_rent_per_unit">Monthly rent / unit ($)</label>
              <NumberInput
                id="monthly_rent_per_unit"
                value={form.monthly_rent_per_unit}
                onChange={(v) => set("monthly_rent_per_unit", v)}
                aria-invalid={!!fieldErrors.monthly_rent_per_unit}
              />
              {fieldError("monthly_rent_per_unit")}
            </div>
          </>
        ) : (
          <>
            <div className="field">
              <label htmlFor="bed_count">Bed count</label>
              <NumberInput
                id="bed_count"
                value={form.bed_count}
                onChange={(v) => set("bed_count", v)}
                aria-invalid={!!fieldErrors.bed_count}
              />
              {fieldError("bed_count")}
            </div>
            <div className="field">
              <label htmlFor="monthly_rent_per_bed">Monthly rent / bed ($)</label>
              <NumberInput
                id="monthly_rent_per_bed"
                value={form.monthly_rent_per_bed}
                onChange={(v) => set("monthly_rent_per_bed", v)}
                aria-invalid={!!fieldErrors.monthly_rent_per_bed}
              />
              {fieldError("monthly_rent_per_bed")}
            </div>
          </>
        )}
        <div className="field">
          <label htmlFor="vacancy_rate_pct">Vacancy rate (%)</label>
          <input
            id="vacancy_rate_pct"
            type="number"
            min="0"
            step="0.1"
            value={form.vacancy_rate_pct}
            onChange={(e) => set("vacancy_rate_pct", e.target.value)}
            aria-invalid={!!fieldErrors.vacancy_rate_pct}
          />
          {fieldError("vacancy_rate_pct")}
        </div>
        <div className="field">
          <label htmlFor="other_income_annual">Other income, annual ($)</label>
          <NumberInput
            id="other_income_annual"
            value={form.other_income_annual}
            onChange={(v) => set("other_income_annual", v)}
            aria-invalid={!!fieldErrors.other_income_annual}
          />
          {fieldError("other_income_annual")}
        </div>
        <div className="field">
          <label htmlFor="other_income_growth_rate_pct">Other income growth (%/yr)</label>
          <input
            id="other_income_growth_rate_pct"
            type="number"
            step="any"
            value={form.other_income_growth_rate_pct}
            onChange={(e) => set("other_income_growth_rate_pct", e.target.value)}
          />
        </div>
        <div className="field">
          <label htmlFor="credit_loss_rate_pct">Bad debt &amp; concessions (% of GPR)</label>
          <input
            id="credit_loss_rate_pct"
            type="number"
            min="0"
            step="any"
            value={form.credit_loss_rate_pct}
            onChange={(e) => set("credit_loss_rate_pct", e.target.value)}
          />
        </div>
        <div className="field">
          <label htmlFor="management_fee_rate_pct">Management fee (% of EGI)</label>
          <input
            id="management_fee_rate_pct"
            type="number"
            min="0"
            step="any"
            value={form.management_fee_rate_pct}
            onChange={(e) => set("management_fee_rate_pct", e.target.value)}
          />
        </div>
        <div className="field">
          <label htmlFor="replacement_reserve_per_unit_or_bed">
            Replacement reserve / {isPerUnit ? "unit" : "bed"} / yr ($, below NOI)
          </label>
          <input
            id="replacement_reserve_per_unit_or_bed"
            type="number"
            min="0"
            step="any"
            value={form.replacement_reserve_per_unit_or_bed}
            onChange={(e) => set("replacement_reserve_per_unit_or_bed", e.target.value)}
          />
        </div>
      </div>

      <h3>Operating expenses &amp; turnover</h3>
      <div className="field-grid">
        <div className="field">
          <label htmlFor="opex_annual">OpEx, annual ($)</label>
          <NumberInput
            id="opex_annual"
            value={form.opex_annual}
            onChange={(v) => set("opex_annual", v)}
            aria-invalid={!!fieldErrors.opex_annual}
          />
          {fieldError("opex_annual")}
        </div>
        <div className="field">
          <label htmlFor="expense_growth_rate_pct">Expense growth rate (%/yr)</label>
          <input
            id="expense_growth_rate_pct"
            type="number"
            min="0"
            step="0.1"
            value={form.expense_growth_rate_pct}
            onChange={(e) => set("expense_growth_rate_pct", e.target.value)}
            aria-invalid={!!fieldErrors.expense_growth_rate_pct}
          />
          {fieldError("expense_growth_rate_pct")}
        </div>
        <div className="field">
          <label htmlFor="rent_growth_rate_pct">Rent growth rate (%/yr)</label>
          <input
            id="rent_growth_rate_pct"
            type="number"
            step="0.1"
            value={form.rent_growth_rate_pct}
            onChange={(e) => set("rent_growth_rate_pct", e.target.value)}
            aria-invalid={!!fieldErrors.rent_growth_rate_pct}
          />
          {fieldError("rent_growth_rate_pct")}
        </div>
        <div className="field">
          <label htmlFor="lease_expiration_month">Lease expiration month (1–12, display only)</label>
          <input
            id="lease_expiration_month"
            type="number"
            min="1"
            max="12"
            value={form.lease_expiration_month}
            onChange={(e) => set("lease_expiration_month", e.target.value)}
            aria-invalid={!!fieldErrors.lease_expiration_month}
          />
          {fieldError("lease_expiration_month")}
        </div>
        <div className="field">
          <label htmlFor="turnover_cost_per_unit_or_bed">
            Turnover cost / {isPerUnit ? "unit" : "bed"} ($)
          </label>
          <NumberInput
            id="turnover_cost_per_unit_or_bed"
            value={form.turnover_cost_per_unit_or_bed}
            onChange={(v) => set("turnover_cost_per_unit_or_bed", v)}
            aria-invalid={!!fieldErrors.turnover_cost_per_unit_or_bed}
          />
          {fieldError("turnover_cost_per_unit_or_bed")}
        </div>
        <div className="field">
          <label htmlFor="annual_turnover_rate_pct">Annual turnover rate (%)</label>
          <input
            id="annual_turnover_rate_pct"
            type="number"
            min="0"
            step="0.1"
            value={form.annual_turnover_rate_pct}
            onChange={(e) => set("annual_turnover_rate_pct", e.target.value)}
            aria-invalid={!!fieldErrors.annual_turnover_rate_pct}
          />
          {fieldError("annual_turnover_rate_pct")}
        </div>
      </div>

      {/* Acquisition & Flexible Financing */}
      <h3>Acquisition &amp; financing</h3>
      <div className="field-grid">
        <div className="field">
          <label htmlFor="purchase_price">Purchase price ($)</label>
          <NumberInput
            id="purchase_price"
            value={form.purchase_price}
            onChange={(v) => set("purchase_price", v)}
            aria-invalid={!!fieldErrors.purchase_price}
          />
          {fieldError("purchase_price")}
        </div>
        <div className="field">
          <label htmlFor="closing_costs">Closing costs ($)</label>
          <NumberInput
            id="closing_costs"
            value={form.closing_costs}
            onChange={(v) => set("closing_costs", v)}
            aria-invalid={!!fieldErrors.closing_costs}
          />
          {fieldError("closing_costs")}
        </div>
      </div>

      <CapitalStackEditor
        layers={layers}
        onChange={updateLayers}
        totalCost={totalCost}
        errors={stackErrors}
        defaultTreasuryPct={treasuryPct}
      />

      {/* Hold & Exit */}
      <h3>Hold &amp; exit</h3>
      <div className="field-grid">
        <div className="field">
          <label htmlFor="hold_period_years">Hold period (years)</label>
          <input
            id="hold_period_years"
            type="number"
            min="0"
            value={form.hold_period_years}
            onChange={(e) => set("hold_period_years", e.target.value)}
            aria-invalid={!!fieldErrors.hold_period_years}
          />
          {fieldError("hold_period_years")}
        </div>
        <div className="field">
          <label htmlFor="exit_cap_rate_pct">Exit cap rate (%)</label>
          <input
            id="exit_cap_rate_pct"
            type="number"
            min="0"
            step="0.01"
            value={form.exit_cap_rate_pct}
            onChange={(e) => set("exit_cap_rate_pct", e.target.value)}
            aria-invalid={!!fieldErrors.exit_cap_rate_pct}
          />
          {fieldError("exit_cap_rate_pct")}
        </div>
        <div className="field">
          <label htmlFor="selling_costs_rate_pct">Selling costs rate (%)</label>
          <input
            id="selling_costs_rate_pct"
            type="number"
            min="0"
            step="0.1"
            value={form.selling_costs_rate_pct}
            onChange={(e) => set("selling_costs_rate_pct", e.target.value)}
            aria-invalid={!!fieldErrors.selling_costs_rate_pct}
          />
          {fieldError("selling_costs_rate_pct")}
        </div>
      </div>

      {Object.keys(fieldErrors).length > 0 && (
        <p className="field error">Please fix the highlighted fields above.</p>
      )}

      {submitError && (
        <div className="status-banner error" role="alert">
          {submitError}
        </div>
      )}

      <div className="form-actions">
        <button type="submit" className="primary" disabled={submitting}>
          {submitting ? "Saving…" : initial ? "Save changes" : "Add deal"}
        </button>
        <button type="button" className="secondary" onClick={onCancel} disabled={submitting}>
          Cancel
        </button>
      </div>
    </form>
  );
}
