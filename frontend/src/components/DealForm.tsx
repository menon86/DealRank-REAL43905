import { useRef, useState } from "react";
import { fractionToPercentInput, percentInputToFraction } from "../lib/format";
import { SUB_ASSET_CLASS_LABELS } from "../lib/types";
import type { DealCreate, DealOut, LeasingMode, SubAssetClass } from "../lib/types";

export type LoanStructure = "fixed_amortizing" | "interest_only" | "floating_rate" | "balloon_mini_perm";

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
  opex_annual: string;
  expense_growth_rate_pct: string;
  rent_growth_rate_pct: string;
  lease_expiration_month: string;
  turnover_cost_per_unit_or_bed: string;
  annual_turnover_rate_pct: string;
  purchase_price: string;
  closing_costs: string;
  loan_amount: string;
  interest_rate_pct: string;
  amortization_years: string;
  hold_period_years: string;
  exit_cap_rate_pct: string;
  selling_costs_rate_pct: string;

  // Financing flexibility extensions
  loan_structure: LoanStructure;
  io_period_years: string;
  sofr_base_rate_pct: string;
  spread_bps: string;
  loan_term_years: string;

  // Suburban Garden specific
  surface_parking_stalls: string;
  covered_parking_stalls: string;
  parking_monthly_rate: string;
  parking_occupancy_pct: string;
  storage_units: string;
  storage_monthly_fee: string;
  pet_monthly_fee: string;
  pet_penetration_pct: string;
  rubs_recovery_pct: string;

  // Student Housing specific
  tech_package_monthly_fee: string;
  furniture_package_monthly_fee: string;
  parental_guaranty_rate_pct: string;

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
  opex_annual: "650000",
  expense_growth_rate_pct: "3",
  rent_growth_rate_pct: "3",
  lease_expiration_month: "6",
  turnover_cost_per_unit_or_bed: "750",
  annual_turnover_rate_pct: "50",
  purchase_price: "22000000",
  closing_costs: "440000",
  loan_amount: "14300000",
  interest_rate_pct: "6.25",
  amortization_years: "30",
  hold_period_years: "10",
  exit_cap_rate_pct: "5.75",
  selling_costs_rate_pct: "2",

  loan_structure: "fixed_amortizing",
  io_period_years: "2",
  sofr_base_rate_pct: "4.8",
  spread_bps: "175",
  loan_term_years: "10",

  surface_parking_stalls: "180",
  covered_parking_stalls: "40",
  parking_monthly_rate: "50",
  parking_occupancy_pct: "85",
  storage_units: "30",
  storage_monthly_fee: "65",
  pet_monthly_fee: "35",
  pet_penetration_pct: "35",
  rubs_recovery_pct: "75",

  tech_package_monthly_fee: "55",
  furniture_package_monthly_fee: "40",
  parental_guaranty_rate_pct: "90",

  garage_parking_stalls: "110",
  garage_monthly_rate: "150",
  commercial_retail_sqft: "4500",
  commercial_rent_sqft_annual: "32",
};

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
    opex_annual: deal.opex_annual.toString(),
    expense_growth_rate_pct: fractionToPercentInput(deal.expense_growth_rate),
    rent_growth_rate_pct: fractionToPercentInput(deal.rent_growth_rate),
    lease_expiration_month: deal.lease_expiration_month.toString(),
    turnover_cost_per_unit_or_bed: deal.turnover_cost_per_unit_or_bed.toString(),
    annual_turnover_rate_pct: fractionToPercentInput(deal.annual_turnover_rate),
    purchase_price: deal.purchase_price.toString(),
    closing_costs: deal.closing_costs.toString(),
    loan_amount: deal.loan_amount.toString(),
    interest_rate_pct: fractionToPercentInput(deal.interest_rate),
    amortization_years: deal.amortization_years.toString(),
    hold_period_years: deal.hold_period_years.toString(),
    exit_cap_rate_pct: fractionToPercentInput(deal.exit_cap_rate),
    selling_costs_rate_pct: fractionToPercentInput(deal.selling_costs_rate),
  };
}

