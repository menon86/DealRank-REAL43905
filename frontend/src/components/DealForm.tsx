import { useState } from "react";
import { fractionToPercentInput, percentInputToFraction } from "../lib/format";
import { SUB_ASSET_CLASS_LABELS } from "../lib/types";
import type { DealCreate, DealOut, LeasingMode, SubAssetClass } from "../lib/types";

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
}

const DEFAULTS: FormState = {
  name: "",
  sub_asset_class: "suburban_garden",
  leasing_mode: "per_unit",
  unit_count: "100",
  monthly_rent_per_unit: "1500",
  bed_count: "",
  monthly_rent_per_bed: "",
  vacancy_rate_pct: "5",
  other_income_annual: "20000",
  opex_annual: "500000",
  expense_growth_rate_pct: "3",
  rent_growth_rate_pct: "3",
  lease_expiration_month: "6",
  turnover_cost_per_unit_or_bed: "700",
  annual_turnover_rate_pct: "50",
  purchase_price: "15000000",
  closing_costs: "300000",
  loan_amount: "9750000",
  interest_rate_pct: "6",
  amortization_years: "30",
  hold_period_years: "10",
  exit_cap_rate_pct: "6",
  selling_costs_rate_pct: "2",
};

function dealToFormState(deal: DealOut): FormState {
  return {
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

interface DealFormProps {
  initial: DealOut | null;
  onSave: (input: DealCreate) => void;
  onCancel: () => void;
}

export function DealForm({ initial, onSave, onCancel }: DealFormProps) {
  const [form, setForm] = useState<FormState>(initial ? dealToFormState(initial) : DEFAULTS);
  const [error, setError] = useState<string | null>(null);

  function set<K extends keyof FormState>(key: K, value: FormState[K]) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);

    if (!form.name.trim()) {
      setError("Name is required.");
      return;
    }

    const isPerUnit = form.leasing_mode === "per_unit";
    if (isPerUnit && (!form.unit_count || !form.monthly_rent_per_unit)) {
      setError("Per-unit deals require unit count and monthly rent per unit.");
      return;
    }
    if (!isPerUnit && (!form.bed_count || !form.monthly_rent_per_bed)) {
      setError("Per-bed deals require bed count and monthly rent per bed.");
      return;
    }

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

      <h3>Basics</h3>
      <div className="field-grid">
        <div className="field">
          <label htmlFor="name">Deal name</label>
          <input
            id="name"
            value={form.name}
            onChange={(e) => set("name", e.target.value)}
            placeholder="e.g. Campus View Student Housing"
          />
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
              />
            </div>
            <div className="field">
              <label htmlFor="monthly_rent_per_unit">Monthly rent / unit ($)</label>
              <input
                id="monthly_rent_per_unit"
                type="number"
                value={form.monthly_rent_per_unit}
                onChange={(e) => set("monthly_rent_per_unit", e.target.value)}
              />
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
              />
            </div>
            <div className="field">
              <label htmlFor="monthly_rent_per_bed">Monthly rent / bed ($)</label>
              <input
                id="monthly_rent_per_bed"
                type="number"
                value={form.monthly_rent_per_bed}
                onChange={(e) => set("monthly_rent_per_bed", e.target.value)}
              />
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
          />
        </div>
        <div className="field">
          <label htmlFor="other_income_annual">Other income, annual ($)</label>
          <input
            id="other_income_annual"
            type="number"
            value={form.other_income_annual}
            onChange={(e) => set("other_income_annual", e.target.value)}
          />
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
          />
        </div>
        <div className="field">
          <label htmlFor="expense_growth_rate_pct">Expense growth rate (%/yr)</label>
          <input
            id="expense_growth_rate_pct"
            type="number"
            step="0.1"
            value={form.expense_growth_rate_pct}
            onChange={(e) => set("expense_growth_rate_pct", e.target.value)}
          />
        </div>
        <div className="field">
          <label htmlFor="rent_growth_rate_pct">Rent growth rate (%/yr)</label>
          <input
            id="rent_growth_rate_pct"
            type="number"
            step="0.1"
            value={form.rent_growth_rate_pct}
            onChange={(e) => set("rent_growth_rate_pct", e.target.value)}
          />
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
          />
        </div>
        <div className="field">
          <label htmlFor="turnover_cost_per_unit_or_bed">Turnover cost / unit or bed ($)</label>
          <input
            id="turnover_cost_per_unit_or_bed"
            type="number"
            value={form.turnover_cost_per_unit_or_bed}
            onChange={(e) => set("turnover_cost_per_unit_or_bed", e.target.value)}
          />
        </div>
        <div className="field">
          <label htmlFor="annual_turnover_rate_pct">Annual turnover rate (%)</label>
          <input
            id="annual_turnover_rate_pct"
            type="number"
            step="0.1"
            value={form.annual_turnover_rate_pct}
            onChange={(e) => set("annual_turnover_rate_pct", e.target.value)}
          />
        </div>
      </div>

      <h3>Acquisition &amp; financing</h3>
      <div className="field-grid">
        <div className="field">
          <label htmlFor="purchase_price">Purchase price ($)</label>
          <input
            id="purchase_price"
            type="number"
            value={form.purchase_price}
            onChange={(e) => set("purchase_price", e.target.value)}
          />
        </div>
        <div className="field">
          <label htmlFor="closing_costs">Closing costs ($)</label>
          <input
            id="closing_costs"
            type="number"
            value={form.closing_costs}
            onChange={(e) => set("closing_costs", e.target.value)}
          />
        </div>
        <div className="field">
          <label htmlFor="loan_amount">Loan amount ($)</label>
          <input
            id="loan_amount"
            type="number"
            value={form.loan_amount}
            onChange={(e) => set("loan_amount", e.target.value)}
          />
        </div>
        <div className="field">
          <label htmlFor="interest_rate_pct">Interest rate (%)</label>
          <input
            id="interest_rate_pct"
            type="number"
            step="0.01"
            value={form.interest_rate_pct}
            onChange={(e) => set("interest_rate_pct", e.target.value)}
          />
        </div>
        <div className="field">
          <label htmlFor="amortization_years">Amortization (years)</label>
          <input
            id="amortization_years"
            type="number"
            value={form.amortization_years}
            onChange={(e) => set("amortization_years", e.target.value)}
          />
        </div>
      </div>

      <h3>Hold &amp; exit</h3>
      <div className="field-grid">
        <div className="field">
          <label htmlFor="hold_period_years">Hold period (years)</label>
          <input
            id="hold_period_years"
            type="number"
            value={form.hold_period_years}
            onChange={(e) => set("hold_period_years", e.target.value)}
          />
        </div>
        <div className="field">
          <label htmlFor="exit_cap_rate_pct">Exit cap rate (%)</label>
          <input
            id="exit_cap_rate_pct"
            type="number"
            step="0.01"
            value={form.exit_cap_rate_pct}
            onChange={(e) => set("exit_cap_rate_pct", e.target.value)}
          />
        </div>
        <div className="field">
          <label htmlFor="selling_costs_rate_pct">Selling costs rate (%)</label>
          <input
            id="selling_costs_rate_pct"
            type="number"
            step="0.1"
            value={form.selling_costs_rate_pct}
            onChange={(e) => set("selling_costs_rate_pct", e.target.value)}
          />
        </div>
      </div>

      {error && <p className="field error">{error}</p>}

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
