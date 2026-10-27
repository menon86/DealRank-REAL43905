import { formatPercent } from "../lib/format";
import type { DealOut, RankedDealOut } from "../lib/types";
import type { Tab } from "./Shell";

interface HomeViewProps {
  deals: DealOut[];
  selectedCount: number;
  hurdleRate: number;
  rankedDeals: RankedDealOut[];
  onNavigate: (tab: Tab) => void;
}

const SHORTCUTS: { tab: Tab; title: string; blurb: string }[] = [
  { tab: "deals", title: "Deals", blurb: "Add, edit and select the deals to analyze." },
  { tab: "compare", title: "Compare", blurb: "Side-by-side metrics for the selected deals." },
  { tab: "rank", title: "Rank", blurb: "Order deals by spread over your hurdle rate." },
  { tab: "risk", title: "Risk-adjusted", blurb: "Rank with downside and risk factored in." },
  { tab: "sensitivity", title: "Sensitivity", blurb: "Stress key assumptions and see the impact." },
  { tab: "market", title: "Market check", blurb: "Test rents against market data." },
];

export function HomeView({
  deals,
  selectedCount,
  hurdleRate,
  rankedDeals,
  onNavigate,
}: HomeViewProps) {
  const top = rankedDeals.find((r) => r.rank === 1) ?? rankedDeals[0];

  return (
    <>
      <div className="card home-hero">
        <h2>Welcome to DealRank</h2>
        <p>Risk-adjusted multifamily deal comparison and ranking.</p>
        <div className="home-stats">
          <div>
            <span className="home-stat-value">{deals.length}</span>
            <span className="home-stat-label">Deals</span>
          </div>
          <div>
            <span className="home-stat-value">{selectedCount}</span>
            <span className="home-stat-label">Selected</span>
          </div>
          <div>
            <span className="home-stat-value">{formatPercent(hurdleRate)}</span>
            <span className="home-stat-label">Hurdle rate</span>
          </div>
        </div>
        {top && (
          <p className="home-top">
            Top ranked: <strong>{top.deal.name}</strong>
            {top.metrics.levered_irr !== null && (
              <> &middot; levered IRR {formatPercent(top.metrics.levered_irr)}</>
            )}
          </p>
        )}
        {deals.length === 0 && (
          <button type="button" className="primary" onClick={() => onNavigate("deals")}>
            Add your first deal
          </button>
        )}
      </div>

      <div className="home-grid">
        {SHORTCUTS.map((s) => (
          <button key={s.tab} type="button" className="home-tile" onClick={() => onNavigate(s.tab)}>
            <strong>{s.title}</strong>
            <span>{s.blurb}</span>
          </button>
        ))}
      </div>
    </>
  );
}