type FieldErrors = Partial<Record<keyof FormState, string>>;

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

  if (parseNumber(form.expense_growth_rate_pct) === null) {
    errors.expense_growth_rate_pct = "Enter a percentage.";
  }
  if (parseNumber(form.rent_growth_rate_pct) === null) {
    errors.rent_growth_rate_pct = "Enter a percentage.";
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

  const loanAmount = parseNumber(form.loan_amount);
  if (loanAmount === null || loanAmount < 0) errors.loan_amount = "Enter a non-negative amount.";

  const interestRate = parseNumber(form.interest_rate_pct);
  if (interestRate === null || interestRate < 0) {
    errors.interest_rate_pct = "Enter a non-negative percentage.";
  }

  const amortYears = parseNumber(form.amortization_years);
  if (amortYears === null || amortYears <= 0 || !Number.isInteger(amortYears)) {
    errors.amortization_years = "Enter a positive whole number of years.";
  }

  const holdYears = parseNumber(form.hold_period_years);
  if (holdYears === null || holdYears <= 0 || !Number.isInteger(holdYears)) {
    errors.hold_period_years = "Enter a positive whole number of years.";
  }

  const exitCap = parseNumber(form.exit_cap_rate_pct);
  if (exitCap === null || exitCap <= 0) errors.exit_cap_rate_pct = "Enter a positive percentage.";

  const sellingCosts = parseNumber(form.selling_costs_rate_pct);
  if (sellingCosts === null || sellingCosts < 0) {
    errors.selling_costs_rate_pct = "Enter a non-negative percentage.";
  }

  return errors;
}

interface DealFormProps {
  initial: DealOut | null;
  onSave: (input: DealCreate) => void;
  onCancel: () => void;
}

