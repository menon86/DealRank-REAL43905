import { useEffect, useMemo, useState } from "react";
import { ComparisonTable } from "./components/ComparisonTable";
import { DealForm } from "./components/DealForm";
import { DealList } from "./components/DealList";
import { RankingView } from "./components/RankingView";
import { Shell } from "./components/Shell";
import type { Tab } from "./components/Shell";
import * as client from "./lib/client";
import { computeMetrics } from "./lib/engine";
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

  useEffect(() => {
    client.listDeals().then((loaded) => {
      setDeals(loaded);
      setSelectedIds(loaded.slice(0, 3).map((d) => d.id));
    });
  }, []);

  useEffect(() => {
    if (selectedIds.length === 0) {
      setRankedDeals([]);
      return;
    }
    client.rank(selectedIds, hurdleRate).then(setRankedDeals);
  }, [selectedIds, hurdleRate, deals]);

  const selectedDeals = useMemo(
    () =>
      selectedIds
        .map((id) => deals.find((d) => d.id === id))
        .filter((d): d is DealOut => Boolean(d)),
    [selectedIds, deals],
  );

  const metricsByDealId = useMemo(() => {
    const entries: Record<string, MetricsOut> = {};
    for (const deal of selectedDeals) {
      entries[deal.id] = computeMetrics(deal);
    }
    return entries;
  }, [selectedDeals]);

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
        <ComparisonTable deals={selectedDeals} metricsByDealId={metricsByDealId} />
      )}

      {activeTab === "rank" && (
        <RankingView
          selectedDealIds={selectedIds}
          hurdleRate={hurdleRate}
          onHurdleRateChange={setHurdleRate}
          rankedDeals={rankedDeals}
        />
      )}
    </Shell>
  );
}
