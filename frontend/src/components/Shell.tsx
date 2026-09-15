import type { ReactNode } from "react";

export type Tab = "deals" | "compare" | "rank";

const TABS: { id: Tab; label: string }[] = [
  { id: "deals", label: "Deals" },
  { id: "compare", label: "Compare" },
  { id: "rank", label: "Rank" },
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
        <span className="subtitle">Deal comparison &amp; ranking — Deliverable 2</span>
      </div>

      <div className="tab-strip">
        {TABS.map((tab) => (
          <button
            key={tab.id}
            type="button"
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
