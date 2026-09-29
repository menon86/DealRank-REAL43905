import { useEffect, useMemo, useState } from "react";
import { ComparisonTable } from "./components/ComparisonTable";
import { DealForm } from "./components/DealForm";
import { DealList } from "./components/DealList";
import { RankingView } from "./components/RankingView";
import { Shell } from "./components/Shell";
import type { Tab } from "./components/Shell";
import * as client from "./lib/client";
import type { DealCreate, DealOut, MetricsOut, RankedDealOut } from "./lib/types";

const DEFAULT_HURDLE_RATE = 0.08;

export function App() {
  const [activeTab, setActiveTab] = useState<Tab>("deals");
  const [deals, setDeals] = useState<DealOut[]>([]);
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [editingDeal, setEditingDeal] = useState<DealOut | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [hurdleRate, setHurdleRate] = useState(DEFAULT_HURDLE_RATE);
  const [rankedDeals, setRankedDeals] = useState<RankedDealOut[]>([]);
  const [metricsByDealId, setMetricsByDealId] = useState<Record<string, MetricsOut>>({});
  const [metricsLoading, setMetricsLoading] = useState(false);
  const [metricsError, setMetricsError] = useState<string | null>(null);
  const [metricsReloadKey, setMetricsReloadKey] = useState(0);
  const [rankLoading, setRankLoading] = useState(false);
  const [rankError, setRankError] = useState<string | null>(null);
  const [rankReloadKey, setRankReloadKey] = useState(0);
  const [apiError, setApiError] = useState<string | null>(null);

  useEffect(() => {
    client
      .listDeals()
      .then((loaded) => {
        setApiError(null);
        setDeals(loaded);
        setSelectedIds(loaded.slice(0, 3).map((d) => d.id));
      })
      .catch(() => {
        setApiError(
          "Couldn't reach the DealRank API. Make sure the backend is running " +
            "(see backend/README or docs/build-plan.md) and VITE_API_BASE_URL points at it.",
        );
      });
  }, []);

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
      setMetricsLoading(false);
      setMetricsError(null);
      return;
    }
    let cancelled = false;
    setMetricsLoading(true);
    setMetricsError(null);
    Promise.all(selectedDeals.map((deal) => client.getMetrics(deal.id)))
      .then((results) => {
        if (cancelled) return;
        const entries: Record<string, MetricsOut> = {};
        selectedDeals.forEach((deal, i) => {
          entries[deal.id] = results[i];
        });
        setMetricsByDealId(entries);
      })
      .catch((err) => {
        if (!cancelled) setMetricsError(client.describeError(err));
      })
      .finally(() => {
        if (!cancelled) setMetricsLoading(false);
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

  async function refreshDeals() {
    setDeals(await client.listDeals());
  }

  async function handleSave(input: DealCreate) {
    if (editingDeal) {
      await client.updateDeal(editingDeal.id, input);
    } else {
      const created = await client.createDeal(input);
      setSelectedIds((prev) => (prev.length < 5 ? [...prev, created.id] : prev));
    }
    setShowForm(false);
    setEditingDeal(null);
    await refreshDeals();
  }

  async function handleDelete(id: string) {
    await client.deleteDeal(id);
    setSelectedIds((prev) => prev.filter((x) => x !== id));
    await refreshDeals();
  }

  if (apiError) {
    return (
      <Shell activeTab={activeTab} onTabChange={setActiveTab}>
        <div className="card">
          <h2>Can&apos;t connect to the backend</h2>
          <p style={{ fontSize: 13, color: "var(--color-negative)" }}>{apiError}</p>
        </div>
      </Shell>
    );
  }

  return (
    <Shell activeTab={activeTab} onTabChange={setActiveTab}>
      {activeTab === "deals" && (
        <>
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
    </Shell>
  );
}
