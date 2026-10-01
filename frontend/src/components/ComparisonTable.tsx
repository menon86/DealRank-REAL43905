import { formatMoney, formatMultiple, formatNumber, formatPercent } from "../lib/format";
import type { DealOut, MetricsOut } from "../lib/types";
import { ProjectionTable } from "./ProjectionTable";
import { ReportDownloads } from "./ReportDownloads";

/** v1 scope: 3–5 deals per comparison. */
const MIN_DEALS = 3;

interface ComparisonTableProps {
  deals: DealOut[];
  metricsByDealId: Record<string, MetricsOut>;
  hurdleRate: number;
  loading: boolean;
  error: string | null;
  onRetry: () => void;
}

/**
 * - "deduction": a line subtracted on the way down the waterfall
 *   (rendered with a "less" prefix, so GPR → EGI → NOI reads as arithmetic)
 * - "addition": a line added in (closing costs, on the way to equity)
 * - "subtotal": EGI, NOI, equity invested, exit value and net sale
 *   proceeds — the lines the additions and deductions roll up into
 * - "ranking-basis": unlevered IRR, the one figure the Rank tab sorts on
 * - "reference": levered IRR, shown but never ranked on
 */
type RowKind = "deduction" | "addition" | "subtotal" | "ranking-basis" | "reference";

interface Row {
  label: string;
  value: (deal: DealOut, metrics: MetricsOut) => string;
  kind?: RowKind;
  note?: string;
}

const YEAR_ONE_ROWS: Row[] = [
  {
    label: "Gross potential rent",
    value: (_, m) => formatMoney(m.annual_cash_flows[0]?.gpr ?? null),
  },
  {
    label: "Vacancy loss",
    value: (_, m) => formatMoney(m.annual_cash_flows[0]?.vacancy_loss ?? null),
    kind: "deduction",
  },
  {
    label: "Effective gross income",
    value: (_, m) => formatMoney(m.annual_cash_flows[0]?.egi ?? null),
    kind: "subtotal",
  },
  {
    label: "Operating expenses",
    value: (_, m) => formatMoney(m.annual_cash_flows[0]?.opex ?? null),
    kind: "deduction",
  },
  {
    label: "Turnover expense",
    value: (_, m) => formatMoney(m.annual_cash_flows[0]?.turnover_expense ?? null),
    kind: "deduction",
  },
  {
    label: "Year 1 NOI",
    value: (_, m) => formatMoney(m.year_one_noi),
    kind: "subtotal",
  },
  {
    label: "Debt service",
    value: (_, m) => formatMoney(m.annual_cash_flows[0]?.debt_service ?? null),
    kind: "deduction",
  },
  {
    label: "Year 1 levered cash flow",
    value: (_, m) => formatMoney(m.annual_cash_flows[0]?.levered_cash_flow ?? null),
    kind: "subtotal",
  },
];

const RETURN_ROWS: Row[] = [
  {
    label: "Unlevered IRR",
    value: (_, m) => formatPercent(m.unlevered_irr),
    kind: "ranking-basis",
    note: "Ranking basis",
  },
  {
    label: "Levered IRR",
    value: (_, m) => formatPercent(m.levered_irr),
    kind: "reference",
    note: "Reference only",
  },
];

const EQUITY_ROWS: Row[] = [
  { label: "Purchase price", value: (d) => formatMoney(d.purchase_price) },
  { label: "Closing costs", value: (d) => formatMoney(d.closing_costs), kind: "addition" },
  { label: "Loan amount", value: (d) => formatMoney(d.loan_amount), kind: "deduction" },
  { label: "Equity invested", value: (_, m) => formatMoney(m.equity_invested), kind: "subtotal" },
  { label: "Cash-on-cash", value: (_, m) => formatPercent(m.cash_on_cash) },
  { label: "Total distributions", value: (_, m) => formatMoney(m.total_distributions) },
  { label: "Equity multiple", value: (_, m) => formatMultiple(m.equity_multiple) },
];

const OPERATING_METRIC_ROWS: Row[] = [
  { label: "Going-in cap rate", value: (_, m) => formatPercent(m.going_in_cap_rate) },
  { label: "Year 1 DSCR", value: (_, m) => formatNumber(m.year_one_dscr) },
];

const EXIT_ROWS: Row[] = [
  { label: "Forward NOI (year N+1)", value: (_, m) => formatMoney(m.forward_noi) },
  { label: "Exit cap rate", value: (d) => formatPercent(d.exit_cap_rate) },
  { label: "Exit value", value: (_, m) => formatMoney(m.exit_value), kind: "subtotal" },
  { label: "Selling costs", value: (_, m) => formatMoney(m.selling_costs), kind: "deduction" },
  {
    label: "Loan balance at exit",
    value: (_, m) => formatMoney(m.loan_balance_at_exit),
    kind: "deduction",
  },
  {
    label: "Net sale proceeds",
    value: (_, m) => formatMoney(m.net_sale_proceeds),
    kind: "subtotal",
  },
];

