import { formatPercent } from "../lib/format";
import type { DealOut, RankedDealOut } from "../lib/types";
import { ICONS } from "./Shell";
import type { Tab } from "./Shell";

interface HomeViewProps {
  deals: DealOut[];
  selectedCount: number;
  hurdleRate: number;
  rankedDeals: RankedDealOut[];
  onNavigate: (tab: Tab) => void;
}

const STEPS = [
  {
    n: "01",
    title: "Add your deals",
    blurb: "Enter price, rents, expenses, financing and the capital stack.",
  },
  {
    n: "02",
    title: "Compare side by side",
    blurb: "See NOI, cap rate, DSCR, cash-on-cash, IRR and equity multiple.",
  },
  {
    n: "03",
    title: "Rank with confidence",
    blurb: "Order by spread over your hurdle, then stress the downside.",
  },
];

const FEATURES: { tab: Tab; title: string; blurb: string }[] = [
  {
    tab: "deals",
    title: "Deals",
    blurb: "Build and manage your pipeline of multifamily acquisitions.",
  },
  {
    tab: "compare",
    title: "Compare",
    blurb: "Full underwriting metrics for up to five deals at a glance.",
  },
  {
    tab: "rank",
    title: "Rank",
    blurb: "Levered IRR spread over your hurdle rate, best deal first.",
  },
  {
    tab: "risk",
    title: "Risk-adjusted",
    blurb: "Factor DSCR, leverage and downside into the ranking.",
  },
  {
    tab: "sensitivity",
    title: "Sensitivity",
    blurb: "Flex rents, exit cap and rates to see what moves returns.",
  },
  {
    tab: "market",
    title: "Market check",
    blurb: "Test your rent assumptions against metro market data.",
  },
];

function Icon({ tab }: { tab: Tab }) {
  return (
    <svg viewBox="0 0 24 24" width="22" height="22" aria-hidden="true">
      <path d={ICONS[tab]} />
    </svg>
  );
}

export function HomeView({
  deals,
  selectedCount,
  hurdleRate,
  rankedDeals,
  onNavigate,
}: HomeViewProps) {
  const top = rankedDeals.find((r) => r.rank === 1) ?? rankedDeals[0];
  const topIrr = top?.metrics.levered_irr ?? null;

  return (
    <div className="home">
      <section className="home-hero">
        <div className="home-glow home-glow--a" aria-hidden="true" />
        <div className="home-glow home-glow--b" aria-hidden="true" />
        <div className="home-hero__body">
          <span className="home-eyebrow">Multifamily underwriting</span>
          <h1 className="home-title">
            Welcome to <span>DealRank</span>
          </h1>
          <p className="home-lede">
            DealRank turns a stack of multifamily acquisitions into a clear, defensible ranking.
            Underwrite each deal with a full capital stack, compare them side by side, and see which
            one earns the most over your hurdle rate &mdash; adjusted for risk.
          </p>
          <div className="home-cta">
            <button
              type="button"
              className="home-btn home-btn--solid"
              onClick={() => onNavigate(deals.length === 0 ? "deals" : "rank")}
            >
              {deals.length === 0 ? "Add your first deal" : "View rankings"}
              <svg viewBox="0 0 16 16" width="16" height="16" aria-hidden="true">
                <path d="M3 8h9M8.5 4l4 4-4 4" />
              </svg>
            </button>
            <button
              type="button"
              className="home-btn home-btn--ghost"
              onClick={() => onNavigate("deals")}
            >
              Manage deals
            </button>
          </div>
        </div>

        <div className="home-stats">
          <div className="home-stat">
            <span className="home-stat__value">{deals.length}</span>
            <span className="home-stat__label">Deals in pipeline</span>
          </div>
          <div className="home-stat">
            <span className="home-stat__value">{selectedCount}</span>
            <span className="home-stat__label">Selected to compare</span>
          </div>
          <div className="home-stat">
            <span className="home-stat__value">{formatPercent(hurdleRate)}</span>
            <span className="home-stat__label">Hurdle rate</span>
          </div>
          <div className="home-stat home-stat--top">
            <span className="home-stat__value">{top ? top.deal.name : "—"}</span>
            <span className="home-stat__label">
              {top
                ? `Top ranked${topIrr !== null ? ` · ${formatPercent(topIrr)} levered IRR` : ""}`
                : "Top ranked deal"}
            </span>
          </div>
        </div>
      </section>

      <section className="home-section">
        <h2 className="home-heading">How it works</h2>
        <ol className="home-steps">
          {STEPS.map((s) => (
            <li key={s.n} className="home-step">
              <span className="home-step__n">{s.n}</span>
              <strong>{s.title}</strong>
              <span>{s.blurb}</span>
            </li>
          ))}
        </ol>
      </section>

      <section className="home-section">
        <h2 className="home-heading">Jump in</h2>
        <div className="home-grid">
          {FEATURES.map((f) => (
            <button
              key={f.tab}
              type="button"
              className="home-tile"
              onClick={() => onNavigate(f.tab)}
            >
              <span className="home-tile__icon">
                <Icon tab={f.tab} />
              </span>
              <strong>{f.title}</strong>
              <span className="home-tile__blurb">{f.blurb}</span>
              <svg
                className="home-tile__arrow"
                viewBox="0 0 16 16"
                width="16"
                height="16"
                aria-hidden="true"
              >
                <path d="M3 8h9M8.5 4l4 4-4 4" />
              </svg>
            </button>
          ))}
        </div>
      </section>
    </div>
  );
}
