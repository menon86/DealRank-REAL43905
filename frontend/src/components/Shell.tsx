import type { ReactNode } from "react";

export type Tab = "home" | "deals" | "compare" | "rank" | "risk" | "sensitivity" | "market";

export const ICONS: Record<Tab, string> = {
  home: "M3 11l9-8 9 8M5 10v10h5v-6h4v6h5V10",
  deals: "M3 21V8l7-5 7 5v13M3 21h14M21 21V11l-4-2M7 12h2M7 16h2M13 12h1M13 16h1",
  compare: "M4 4h6v16H4zM14 4h6v16h-6z",
  rank: "M5 20V12M12 20V4M19 20v-6",
  risk: "M12 3l8 3v6c0 4.5-3.2 7.6-8 9-4.8-1.4-8-4.5-8-9V6z",
  sensitivity: "M4 7h10M18 7h2M4 17h2M10 17h10M14 5v4M6 15v4",
  market:
    "M12 21s7-5.6 7-11a7 7 0 10-14 0c0 5.4 7 11 7 11zM12 12.5a2.5 2.5 0 100-5 2.5 2.5 0 000 5z",
};

const TABS: { id: Tab; label: string }[] = [
  { id: "home", label: "Home" },
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
  const current = TABS.find((t) => t.id === activeTab);
  return (
    <div className="app-shell">
      <aside className="rail">
        <div className="brand">
          <span className="brand-mark" aria-hidden="true">
            <svg viewBox="0 0 24 24" width="18" height="18">
              <path d="M4 20V10l8-6 8 6v10M9 20v-6h6v6" />
            </svg>
          </span>
          <span className="brand-name">DealRank</span>
        </div>

        <div className="tab-strip" role="tablist" aria-label="Views" aria-orientation="vertical">
          {TABS.map((tab) => (
            <button
              key={tab.id}
              type="button"
              role="tab"
              aria-selected={tab.id === activeTab}
              className={tab.id === activeTab ? "active" : ""}
              onClick={() => onTabChange(tab.id)}
            >
              <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true">
                <path d={ICONS[tab.id]} />
              </svg>
              {tab.label}
            </button>
          ))}
        </div>

        <p className="rail-note">Multifamily deal comparison and ranking</p>
      </aside>

      <main className="app-main">
        {activeTab !== "home" && <h1 className="page-title">{current?.label}</h1>}
        {children}
      </main>
    </div>
  );
}