/** The v1 scope's per-deal formulas, shown verbatim under the table. */
const FORMULAS: [string, string][] = [
  ["EGI", "Gross potential rent × (1 − vacancy rate) + other income"],
  ["NOI", "EGI − operating expenses (including turnover)"],
  [
    "NOI (year n)",
    "Rent grows at the rent growth rate and expenses at the expense growth rate, compounded annually",
  ],
  ["Equity invested", "Purchase price + closing costs − loan amount"],
  ["Going-in cap rate", "Year 1 NOI ÷ purchase price"],
  ["Annual debt service", "Standard amortizing payment from loan amount, rate and term"],
  ["DSCR", "NOI ÷ annual debt service"],
  ["Levered cash flow (year n)", "NOI (year n) − debt service"],
  ["Cash-on-cash", "Year 1 levered cash flow ÷ equity invested"],
  ["Exit value", "NOI (year N+1) ÷ exit cap rate"],
  ["Net sale proceeds", "Exit value − selling costs − remaining loan balance"],
  ["Levered IRR", "IRR of −equity, levered cash flow years 1…N, plus net sale proceeds in year N"],
  [
    "Unlevered IRR",
    "IRR of −(price + closing costs), NOI years 1…N, plus exit value − selling costs in year N; no debt",
  ],
  [
    "Equity multiple",
    "Total distributions (levered cash flows + net sale proceeds) ÷ equity invested",
  ],
];

export function ComparisonTable({
  deals,
  metricsByDealId,
  hurdleRate,
  loading,
  error,
  onRetry,
}: ComparisonTableProps) {
  if (deals.length === 0) {
    return (
      <div className="card">
        <h2>Comparison</h2>
        <div className="empty-state">Select 3–5 deals on the Deals tab to compare them.</div>
      </div>
    );
  }

  const columnCount = deals.length + 1;

  function renderSection(title: string) {
    return (
      <tr className="section-row">
        <td colSpan={columnCount}>{title}</td>
      </tr>
    );
  }

  function renderRows(rows: Row[]) {
    return rows.map((row) => (
      <tr key={row.label} className={row.kind ? `row-${row.kind}` : undefined}>
        <th scope="row">
          {row.kind === "deduction" && <span className="row-operator">less</span>}
          {row.kind === "addition" && <span className="row-operator">plus</span>}
          {row.label}
          {row.note && <span className={`row-tag tag-${row.kind}`}>{row.note}</span>}
        </th>
        {deals.map((deal) => {
          const metrics = metricsByDealId[deal.id];
          return (
            <td key={deal.id}>
              {metrics ? row.value(deal, metrics) : <span className="cell-placeholder">…</span>}
            </td>
          );
        })}
      </tr>
    ));
  }

  return (
    <div className="card">
      <div className="card-header">
        <div>
          <h2>Comparison</h2>
          <p className="card-subtitle">
            {deals.length} deals side by side · Year 1 operating waterfall, returns, equity and exit
          </p>
        </div>
        <ReportDownloads dealIds={deals.map((deal) => deal.id)} hurdleRate={hurdleRate} />
      </div>

      {deals.length < MIN_DEALS && (
        <div className="status-banner info" role="status">
          The v1 comparison covers 3–5 deals. Select {MIN_DEALS - deals.length} more on the Deals
          tab.
        </div>
      )}

      {error && (
        <div className="status-banner error" role="alert">
          Couldn&apos;t load metrics for every selected deal. {error}
          <button type="button" className="link" onClick={onRetry}>
            Retry
          </button>
        </div>
      )}
      {loading && !error && (
        <div className="status-banner loading" role="status">
          <span className="spinner" aria-hidden="true" /> Calculating metrics…
        </div>
      )}

      <div className="table-scroll">
        <table className={`data-table comparison-table cols-${deals.length}`} aria-busy={loading}>
          <colgroup>
            <col className="label-col" />
            {deals.map((deal) => (
              <col key={deal.id} />
            ))}
          </colgroup>
          <thead>
            <tr>
              <th scope="col">Deal</th>
              {deals.map((deal) => (
                <th key={deal.id} scope="col" className="deal-name">
                  {deal.name}
                  <span className="deal-meta">{deal.hold_period_years}-yr hold</span>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {renderSection("Year 1 operating waterfall")}
            {renderRows(YEAR_ONE_ROWS)}
            {renderSection("Returns")}
            {renderRows(RETURN_ROWS)}
            {renderSection("Equity & cash yield")}
            {renderRows(EQUITY_ROWS)}
            {renderSection("Operating metrics")}
            {renderRows(OPERATING_METRIC_ROWS)}
            {renderSection("Exit (end of hold)")}
            {renderRows(EXIT_ROWS)}
          </tbody>
        </table>
      </div>

      <p className="methodology-note">
        <strong>Unlevered IRR is the ranking basis.</strong> Both IRRs are shown, but the Rank tab
        sorts on unlevered IRR against your hurdle rate; levered IRR is for reference only.
      </p>

      <details className="formula-reference">
        <summary>How each metric is calculated</summary>
        <dl>
          {FORMULAS.map(([name, formula]) => (
            <div key={name}>
              <dt>{name}</dt>
              <dd>{formula}</dd>
            </div>
          ))}
        </dl>
      </details>

      <ProjectionTable deals={deals} metricsByDealId={metricsByDealId} />
    </div>
  );
}
