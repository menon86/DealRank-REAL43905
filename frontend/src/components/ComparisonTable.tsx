import { formatMoney, formatMultiple, formatNumber, formatPercent } from "../lib/format";
import type { DealOut, MetricsOut } from "../lib/types";
import { ReportDownloads } from "./ReportDownloads";

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
 * - "subtotal": EGI and NOI, the lines the deductions roll up into
 * - "ranking-basis": unlevered IRR, the one figure the Rank tab sorts on
 * - "reference": levered IRR, shown but never ranked on
 */
type RowKind = "deduction" | "subtotal" | "ranking-basis" | "reference";

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

const OTHER_METRIC_ROWS: Row[] = [
  { label: "Going-in cap rate", value: (_, m) => formatPercent(m.going_in_cap_rate) },
  { label: "Year 1 DSCR", value: (_, m) => formatNumber(m.year_one_dscr) },
  { label: "Cash-on-cash", value: (_, m) => formatPercent(m.cash_on_cash) },
  { label: "Equity multiple", value: (_, m) => formatMultiple(m.equity_multiple) },
  { label: "Exit value", value: (_, m) => formatMoney(m.exit_value) },
  { label: "Net sale proceeds", value: (_, m) => formatMoney(m.net_sale_proceeds) },
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
            {deals.length} deals side by side · Year 1 operating waterfall, then returns
          </p>
        </div>
        <ReportDownloads dealIds={deals.map((deal) => deal.id)} hurdleRate={hurdleRate} />
      </div>

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
            {renderSection("Other metrics")}
            {renderRows(OTHER_METRIC_ROWS)}
          </tbody>
        </table>
      </div>

      <p className="methodology-note">
        <strong>Unlevered IRR is the ranking basis.</strong> Both IRRs are shown, but the Rank tab
        sorts on unlevered IRR against your hurdle rate; levered IRR is for reference only.
      </p>
    </div>
  );
}
