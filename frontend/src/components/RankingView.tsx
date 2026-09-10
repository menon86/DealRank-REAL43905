import { useEffect, useState } from "react";
import { fractionToPercentInput, formatPercent, percentInputToFraction } from "../lib/format";
import type { RankedDealOut } from "../lib/types";

interface RankingViewProps {
  selectedDealIds: string[];
  hurdleRate: number;
  onHurdleRateChange: (rate: number) => void;
  rankedDeals: RankedDealOut[];
}

export function RankingView({
  selectedDealIds,
  hurdleRate,
  onHurdleRateChange,
  rankedDeals,
}: RankingViewProps) {
  const [hurdleInput, setHurdleInput] = useState(fractionToPercentInput(hurdleRate));

  useEffect(() => {
    setHurdleInput(fractionToPercentInput(hurdleRate));
  }, [hurdleRate]);

  function commitHurdle(value: string) {
    setHurdleInput(value);
    onHurdleRateChange(percentInputToFraction(value));
  }

  if (selectedDealIds.length === 0) {
    return (
      <div className="card">
        <h2>Ranking</h2>
        <div className="empty-state">Select 3–5 deals on the Deals tab to rank them.</div>
      </div>
    );
  }

  return (
    <div className="card">
      <h2>Ranking</h2>

      <div className="hurdle-input">
        <label htmlFor="hurdle-rate">Hurdle rate (%)</label>
        <input
          id="hurdle-rate"
          type="number"
          step="0.1"
          value={hurdleInput}
          onChange={(e) => commitHurdle(e.target.value)}
        />
      </div>

      <table className="data-table">
        <thead>
          <tr>
            <th>Rank</th>
            <th>Deal</th>
            <th>Unlevered IRR</th>
            <th>Levered IRR</th>
            <th>Spread vs. hurdle</th>
          </tr>
        </thead>
        <tbody>
          {rankedDeals.map((entry) => (
            <tr key={entry.deal.id} className={entry.rank === 1 ? "rank-1" : undefined}>
              <td>#{entry.rank}</td>
              <td>{entry.deal.name}</td>
              <td>{formatPercent(entry.metrics.unlevered_irr)}</td>
              <td>{formatPercent(entry.metrics.levered_irr)}</td>
              <td className={entry.spread >= 0 ? "positive" : "negative"}>
                {entry.spread >= 0 ? "+" : ""}
                {formatPercent(entry.spread)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      <p className="methodology-note">
        Ranked by unlevered IRR minus your hurdle rate, descending. Levered IRR is shown for
        reference only and is never sorted on. This is Deliverable 2&apos;s flat, user-entered
        hurdle — a risk-adjusted, sub-class-specific hurdle is Deliverable 3&apos;s successor to
        this view (see <code>app/engine/ranking.py</code>).
      </p>
    </div>
  );
}
