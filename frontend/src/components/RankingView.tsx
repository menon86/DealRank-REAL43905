import { useEffect, useRef, useState } from "react";
import { fractionToPercentInput, formatPercent, percentInputToFraction } from "../lib/format";
import type { RankedDealOut } from "../lib/types";
import { ReportDownloads } from "./ReportDownloads";

interface RankingViewProps {
  selectedDealIds: string[];
  hurdleRate: number;
  onHurdleRateChange: (rate: number) => void;
  rankedDeals: RankedDealOut[];
  loading: boolean;
  error: string | null;
  onRetry: () => void;
}

/** The API sends a non-converging deal's spread as -Infinity so it sorts last. */
function formatSpread(spread: number): string {
  if (!Number.isFinite(spread)) return "n/a — IRR didn't converge";
  return `${spread >= 0 ? "+" : ""}${formatPercent(spread)}`;
}

/**
 * The hurdle this row was actually ranked against (IRR − spread), rather
 * than the live input, so the row's arithmetic stays consistent while a
 * re-rank for a newly typed hurdle is still in flight.
 */
function hurdleUsed(entry: RankedDealOut): number | null {
  const irr = entry.metrics.unlevered_irr;
  if (irr === null || !Number.isFinite(entry.spread)) return null;
  return irr - entry.spread;
}

const HURDLE_LIMIT_PCT = 100;

/** Why a typed hurdle (in %) can't be used, or null when it can. */
function hurdleInputError(value: string): string | null {
  if (value.trim() === "") return "Enter a hurdle rate.";
  const parsed = Number.parseFloat(value);
  if (!Number.isFinite(parsed)) return "Enter the hurdle as a number, e.g. 8.";
  if (Math.abs(parsed) > HURDLE_LIMIT_PCT) {
    return `Enter a hurdle between −${HURDLE_LIMIT_PCT}% and ${HURDLE_LIMIT_PCT}%.`;
  }
  return null;
}

