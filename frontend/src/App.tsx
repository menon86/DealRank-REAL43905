import { useEffect, useMemo, useRef, useState } from "react";
import { ComparisonTable } from "./components/ComparisonTable";
import { DealForm } from "./components/DealForm";
import { DealList } from "./components/DealList";
import { HomeView } from "./components/HomeView";
import { MarketCheckView } from "./components/MarketCheckView";
import { RankingView } from "./components/RankingView";
import { RiskRankingView } from "./components/RiskRankingView";
import { SensitivityView } from "./components/SensitivityView";
import { ChatPanel } from "./components/ChatPanel";
import type { RankingSettings } from "./components/ChatPanel";
import { Shell } from "./components/Shell";
import type { Tab } from "./components/Shell";
import * as client from "./lib/client";
import type { DealCreate, DealOut, MetricsOut, RankedDealOut } from "./lib/types";

const DEFAULT_HURDLE_RATE = 0.08;

export function App() {
  const [activeTab, setActiveTab] = useState<Tab>("home");
  const [deals, setDeals] = useState<DealOut[]>([]);
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [editingDeal, setEditingDeal] = useState<DealOut | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [hurdleRate, setHurdleRate] = useState(DEFAULT_HURDLE_RATE);
  const [rankedDeals, setRankedDeals] = useState<RankedDealOut[]>([]);
  const [metricsByDealId, setMetricsByDealId] = useState<Record<string, MetricsOut>>({});
  const [metricsLoading, setMetricsLoading] = useState(false);
  const [metricsError, setMetricsError] = useState<string | null>(null);
  /** Deals whose latest metrics fetch failed: the numbers shown are from an earlier fetch. */
  const [staleMetricIds, setStaleMetricIds] = useState<string[]>([]);
  const [metricsReloadKey, setMetricsReloadKey] = useState(0);
  const [rankLoading, setRankLoading] = useState(false);
  const [rankError, setRankError] = useState<string | null>(null);
  const [rankReloadKey, setRankReloadKey] = useState(0);
  const [chatOpen, setChatOpen] = useState(false);
  const chatLauncherRef = useRef<HTMLButtonElement | null>(null);
  const chatWasOpen = useRef(false);
  const [riskSettings, setRiskSettings] = useState<RankingSettings>({});
  const [apiError, setApiError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  /** A save or delete succeeded but re-reading the deal list failed. */
  const [refreshError, setRefreshError] = useState<{ done: string; detail: string } | null>(null);
  const [initialLoading, setInitialLoading] = useState(true);
  const [initialLoadKey, setInitialLoadKey] = useState(0);

  useEffect(() => {
    let cancelled = false;
    setInitialLoading(true);
    client
      .listDeals()
      .then((loaded) => {
        if (cancelled) return;
        setApiError(null);
        setDeals(loaded);
        setSelectedIds(loaded.slice(0, 3).map((d) => d.id));
      })
      .catch(() => {
        if (cancelled) return;
        setApiError(
          "Couldn't reach the DealRank API. Make sure the backend is running " +
            "(see backend/README or docs/build-plan.md) and VITE_API_BASE_URL points at it.",
        );
      })
      .finally(() => {
        if (!cancelled) setInitialLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [initialLoadKey]);

  // Closing the chat panel hands focus back to the button that opened it.
  useEffect(() => {
    if (chatWasOpen.current && !chatOpen) chatLauncherRef.current?.focus();
    chatWasOpen.current = chatOpen;
  }, [chatOpen]);

  const selectedDeals = useMemo(
    () =>
      selectedIds
        .map((id) => deals.find((d) => d.id === id))
        .filter((d): d is DealOut => Boolean(d)),
    [selectedIds, deals],
  );

  // Metrics come from the backend's calculation engine (GET
  // /deals/{id}/metrics), one call per selected deal, rather than being
  // recomputed client-side — the API is the single source of truth now
  // that Phase 3 exists. A failure is surfaced on the comparison table
  // with a retry, not swallowed.
  useEffect(() => {
    if (selectedDeals.length === 0) {
      setMetricsByDealId({});
      setStaleMetricIds([]);
      setMetricsLoading(false);
      setMetricsError(null);
      return;
    }
    let cancelled = false;
    setMetricsLoading(true);
    setMetricsError(null);
    // allSettled, so one failing deal doesn't hide the others' fresh numbers.
    // A deal whose fetch failed keeps its previous metrics, flagged as stale
    // so the table never presents them as current.
    Promise.allSettled(selectedDeals.map((deal) => client.getMetrics(deal.id))).then((results) => {
      if (cancelled) return;
      setMetricsByDealId((previous) => {
        const entries: Record<string, MetricsOut> = {};
        selectedDeals.forEach((deal, i) => {
          const result = results[i];
          if (result.status === "fulfilled") entries[deal.id] = result.value;
          else if (previous[deal.id]) entries[deal.id] = previous[deal.id];
        });
        return entries;
      });
      const failed = results.find((r): r is PromiseRejectedResult => r.status === "rejected");
      setStaleMetricIds(
        selectedDeals.filter((_, i) => results[i].status === "rejected").map((deal) => deal.id),
      );
      setMetricsError(failed ? client.describeError(failed.reason) : null);
      setMetricsLoading(false);
    });
    return () => {
      cancelled = true;
    };
  }, [selectedDeals, metricsReloadKey]);

  // Same as above for POST /rank: the ranking view shows a loading state
  // while a new hurdle is being applied and a real error if it fails. The
  // cancelled flag drops responses for a hurdle the user has since typed
  // past, so a slow earlier request can't overwrite a newer ranking.
  useEffect(() => {
    if (selectedIds.length === 0) {
      setRankedDeals([]);
      setRankLoading(false);
      setRankError(null);
      return;
    }
    let cancelled = false;
    setRankLoading(true);
    setRankError(null);
    client
      .rank(selectedIds, hurdleRate)
      .then((ranked) => {
        if (!cancelled) setRankedDeals(ranked);
      })
      .catch((err) => {
        if (!cancelled) setRankError(client.describeError(err));
      })
      .finally(() => {
        if (!cancelled) setRankLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [selectedIds, hurdleRate, deals, rankReloadKey]);

  function toggleSelected(id: string) {
    setSelectedIds((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]));
  }

  /**
   * Re-reads the deal list after a save or delete. The write has already
   * succeeded by the time this runs, so a failure here is reported as a
   * refresh problem with a retry, never as the write failing.
   */
  async function refreshDeals(done: string) {
    try {
      setDeals(await client.listDeals());
      setRefreshError(null);
    } catch (err) {
      setRefreshError({ done, detail: client.describeError(err) });
    }
  }

  async function handleSave(input: DealCreate) {
    // A failed write throws back to the form, which shows the error.
    if (editingDeal) {
      await client.updateDeal(editingDeal.id, input);
    } else {
      const created = await client.createDeal(input);
      setSelectedIds((prev) => (prev.length < 5 ? [...prev, created.id] : prev));
    }
    setShowForm(false);
    setEditingDeal(null);
    await refreshDeals("Saved");
  }

  async function handleDelete(id: string) {
    const name = deals.find((d) => d.id === id)?.name ?? "this deal";
    if (!window.confirm(`Delete "${name}"? This can't be undone.`)) return;
    setActionError(null);
    try {
      await client.deleteDeal(id);
    } catch (err) {
      setActionError(`Couldn't delete the deal. ${client.describeError(err)}`);
      return;
    }
    setSelectedIds((prev) => prev.filter((x) => x !== id));
    // Drop it locally straight away, so the list is right even if the refresh fails.
    setDeals((prev) => prev.filter((d) => d.id !== id));
    if (editingDeal?.id === id) {
      setShowForm(false);
      setEditingDeal(null);
    }
    await refreshDeals("Deleted");
  }

  if (apiError) {
    return (
      <Shell activeTab={activeTab} onTabChange={setActiveTab}>
        <div className="card">
          <h2>Can&apos;t connect to the backend</h2>
          <p style={{ fontSize: 13, color: "var(--color-negative)" }}>{apiError}</p>
          <button
            type="button"
            className="primary"
            disabled={initialLoading}
            onClick={() => setInitialLoadKey((key) => key + 1)}
          >
            {initialLoading ? "Retrying…" : "Retry"}
          </button>
        </div>
      </Shell>
    );
  }

  if (initialLoading) {
    return (
      <Shell activeTab={activeTab} onTabChange={setActiveTab}>
        <div className="status-banner loading" role="status">
          <span className="spinner" aria-hidden="true" /> Loading deals…
        </div>
      </Shell>
    );
  }

  return (
    <Shell activeTab={activeTab} onTabChange={setActiveTab}>
      {activeTab === "home" && (
        <HomeView
          deals={deals}
          selectedCount={selectedIds.length}
          hurdleRate={hurdleRate}
          rankedDeals={rankedDeals}
          onNavigate={setActiveTab}
        />
      )}

      {refreshError && (
        <div className="status-banner error" role="alert">
          {refreshError.done}, but couldn&apos;t refresh the deal list. {refreshError.detail}
          <button
            type="button"
            className="link"
            onClick={() => void refreshDeals(refreshError.done)}
          >
            Retry
          </button>
          <button type="button" className="link" onClick={() => setRefreshError(null)}>
            Dismiss
          </button>
        </div>
      )}

      {activeTab === "deals" && (
        <>
          {actionError && (
            <div className="status-banner error" role="alert">
              {actionError}
              <button type="button" className="link" onClick={() => setActionError(null)}>
                Dismiss
              </button>
            </div>
          )}
          <DealList
            deals={deals}
            selectedIds={selectedIds}
            onToggleSelected={toggleSelected}
            onEdit={(deal) => {
              setEditingDeal(deal);
              setShowForm(true);
            }}
            onDelete={handleDelete}
            onAddNew={() => {
              setEditingDeal(null);
              setShowForm(true);
            }}
          />
          {showForm && (
            <DealForm
              key={editingDeal?.id ?? "new"}
              initial={editingDeal}
              onSave={handleSave}
              onCancel={() => {
                setShowForm(false);
                setEditingDeal(null);
              }}
            />
          )}
        </>
      )}

      {activeTab === "compare" && (
        <ComparisonTable
          deals={selectedDeals}
          metricsByDealId={metricsByDealId}
          hurdleRate={hurdleRate}
          loading={metricsLoading}
          error={metricsError}
          staleDealIds={staleMetricIds}
          onRetry={() => setMetricsReloadKey((key) => key + 1)}
        />
      )}

      {activeTab === "rank" && (
        <RankingView
          selectedDealIds={selectedIds}
          hurdleRate={hurdleRate}
          onHurdleRateChange={setHurdleRate}
          rankedDeals={rankedDeals}
          loading={rankLoading}
          error={rankError}
          onRetry={() => setRankReloadKey((key) => key + 1)}
        />
      )}

      {activeTab === "risk" && (
        <RiskRankingView selectedDealIds={selectedIds} onSettingsChange={setRiskSettings} />
      )}
      {activeTab === "sensitivity" && <SensitivityView deals={deals} />}
      {activeTab === "market" && <MarketCheckView deals={deals} />}

      {!chatOpen && (
        <button
          ref={chatLauncherRef}
          type="button"
          className="primary chat-launcher"
          onClick={() => setChatOpen(true)}
        >
          Ask DealRank
        </button>
      )}
      <ChatPanel
        open={chatOpen}
        onClose={() => setChatOpen(false)}
        selectedDealIds={selectedIds}
        rankingSettings={{ ...riskSettings, hurdle_rate: hurdleRate }}
      />
    </Shell>
  );
}
