import { useState } from "react";
import { formatMoney, formatNumber } from "../lib/format";
import type { AnnualCashFlowOut, DealOut, MetricsOut } from "../lib/types";

interface ProjectionTableProps {
  deals: DealOut[];
  metricsByDealId: Record<string, MetricsOut>;
}

interface ProjectionRow {
  label: string;
  value: (cf: AnnualCashFlowOut) => string;
  kind?: "deduction" | "subtotal";
}

const ROWS: ProjectionRow[] = [
  { label: "Gross potential rent", value: (cf) => formatMoney(cf.gpr) },
  { label: "Vacancy loss", value: (cf) => formatMoney(cf.vacancy_loss), kind: "deduction" },
  { label: "Effective gross income", value: (cf) => formatMoney(cf.egi), kind: "subtotal" },
  { label: "Operating expenses", value: (cf) => formatMoney(cf.opex), kind: "deduction" },
  {
    label: "Turnover expense",
    value: (cf) => formatMoney(cf.turnover_expense),
    kind: "deduction",
  },
  { label: "NOI", value: (cf) => formatMoney(cf.noi), kind: "subtotal" },
  { label: "Debt service", value: (cf) => formatMoney(cf.debt_service), kind: "deduction" },
  {
    label: "Levered cash flow",
    value: (cf) => formatMoney(cf.levered_cash_flow),
    kind: "subtotal",
  },
  {
    label: "DSCR",
    value: (cf) => (cf.debt_service === 0 ? "—" : formatNumber(cf.noi / cf.debt_service)),
  },
  { label: "Loan balance (year end)", value: (cf) => formatMoney(cf.ending_loan_balance) },
];

/**
 * Year-by-year pro forma for one deal at a time: the comparison table
 * above only shows Year 1, so this is where NOI(year n) — rent and
 * expenses compounding at their own growth rates — debt service, DSCR
 * and levered cash flow can be read for every year of the hold.
 */
export function ProjectionTable({ deals, metricsByDealId }: ProjectionTableProps) {
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const deal = deals.find((d) => d.id === selectedId) ?? deals[0];
  if (!deal) return null;
  const metrics = metricsByDealId[deal.id];

  return (
    <section className="projection" aria-labelledby="projection-title">
      <div className="projection-header">
        <h3 id="projection-title">Year-by-year projection</h3>
        <div className="segmented" role="tablist" aria-label="Deal">
          {deals.map((d) => (
            <button
              key={d.id}
              type="button"
              role="tab"
              aria-selected={d.id === deal.id}
              className={d.id === deal.id ? "active" : ""}
              onClick={() => setSelectedId(d.id)}
            >
              {d.name}
            </button>
          ))}
        </div>
      </div>

      {!metrics ? (
        <div className="status-banner loading" role="status">
          <span className="spinner" aria-hidden="true" /> Calculating projection…
        </div>
      ) : (
        <>
          <div className="table-scroll">
            <table className="data-table projection-table">
              <thead>
                <tr>
                  <th scope="col">{deal.hold_period_years}-year hold</th>
                  {metrics.annual_cash_flows.map((cf) => (
                    <th key={cf.year} scope="col">
                      Year {cf.year}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {ROWS.map((row) => (
                  <tr key={row.label} className={row.kind ? `row-${row.kind}` : undefined}>
                    <th scope="row">
                      {row.kind === "deduction" && <span className="row-operator">less</span>}
                      {row.label}
                    </th>
                    {metrics.annual_cash_flows.map((cf) => (
                      <td key={cf.year}>{row.value(cf)}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="card-subtitle projection-note">
            Exit at the end of year {deal.hold_period_years}: year {deal.hold_period_years + 1} NOI
            of {formatMoney(metrics.forward_noi)} ÷ {formatNumber(deal.exit_cap_rate * 100)}% exit
            cap = {formatMoney(metrics.exit_value)} exit value.
          </p>
        </>
      )}
    </section>
  );
}