export function RankingView({
  selectedDealIds,
  hurdleRate,
  onHurdleRateChange,
  rankedDeals,
  loading,
  error,
  onRetry,
}: RankingViewProps) {
  const [hurdleInput, setHurdleInput] = useState(fractionToPercentInput(hurdleRate));
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  /** A typed hurdle not yet sent (waiting on the debounce). */
  const pendingRef = useRef<number | null>(null);
  const onChangeRef = useRef(onHurdleRateChange);
  onChangeRef.current = onHurdleRateChange;

  // Only resync the text box when the rate changed from outside what the
  // user is typing, so partial input like "7." or an empty box isn't rewritten.
  useEffect(() => {
    setHurdleInput((current) =>
      current.trim() !== "" && percentInputToFraction(current) === hurdleRate
        ? current
        : fractionToPercentInput(hurdleRate),
    );
  }, [hurdleRate]);

  /** Sends a pending hurdle now instead of waiting for the debounce. */
  function flushHurdle() {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = null;
    const pending = pendingRef.current;
    pendingRef.current = null;
    if (pending !== null) onChangeRef.current(pending);
  }

  // Leaving the tab mid-debounce still applies what was typed.
  useEffect(
    () => () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
      if (pendingRef.current !== null) onChangeRef.current(pendingRef.current);
    },
    [],
  );

  const hurdleError = hurdleInputError(hurdleInput);

  // Re-rank once typing pauses, and never for a blank/invalid box.
  function commitHurdle(value: string) {
    setHurdleInput(value);
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = null;
    pendingRef.current = null;
    if (hurdleInputError(value) !== null) return;
    pendingRef.current = percentInputToFraction(value);
    debounceRef.current = setTimeout(flushHurdle, 300);
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
      <div className="card-header">
        <div>
          <h2>Ranking</h2>
          <p className="card-subtitle">
            Ranked by <strong>unlevered IRR</strong> minus a{" "}
            <strong>{formatPercent(hurdleRate)}</strong> hurdle
          </p>
        </div>
        <ReportDownloads dealIds={selectedDealIds} hurdleRate={hurdleRate} />
      </div>

      {selectedDealIds.length < 3 && (
        <div className="status-banner info" role="status">
          The v1 ranking covers 3–5 deals. Select {3 - selectedDealIds.length} more on the Deals
          tab.
        </div>
      )}

      <section className="methodology-panel" aria-labelledby="ranking-methodology-title">
        <h3 id="ranking-methodology-title">How this ranking works</h3>
        <dl>
          <div>
            <dt>Ranking basis</dt>
            <dd>
              <strong>Unlevered IRR</strong> — the property-level return with no debt: full purchase
              price plus closing costs out, NOI less replacement reserves in each year, and exit
              value less selling costs at the sale, before any loan payoff.
            </dd>
          </div>
          <div>
            <dt>Rank score</dt>
            <dd>
              <code>Unlevered IRR − hurdle rate</code>, highest first. A deal whose IRR doesn&apos;t
              converge sorts last rather than disappearing.
            </dd>
          </div>
          <div>
            <dt>Hurdle</dt>
            <dd>
              One flat rate you enter below, applied to every deal regardless of sub-asset class.
            </dd>
          </div>
          <div>
            <dt>Why not levered IRR?</dt>
            <dd>
              Levered IRR depends on how much debt a deal carries. Ranking on it would let a deal
              win by borrowing more rather than by being a better asset, so it&apos;s shown for
              reference only and never sorted on.
            </dd>
          </div>
          <div>
            <dt>Risk-adjusted alternative</dt>
            <dd>
              The Risk-adjusted tab replaces this flat hurdle with a sub-class-specific one (10-Year
              Treasury + cap-rate spread + stabilized NOI growth) and a DSCR gate. The PDF and PPTX
              exports use the flat hurdle shown here.
            </dd>
          </div>
        </dl>
      </section>

      <div className="hurdle-input">
        <label htmlFor="hurdle-rate">Hurdle rate (%)</label>
        <input
          id="hurdle-rate"
          type="number"
          step="0.1"
          min={-HURDLE_LIMIT_PCT}
          max={HURDLE_LIMIT_PCT}
          value={hurdleInput}
          aria-invalid={hurdleError !== null}
          aria-describedby={hurdleError ? "hurdle-rate-error" : undefined}
          onChange={(e) => commitHurdle(e.target.value)}
          onBlur={flushHurdle}
        />
        {hurdleError && (
          <span id="hurdle-rate-error" className="field-error-text" role="alert">
            {hurdleError} Still ranking at {formatPercent(hurdleRate)}.
          </span>
        )}
        {loading && !error && (
          <span className="inline-status" role="status">
            <span className="spinner" aria-hidden="true" /> Re-ranking…
          </span>
        )}
      </div>

      {error && (
        <div className="status-banner error" role="alert">
          Couldn&apos;t rank the selected deals. {error}
          <button type="button" className="link" onClick={onRetry}>
            Retry
          </button>
        </div>
      )}

      {rankedDeals.length === 0 && loading && !error ? (
        <div className="status-banner loading" role="status">
          <span className="spinner" aria-hidden="true" /> Ranking deals…
        </div>
      ) : (
        <div className="table-scroll">
          <table
            className={`data-table ranking-table${loading ? " is-stale" : ""}`}
            aria-busy={loading}
          >
            <thead>
              <tr>
                <th scope="col">Rank</th>
                <th scope="col" className="deal-col">
                  Deal
                </th>
                <th scope="col" className="col-ranking-basis">
                  Unlevered IRR
                  <span className="row-tag tag-ranking-basis">Ranking basis</span>
                </th>
                <th scope="col">Hurdle</th>
                <th scope="col" className="col-ranking-basis">
                  Spread vs. hurdle
                </th>
                <th scope="col" className="col-reference">
                  Levered IRR
                  <span className="row-tag tag-reference">Reference only</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {rankedDeals.map((entry) => (
                <tr key={entry.deal.id} className={entry.rank === 1 ? "rank-1" : undefined}>
                  <td className="rank-cell">#{entry.rank}</td>
                  <td className="deal-cell">{entry.deal.name}</td>
                  <td className="col-ranking-basis">
                    {formatPercent(entry.metrics.unlevered_irr)}
                  </td>
                  <td>{formatPercent(hurdleUsed(entry))}</td>
                  <td
                    className={`col-ranking-basis ${entry.spread >= 0 ? "positive" : "negative"}`}
                  >
                    {formatSpread(entry.spread)}
                  </td>
                  <td className="col-reference">{formatPercent(entry.metrics.levered_irr)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
