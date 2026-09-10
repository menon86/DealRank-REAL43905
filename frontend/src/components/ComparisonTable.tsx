import { formatMoney, formatMultiple, formatNumber, formatPercent } from "../lib/format";
import type { DealOut, MetricsOut } from "../lib/types";

interface ComparisonTableProps {
  deals: DealOut[];
  metricsByDealId: Record<string, MetricsOut>;
}

interface Row {
  label: string;
  value: (deal: DealOut, metrics: MetricsOut) => string;
  className?: string;
}

const YEAR_ONE_ROWS: Row[] = [
  {
    label: "Gross potential rent",
    value: (_, m) => formatMoney(m.annual_cash_flows[0]?.gpr ?? null),
  },
  {
    label: "Vacancy loss",
    value: (_, m) => formatMoney(m.annual_cash_flows[0]?.vacancy_loss ?? null),
  },
  {
    label: "Effective gross income",
    value: (_, m) => formatMoney(m.annual_cash_flows[0]?.egi ?? null),
  },
  {
    label: "Operating expenses",
    value: (_, m) => formatMoney(m.annual_cash_flows[0]?.opex ?? null),
  },
  {
    label: "Turnover expense",
    value: (_, m) => formatMoney(m.annual_cash_flows[0]?.turnover_expense ?? null),
  },
  {
    label: "Year 1 NOI",
    value: (_, m) => formatMoney(m.year_one_noi),
    className: "headline-row",
  },
  {
    label: "Debt service",
    value: (_, m) => formatMoney(m.annual_cash_flows[0]?.debt_service ?? null),
  },
  {
    label: "Year 1 levered cash flow",
    value: (_, m) => formatMoney(m.annual_cash_flows[0]?.levered_cash_flow ?? null),
  },
];

const HEADLINE_ROWS: Row[] = [
  { label: "Going-in cap rate", value: (_, m) => formatPercent(m.going_in_cap_rate) },
  { label: "Year 1 DSCR", value: (_, m) => formatNumber(m.year_one_dscr) },
  { label: "Cash-on-cash", value: (_, m) => formatPercent(m.cash_on_cash) },
  {
    label: "Unlevered IRR",
    value: (_, m) => formatPercent(m.unlevered_irr),
    className: "headline-row",
  },
  { label: "Levered IRR", value: (_, m) => formatPercent(m.levered_irr) },
  { label: "Equity multiple", value: (_, m) => formatMultiple(m.equity_multiple) },
  { label: "Exit value", value: (_, m) => formatMoney(m.exit_value) },
  { label: "Net sale proceeds", value: (_, m) => formatMoney(m.net_sale_proceeds) },
];

export function ComparisonTable({ deals, metricsByDealId }: ComparisonTableProps) {
  if (deals.length === 0) {
    return (
      <div className="card">
        <h2>Comparison</h2>
        <div className="empty-state">Select 3–5 deals on the Deals tab to compare them.</div>
      </div>
    );
  }

  function renderRows(rows: Row[]) {
    return rows.map((row) => (
      <tr key={row.label} className={row.className}>
        <td>{row.label}</td>
        {deals.map((deal) => (
          <td key={deal.id}>{row.value(deal, metricsByDealId[deal.id])}</td>
        ))}
      </tr>
    ));
  }

  return (
    <div className="card">
      <h2>Comparison</h2>
      <div style={{ overflowX: "auto" }}>
        <table className="data-table">
          <thead>
            <tr>
              <th>Deal</th>
              {deals.map((deal) => (
                <th key={deal.id}>{deal.name}</th>
              ))}
            </tr>
            <tr>
              <th>Hold period</th>
              {deals.map((deal) => (
                <th key={deal.id} style={{ fontWeight: 400, textTransform: "none" }}>
                  {deal.hold_period_years} yrs
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            <tr className="section-row">
              <td>Year 1 waterfall</td>
              {deals.map((deal) => (
                <td key={deal.id} />
              ))}
            </tr>
            {renderRows(YEAR_ONE_ROWS)}
            <tr className="section-row">
              <td>Headline metrics</td>
              {deals.map((deal) => (
                <td key={deal.id} />
              ))}
            </tr>
            {renderRows(HEADLINE_ROWS)}
          </tbody>
        </table>
      </div>
      <p className="methodology-note">
        Both unlevered and levered IRR are shown; ranking (see the Rank tab) is based on unlevered
        IRR against your hurdle rate.
      </p>
    </div>
  );
}
