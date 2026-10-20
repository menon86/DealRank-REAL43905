import type { ReactNode } from "react";

export type Tab = "deals" | "compare" | "rank" | "risk" | "sensitivity" | "market";

const TABS: { id: Tab; label: string }[] = [
  { id: "deals", label: "Deals" },
  { id: "compare", label: "Compare" },
  { id: "rank", label: "Rank" },
  { id: "risk", label: "Risk-adjusted" },
  { id: "sensitivity", label: "Sensitivity" },
  { id: "market", label: "Market check" },
];

interface ShellProps {
  activeTab: Tab;
  onTabChange: (tab: Tab) => void;
  children: ReactNode;
}

export function Shell({ activeTab, onTabChange, children }: ShellProps) {
  return (
    <div className="app-shell">
      <div className="app-header">
        <h1>DealRank</h1>
        <span className="subtitle">Deal comparison &amp; ranking — Deliverable 3</span>
      </div>

      <div className="tab-strip" role="tablist" aria-label="Views">
        {TABS.map((tab) => (
          <button
            key={tab.id}
            type="button"
            role="tab"
            aria-selected={tab.id === activeTab}
            className={tab.id === activeTab ? "active" : ""}
            onClick={() => onTabChange(tab.id)}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {children}
    </div>
  );
}