export function DealForm({ initial, onSave, onCancel }: DealFormProps) {
  const [form, setForm] = useState<FormState>(initial ? dealToFormState(initial) : DEFAULTS);
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});
  const [unitMix, setUnitMix] = useState<UnitMixTier[]>(DEFAULT_UNIT_MIX);
  const [showUnitMix, setShowUnitMix] = useState<boolean>(true);
  const [importNotice, setImportNotice] = useState<{ message: string; type: "success" | "error" } | null>(null);

  const underwritingFileInputRef = useRef<HTMLInputElement | null>(null);
  const financingFileInputRef = useRef<HTMLInputElement | null>(null);

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
      set("monthly_rent_per_unit", Math.round(weightedAvgRentPerUnit).toString());
    } else {
      set("bed_count", totalMixBeds.toString());
      const avgRentPerBed = totalMixBeds > 0 ? totalMonthlyGpr / totalMixBeds : 0;
      set("monthly_rent_per_bed", Math.round(avgRentPerBed).toString());
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

  // --- Financing Computations ---
  const loanPrincipal = Number(form.loan_amount) || 0;
  const purchasePriceVal = Number(form.purchase_price) || 0;
  const closingCostsVal = Number(form.closing_costs) || 0;
  const interestRateDec = (Number(form.interest_rate_pct) || 0) / 100;
  const amortYearsNum = Number(form.amortization_years) || 30;

  const monthlyRate = interestRateDec / 12;
  const nMonths = amortYearsNum * 12;

  // Monthly amortizing payment
  const monthlyAmortPayment =
    loanPrincipal > 0 && monthlyRate > 0 && nMonths > 0
      ? (loanPrincipal * (monthlyRate * Math.pow(1 + monthlyRate, nMonths))) /
        (Math.pow(1 + monthlyRate, nMonths) - 1)
      : 0;

  // Monthly IO payment
  const monthlyIoPayment = loanPrincipal > 0 ? loanPrincipal * monthlyRate : 0;

  const isIO = form.loan_structure === "interest_only";
  const displayedMonthlyPayment = isIO ? monthlyIoPayment : monthlyAmortPayment;
  const displayedAnnualDebtService = displayedMonthlyPayment * 12;
  const ltvPct = purchasePriceVal > 0 ? (loanPrincipal / purchasePriceVal) * 100 : 0;
  const requiredEquity = Math.max(0, purchasePriceVal + closingCostsVal - loanPrincipal);

  // Floating rate sync
  function updateFloatingRate(sofr: string, spread: string) {
    const sofrVal = Number(sofr) || 0;
    const spreadVal = Number(spread) || 0;
    const totalRate = sofrVal + spreadVal / 100;
    set("sofr_base_rate_pct", sofr);
    set("spread_bps", spread);
    set("interest_rate_pct", totalRate.toFixed(2));
  }

  // --- Excel / CSV Template Downloads ---
  function downloadCsv(filename: string, content: string) {
    const blob = new Blob([content], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.setAttribute("download", filename);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  }

  function handleDownloadUnderwritingTemplate() {
    const csvContent = [
      "Property_Details,Value",
      "deal_name,Westwood Ridge Multifamily",
      "sub_asset_class,suburban_garden",
      "leasing_mode,per_unit",
      "purchase_price,24500000",
      "closing_costs,490000",
      "vacancy_rate_pct,5.0",
      "opex_annual,720000",
      "expense_growth_rate_pct,3.0",
      "rent_growth_rate_pct,3.0",
      "lease_expiration_month,6",
      "turnover_cost,800",
      "turnover_rate_pct,55.0",
      "hold_period_years,10",
      "exit_cap_rate_pct,5.75",
      "selling_costs_rate_pct,2.0",
      "",
      "Unit_Mix,Units,BedsPerUnit,AvgSqFt,MonthlyRent",
      "Studio,20,1,540,1200",
      "1bed,60,1,720,1450",
      "2bed,80,2,980,1800",
      "3bed,20,3,1240,2200",
      "4bed_plus,0,4,1500,0",
      "",
      "Ancillary_Inputs,Value",
      "surface_parking_stalls,180",
      "covered_parking_stalls,40",
      "parking_monthly_rate,50",
      "storage_units,30",
      "storage_monthly_fee,60",
      "pet_monthly_fee,35",
      "pet_penetration_pct,30",
    ].join("\n");
    downloadCsv("dealrank_underwriting_template.csv", csvContent);
  }

  function handleDownloadFinancingTemplate() {
    const csvContent = [
      "Financing_Parameter,Value",
      "loan_structure,interest_only",
      "loan_amount,15925000",
      "interest_rate_pct,6.25",
      "io_period_years,2",
      "amortization_years,30",
      "loan_term_years,10",
      "sofr_base_rate_pct,4.8",
      "spread_bps,175",
      "mezzanine_loan_amount,0",
      "mezzanine_interest_rate_pct,0",
    ].join("\n");
    downloadCsv("dealrank_financing_template.csv", csvContent);
  }

  // --- Excel / CSV Parsers ---
  function parseCsvText(text: string) {
    const lines = text.split(/\r?\n/).map((l) => l.trim()).filter((l) => l.length > 0);
    const data: Record<string, string> = {};
    const mixRows: UnitMixTier[] = [];

    let inUnitMix = false;
    for (const line of lines) {
      const parts = line.split(",").map((p) => p.trim().replace(/^"|"$/g, ""));
      if (parts[0] === "Unit_Mix") {
        inUnitMix = true;
        continue;
      }
      if (inUnitMix) {
        if (parts[0] === "Ancillary_Inputs" || parts[0] === "" || parts.length < 5) {
          inUnitMix = false;
        } else {
          const typeLower = parts[0].toLowerCase();
          const matchedId = DEFAULT_UNIT_MIX.find((t) => t.id === typeLower || t.name.toLowerCase().includes(typeLower))?.id ?? typeLower;
          mixRows.push({
            id: matchedId,
            name: parts[0],
            units: parts[1] || "0",
            bedsPerUnit: parts[2] || "1",
            avgSqFt: parts[3] || "0",
            rent: parts[4] || "0",
          });
          continue;
        }
      }

      if (parts.length >= 2) {
        data[parts[0].toLowerCase()] = parts[1];
      }
    }

    return { data, mixRows };
  }

  function handleUnderwritingFile(file: File) {
    const reader = new FileReader();
    reader.onload = (e) => {
      try {
        const text = e.target?.result as string;
        const { data, mixRows } = parseCsvText(text);

        if (data.deal_name || data.name) set("name", data.deal_name || data.name);
        if (data.sub_asset_class && ["student_housing", "suburban_garden", "urban_midrise"].includes(data.sub_asset_class)) {
          set("sub_asset_class", data.sub_asset_class as SubAssetClass);
        }
        if (data.purchase_price) set("purchase_price", data.purchase_price);
        if (data.closing_costs) set("closing_costs", data.closing_costs);
        if (data.vacancy_rate_pct) set("vacancy_rate_pct", data.vacancy_rate_pct);
        if (data.opex_annual) set("opex_annual", data.opex_annual);
        if (data.expense_growth_rate_pct) set("expense_growth_rate_pct", data.expense_growth_rate_pct);
        if (data.rent_growth_rate_pct) set("rent_growth_rate_pct", data.rent_growth_rate_pct);
        if (data.lease_expiration_month) set("lease_expiration_month", data.lease_expiration_month);
        if (data.turnover_cost) set("turnover_cost_per_unit_or_bed", data.turnover_cost);
        if (data.turnover_rate_pct) set("annual_turnover_rate_pct", data.turnover_rate_pct);
        if (data.exit_cap_rate_pct) set("exit_cap_rate_pct", data.exit_cap_rate_pct);
        if (data.selling_costs_rate_pct) set("selling_costs_rate_pct", data.selling_costs_rate_pct);

        if (mixRows.length > 0) {
          setUnitMix(mixRows);
          const unitsSum = mixRows.reduce((acc, r) => acc + (Number(r.units) || 0), 0);
          const gprSum = mixRows.reduce((acc, r) => acc + (Number(r.units) || 0) * (Number(r.rent) || 0), 0);
          const avgRent = unitsSum > 0 ? Math.round(gprSum / unitsSum) : 0;
          set("unit_count", unitsSum.toString());
          set("monthly_rent_per_unit", avgRent.toString());
        }

        setImportNotice({
          message: `Successfully imported property & underwriting details from "${file.name}"!`,
          type: "success",
        });
      } catch {
        setImportNotice({
          message: `Failed to parse "${file.name}". Please ensure it matches the template format.`,
          type: "error",
        });
      }
    };
    reader.readAsText(file);
  }

  function handleFinancingFile(file: File) {
    const reader = new FileReader();
    reader.onload = (e) => {
      try {
        const text = e.target?.result as string;
        const { data } = parseCsvText(text);

        if (data.loan_amount) set("loan_amount", data.loan_amount);
        if (data.interest_rate_pct) set("interest_rate_pct", data.interest_rate_pct);
        if (data.amortization_years) set("amortization_years", data.amortization_years);
        if (data.io_period_years) set("io_period_years", data.io_period_years);
        if (data.loan_structure && ["fixed_amortizing", "interest_only", "floating_rate", "balloon_mini_perm"].includes(data.loan_structure)) {
          set("loan_structure", data.loan_structure as LoanStructure);
        }
        if (data.sofr_base_rate_pct) set("sofr_base_rate_pct", data.sofr_base_rate_pct);
        if (data.spread_bps) set("spread_bps", data.spread_bps);
        if (data.loan_term_years) set("loan_term_years", data.loan_term_years);

        setImportNotice({
          message: `Successfully imported financing details from "${file.name}"!`,
          type: "success",
        });
      } catch {
        setImportNotice({
          message: `Failed to parse financing file "${file.name}".`,
          type: "error",
        });
      }
    };
    reader.readAsText(file);
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();

    const errors = validate(form);
    setFieldErrors(errors);
    if (Object.keys(errors).length > 0) return;

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
      opex_annual: Number(form.opex_annual) || 0,
      expense_growth_rate: percentInputToFraction(form.expense_growth_rate_pct),
      rent_growth_rate: percentInputToFraction(form.rent_growth_rate_pct),
      lease_expiration_month: Number(form.lease_expiration_month) || 1,
      turnover_cost_per_unit_or_bed: Number(form.turnover_cost_per_unit_or_bed) || 0,
      annual_turnover_rate: percentInputToFraction(form.annual_turnover_rate_pct),
      purchase_price: Number(form.purchase_price) || 0,
      closing_costs: Number(form.closing_costs) || 0,
      loan_amount: Number(form.loan_amount) || 0,
      interest_rate: percentInputToFraction(form.interest_rate_pct),
      amortization_years: Number(form.amortization_years) || 0,
      hold_period_years: Number(form.hold_period_years) || 0,
      exit_cap_rate: percentInputToFraction(form.exit_cap_rate_pct),
      selling_costs_rate: percentInputToFraction(form.selling_costs_rate_pct),
    };

    onSave(input);
  }

  const isPerUnit = form.leasing_mode === "per_unit";

  return (
    <form className="card" onSubmit={handleSubmit}>
      <h2>{initial ? "Edit deal" : "New deal"}</h2>

      {/* Excel & CSV Ingestion Toolbar */}
      <div className="import-toolbar">
        <div className="import-toolbar-title">
          <span>📊</span>
          <span>Excel / CSV Ingestion</span>
        </div>
        <div className="import-actions">
          <input
            type="file"
            ref={underwritingFileInputRef}
            style={{ display: "none" }}
            accept=".csv,.tsv,.xlsx"
            onChange={(e) => {
              if (e.target.files?.[0]) handleUnderwritingFile(e.target.files[0]);
            }}
          />
          <button
            type="button"
            className="import-btn"
            onClick={() => underwritingFileInputRef.current?.click()}
          >
            📥 Import Underwriting
          </button>

          <input
            type="file"
            ref={financingFileInputRef}
            style={{ display: "none" }}
            accept=".csv,.tsv,.xlsx"
            onChange={(e) => {
              if (e.target.files?.[0]) handleFinancingFile(e.target.files[0]);
            }}
          />
          <button
            type="button"
            className="import-btn"
            onClick={() => financingFileInputRef.current?.click()}
          >
            📥 Import Financing
          </button>

          <button
            type="button"
            className="import-btn"
            onClick={handleDownloadUnderwritingTemplate}
          >
            📄 Template (Underwriting)
          </button>
          <button
            type="button"
            className="import-btn"
            onClick={handleDownloadFinancingTemplate}
          >
            📄 Template (Financing)
          </button>
        </div>
      </div>

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
                <input
                  type="number"
                  value={form.surface_parking_stalls}
                  onChange={(e) => set("surface_parking_stalls", e.target.value)}
                />
              </div>
              <div className="field">
                <label>Covered/Garage Stalls</label>
                <input
                  type="number"
                  value={form.covered_parking_stalls}
                  onChange={(e) => set("covered_parking_stalls", e.target.value)}
                />
              </div>
              <div className="field">
                <label>Monthly Parking Fee ($/stall)</label>
                <input
                  type="number"
                  value={form.parking_monthly_rate}
                  onChange={(e) => set("parking_monthly_rate", e.target.value)}
                />
              </div>
              <div className="field">
                <label>Parking Occupancy (%)</label>
                <input
                  type="number"
                  value={form.parking_occupancy_pct}
                  onChange={(e) => set("parking_occupancy_pct", e.target.value)}
                />
              </div>
              <div className="field">
                <label>Storage Units</label>
                <input
                  type="number"
                  value={form.storage_units}
                  onChange={(e) => set("storage_units", e.target.value)}
                />
              </div>
              <div className="field">
                <label>Storage Fee ($/mo)</label>
                <input
                  type="number"
                  value={form.storage_monthly_fee}
                  onChange={(e) => set("storage_monthly_fee", e.target.value)}
                />
              </div>
              <div className="field">
                <label>Monthly Pet Fee ($/unit)</label>
                <input
                  type="number"
                  value={form.pet_monthly_fee}
                  onChange={(e) => set("pet_monthly_fee", e.target.value)}
                />
              </div>
              <div className="field">
                <label>Pet Penetration Rate (%)</label>
                <input
                  type="number"
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
                <input
                  type="number"
                  value={form.tech_package_monthly_fee}
                  onChange={(e) => set("tech_package_monthly_fee", e.target.value)}
                />
              </div>
              <div className="field">
                <label>Furniture Package ($/bed/mo)</label>
                <input
                  type="number"
                  value={form.furniture_package_monthly_fee}
                  onChange={(e) => set("furniture_package_monthly_fee", e.target.value)}
                />
              </div>
              <div className="field">
                <label>Parental Guaranty Rate (%)</label>
                <input
                  type="number"
                  value={form.parental_guaranty_rate_pct}
                  onChange={(e) => set("parental_guaranty_rate_pct", e.target.value)}
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
                <input
                  type="number"
                  value={form.garage_parking_stalls}
                  onChange={(e) => set("garage_parking_stalls", e.target.value)}
                />
              </div>
              <div className="field">
                <label>Monthly Garage Rate ($/stall)</label>
                <input
                  type="number"
                  value={form.garage_monthly_rate}
                  onChange={(e) => set("garage_monthly_rate", e.target.value)}
                />
              </div>
              <div className="field">
                <label>Ground-Floor Retail Sq Ft</label>
                <input
                  type="number"
                  value={form.commercial_retail_sqft}
                  onChange={(e) => set("commercial_retail_sqft", e.target.value)}
                />
              </div>
              <div className="field">
                <label>Retail Rent ($/sqft NNN annual)</label>
                <input
                  type="number"
                  value={form.commercial_rent_sqft_annual}
                  onChange={(e) => set("commercial_rent_sqft_annual", e.target.value)}
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
                        <input
                          type="number"
                          value={row.units}
                          onChange={(e) => updateUnitMixRow(row.id, "units", e.target.value)}
                        />
                      </td>
                      <td>
                        <input
                          type="number"
                          value={row.bedsPerUnit}
                          onChange={(e) => updateUnitMixRow(row.id, "bedsPerUnit", e.target.value)}
                        />
                      </td>
                      <td>
                        <input
                          type="number"
                          value={row.avgSqFt}
                          onChange={(e) => updateUnitMixRow(row.id, "avgSqFt", e.target.value)}
                        />
                      </td>
                      <td>
                        <input
                          type="number"
                          value={row.rent}
                          onChange={(e) => updateUnitMixRow(row.id, "rent", e.target.value)}
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
              <input
                id="unit_count"
                type="number"
                value={form.unit_count}
                onChange={(e) => set("unit_count", e.target.value)}
                aria-invalid={!!fieldErrors.unit_count}
              />
              {fieldError("unit_count")}
            </div>
            <div className="field">
              <label htmlFor="monthly_rent_per_unit">Monthly rent / unit ($)</label>
              <input
                id="monthly_rent_per_unit"
                type="number"
                value={form.monthly_rent_per_unit}
                onChange={(e) => set("monthly_rent_per_unit", e.target.value)}
                aria-invalid={!!fieldErrors.monthly_rent_per_unit}
              />
              {fieldError("monthly_rent_per_unit")}
            </div>
          </>
        ) : (
          <>
            <div className="field">
              <label htmlFor="bed_count">Bed count</label>
              <input
                id="bed_count"
                type="number"
                value={form.bed_count}
                onChange={(e) => set("bed_count", e.target.value)}
                aria-invalid={!!fieldErrors.bed_count}
              />
              {fieldError("bed_count")}
            </div>
            <div className="field">
              <label htmlFor="monthly_rent_per_bed">Monthly rent / bed ($)</label>
              <input
                id="monthly_rent_per_bed"
                type="number"
                value={form.monthly_rent_per_bed}
                onChange={(e) => set("monthly_rent_per_bed", e.target.value)}
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
            step="0.1"
            value={form.vacancy_rate_pct}
            onChange={(e) => set("vacancy_rate_pct", e.target.value)}
            aria-invalid={!!fieldErrors.vacancy_rate_pct}
          />
          {fieldError("vacancy_rate_pct")}
        </div>
        <div className="field">
          <label htmlFor="other_income_annual">Other income, annual ($)</label>
          <input
            id="other_income_annual"
            type="number"
            value={form.other_income_annual}
            onChange={(e) => set("other_income_annual", e.target.value)}
            aria-invalid={!!fieldErrors.other_income_annual}
          />
          {fieldError("other_income_annual")}
        </div>
      </div>

      <h3>Operating expenses &amp; turnover</h3>
      <div className="field-grid">
        <div className="field">
          <label htmlFor="opex_annual">OpEx, annual ($)</label>
          <input
            id="opex_annual"
            type="number"
            value={form.opex_annual}
            onChange={(e) => set("opex_annual", e.target.value)}
            aria-invalid={!!fieldErrors.opex_annual}
          />
          {fieldError("opex_annual")}
        </div>
        <div className="field">
          <label htmlFor="expense_growth_rate_pct">Expense growth rate (%/yr)</label>
          <input
            id="expense_growth_rate_pct"
            type="number"
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
          <label htmlFor="lease_expiration_month">Lease expiration month (1–12)</label>
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
          <input
            id="turnover_cost_per_unit_or_bed"
            type="number"
            value={form.turnover_cost_per_unit_or_bed}
            onChange={(e) => set("turnover_cost_per_unit_or_bed", e.target.value)}
            aria-invalid={!!fieldErrors.turnover_cost_per_unit_or_bed}
          />
          {fieldError("turnover_cost_per_unit_or_bed")}
        </div>
        <div className="field">
          <label htmlFor="annual_turnover_rate_pct">Annual turnover rate (%)</label>
          <input
            id="annual_turnover_rate_pct"
            type="number"
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
          <input
            id="purchase_price"
            type="number"
            value={form.purchase_price}
            onChange={(e) => set("purchase_price", e.target.value)}
            aria-invalid={!!fieldErrors.purchase_price}
          />
          {fieldError("purchase_price")}
        </div>
        <div className="field">
          <label htmlFor="closing_costs">Closing costs ($)</label>
          <input
            id="closing_costs"
            type="number"
            value={form.closing_costs}
            onChange={(e) => set("closing_costs", e.target.value)}
            aria-invalid={!!fieldErrors.closing_costs}
          />
          {fieldError("closing_costs")}
        </div>

        <div className="field">
          <label htmlFor="loan_structure">Loan structure</label>
          <select
            id="loan_structure"
            value={form.loan_structure}
            onChange={(e) => set("loan_structure", e.target.value as LoanStructure)}
          >
            <option value="fixed_amortizing">Fixed Rate Amortizing (30-Year)</option>
            <option value="interest_only">Interest-Only Period (1–5 Years I/O)</option>
            <option value="floating_rate">Floating Rate (SOFR + Spread)</option>
            <option value="balloon_mini_perm">Balloon / Mini-Perm Term</option>
          </select>
        </div>

        <div className="field">
          <label htmlFor="loan_amount">Loan amount ($)</label>
          <input
            id="loan_amount"
            type="number"
            value={form.loan_amount}
            onChange={(e) => set("loan_amount", e.target.value)}
            aria-invalid={!!fieldErrors.loan_amount}
          />
          {fieldError("loan_amount")}
        </div>

        {form.loan_structure === "interest_only" && (
          <div className="field">
            <label htmlFor="io_period_years">Interest-Only period (years)</label>
            <select
              id="io_period_years"
              value={form.io_period_years}
              onChange={(e) => set("io_period_years", e.target.value)}
            >
              <option value="1">1 Year I/O</option>
              <option value="2">2 Years I/O</option>
              <option value="3">3 Years I/O</option>
              <option value="4">4 Years I/O</option>
              <option value="5">5 Years I/O</option>
            </select>
          </div>
        )}

        {form.loan_structure === "floating_rate" && (
          <>
            <div className="field">
              <label>SOFR Base Rate (%)</label>
              <input
                type="number"
                step="0.01"
                value={form.sofr_base_rate_pct}
                onChange={(e) => updateFloatingRate(e.target.value, form.spread_bps)}
              />
            </div>
            <div className="field">
              <label>Lender Spread (bps)</label>
              <input
                type="number"
                value={form.spread_bps}
                onChange={(e) => updateFloatingRate(form.sofr_base_rate_pct, e.target.value)}
              />
            </div>
          </>
        )}

        <div className="field">
          <label htmlFor="interest_rate_pct">Interest rate (%)</label>
          <input
            id="interest_rate_pct"
            type="number"
            step="0.01"
            value={form.interest_rate_pct}
            onChange={(e) => set("interest_rate_pct", e.target.value)}
            aria-invalid={!!fieldErrors.interest_rate_pct}
          />
          {fieldError("interest_rate_pct")}
        </div>
        <div className="field">
          <label htmlFor="amortization_years">Amortization (years)</label>
          <input
            id="amortization_years"
            type="number"
            value={form.amortization_years}
            onChange={(e) => set("amortization_years", e.target.value)}
            aria-invalid={!!fieldErrors.amortization_years}
          />
          {fieldError("amortization_years")}
        </div>
      </div>

      {/* Live Debt Analytics Card */}
      <div className="financing-summary-card">
        <div className="financing-stat">
          <span className="stat-label">Estimated Monthly Payment</span>
          <span className="stat-value">
            ${Math.round(displayedMonthlyPayment).toLocaleString()}
            <small style={{ fontSize: "10px", fontWeight: "normal", color: "#15803d", marginLeft: "4px" }}>
              ({isIO ? `${form.io_period_years}yr I/O` : "Amortizing"})
            </small>
          </span>
        </div>
        <div className="financing-stat">
          <span className="stat-label">Annual Debt Service</span>
          <span className="stat-value">${Math.round(displayedAnnualDebtService).toLocaleString()}</span>
        </div>
        <div className="financing-stat">
          <span className="stat-label">Loan-to-Value (LTV)</span>
          <span className="stat-value">{ltvPct.toFixed(1)}%</span>
        </div>
        <div className="financing-stat">
          <span className="stat-label">Equity Required</span>
          <span className="stat-value">${Math.round(requiredEquity).toLocaleString()}</span>
        </div>
      </div>

      {/* Hold & Exit */}
      <h3>Hold &amp; exit</h3>
      <div className="field-grid">
        <div className="field">
          <label htmlFor="hold_period_years">Hold period (years)</label>
          <input
            id="hold_period_years"
            type="number"
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

      <div className="form-actions">
        <button type="submit" className="primary">
          {initial ? "Save changes" : "Add deal"}
        </button>
        <button type="button" className="secondary" onClick={onCancel}>
          Cancel
        </button>
      </div>
    </form>
  );
}
