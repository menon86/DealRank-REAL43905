import { useEffect, useRef, useState } from "react";
import type { RankingSettings } from "./ChatPanel";
import { ReportDownloads } from "./ReportDownloads";
import * as client from "../lib/client";
import { formatMultiple, formatPercent, percentInputToFraction } from "../lib/format";
import type { PrimaryGoal, Questionnaire, RiskRankResponse, Weights } from "../lib/types";
import { SUB_ASSET_CLASS_LABELS } from "../lib/types";

interface RiskRankingViewProps {
  selectedDealIds: string[];
  // Reports the active settings so the chat assistant can default to them.
  onSettingsChange?: (settings: RankingSettings) => void;
}

type PreferenceMode = "none" | "questionnaire" | "manual";

const GOALS: { id: PrimaryGoal; label: string }[] = [
  { id: "total_return", label: "Maximize total return (IRR)" },
  { id: "cash_flow", label: "Steady cash flow now" },
  { id: "preservation", label: "Protect capital / low risk" },
];

const TOLERANCE_LABELS = ["Very low", "Low", "Moderate", "High", "Very high"];
const NEED_LABELS = ["Irrelevant", "Nice to have", "Important", "Very important", "Essential"];

const SOURCE_LABELS: Record<string, string> = {
  fred: "live, FRED DGS10",
  treasury: "live, US Treasury par yield curve",
  fallback: "FALLBACK default — live lookup failed",
  override: "manual override",
};

function signed(fraction: number): string {
  return `${fraction >= 0 ? "+" : ""}${formatPercent(fraction)}`;
}

export function RiskRankingView({ selectedDealIds, onSettingsChange }: RiskRankingViewProps) {
  const [dscrInput, setDscrInput] = useState("1.25");
  const [treasuryInput, setTreasuryInput] = useState("");
  const [mode, setMode] = useState<PreferenceMode>("none");
  const [answers, setAnswers] = useState<Questionnaire>({
    primary_goal: "total_return",
    risk_tolerance: 3,
    income_need: 3,
  });
  const [manual, setManual] = useState({ irr: "50", cash_flow: "25", risk: "25" });
  const [result, setResult] = useState<RiskRankResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);
  // Only the latest request may update state; an older response (or one
  // superseded by inputs turning invalid) is dropped.
  const requestIdRef = useRef(0);

  const dscrMinimum = Number.parseFloat(dscrInput);
  const treasuryOverride =
    treasuryInput.trim() === "" ? null : percentInputToFraction(treasuryInput);
  const manualWeights: Weights = {
    irr: Math.max(0, Number.parseFloat(manual.irr) || 0),
    cash_flow: Math.max(0, Number.parseFloat(manual.cash_flow) || 0),
    risk: Math.max(0, Number.parseFloat(manual.risk) || 0),
  };
  const manualInvalid =
    mode === "manual" && manualWeights.irr + manualWeights.cash_flow + manualWeights.risk <= 0;
  const dscrInvalid = !Number.isFinite(dscrMinimum) || dscrMinimum < 0;
  const inputsInvalid = dscrInvalid || manualInvalid;

  useEffect(() => {
    const requestId = ++requestIdRef.current;
    if (selectedDealIds.length === 0 || inputsInvalid) {
      setResult(null);
      setLoading(false);
      setError(null);
      return;
    }
    const isCurrent = () => requestId === requestIdRef.current;
    setLoading(true);
    setError(null);
    client
      .rankRiskAdjusted({
        deal_ids: selectedDealIds,
        dscr_minimum: dscrMinimum,
        treasury_yield: treasuryOverride,
        weights: mode === "manual" ? manualWeights : null,
        answers: mode === "questionnaire" ? answers : null,
      })
      .then((r) => {
        if (!isCurrent()) return;
        setResult(r);
        setLoading(false);
      })
      .catch((err) => {
        if (!isCurrent()) return;
        setError(client.describeError(err));
        setLoading(false);
      });
    // manualWeights is derived from `manual`; depending on the strings avoids a new object each render.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [
    selectedDealIds,
    dscrMinimum,
    treasuryOverride,
    mode,
    answers,
    manual,
    reloadKey,
    inputsInvalid,
  ]);

  // The effective weights come from the response, so questionnaire answers are reflected too.
  const effectiveWeights = result?.weights;
  const effectiveDscr = dscrMinimum;
  const effectiveTreasury = treasuryOverride;
  useEffect(() => {
    if (!onSettingsChange) return;
    const settings: RankingSettings = {};
    if (Number.isFinite(effectiveDscr) && effectiveDscr >= 0) settings.dscr_minimum = effectiveDscr;
    if (effectiveTreasury !== null && Number.isFinite(effectiveTreasury)) {
      settings.treasury_yield = effectiveTreasury;
    }
    if (effectiveWeights) settings.weights = effectiveWeights;
    onSettingsChange(settings);
  }, [onSettingsChange, effectiveDscr, effectiveTreasury, effectiveWeights]);

  if (selectedDealIds.length === 0) {
    return (
      <div className="card">
        <h2>Risk-adjusted ranking</h2>
        <div className="empty-state">Select deals on the Deals tab to rank them.</div>
      </div>
    );
  }

  const weights = result?.weights;
  return (
    <div className="card">
      <div className="card-header">
        <div>
          <h2>Risk-adjusted ranking</h2>
          <p className="card-subtitle">
            Each deal is measured against <strong>its own sub-class hurdle</strong>, so garden,
            mid-rise and student housing compare on one scale.
          </p>
        </div>
        <ReportDownloads
          dealIds={selectedDealIds}
          risk={{
            dscrMinimum: Number.isFinite(dscrMinimum) ? dscrMinimum : 1.25,
            treasuryYield: treasuryOverride,
            weights: mode === "manual" ? manualWeights : null,
            answers: mode === "questionnaire" ? answers : null,
          }}
        />
      </div>

      <section className="methodology-panel">
        <h3>How this ranking works</h3>
        <dl>
          <div>
            <dt>Hurdle</dt>
            <dd>
              <code>10-yr Treasury + sub-class cap-rate spread + stabilized NOI growth</code> — an
              expected unlevered total return for that kind of asset.
            </dd>
          </div>
          <div>
            <dt>Gate</dt>
            <dd>
              Deals with lowest DSCR over the hold below the minimum are <strong>excluded</strong>,
              not penalized.
            </dd>
          </div>
          <div>
            <dt>Score</dt>
            <dd>
              <code>Unlevered IRR (before closing and selling costs) − hurdle</code>. With
              preferences set, three factors are each scaled 0–1 against{" "}
              <strong>fixed anchors</strong> and blended by your weights: return = spread (−3% to
              +5%); cash flow = unlevered year-one cash yield, NOI ÷ (price + closing costs) (3% to
              8%); safety = the mean of lowest DSCR over the hold (1.0x to 2.0x) and equity share
              (20% to 60%). Because the anchors are fixed, a deal&apos;s score doesn&apos;t depend
              on which other deals are selected. Levered IRR is never ranked on.
            </dd>
          </div>
        </dl>
      </section>

      <div className="control-grid">
        <div className="field">
          <label htmlFor="dscr-min">DSCR minimum (x)</label>
          <input
            id="dscr-min"
            type="number"
            step="0.05"
            min="0"
            value={dscrInput}
            aria-invalid={dscrInvalid}
            aria-describedby={dscrInvalid ? "dscr-min-error" : undefined}
            onChange={(e) => setDscrInput(e.target.value)}
          />
          {dscrInvalid && (
            <p id="dscr-min-error" className="field-error-text" role="alert">
              Enter a DSCR minimum of 0 or more (for example 1.25) to rank.
            </p>
          )}
        </div>
        <div className="field">
          <label htmlFor="treasury-override">10-yr Treasury override (%)</label>
          <input
            id="treasury-override"
            type="number"
            step="0.05"
            placeholder="blank = live"
            value={treasuryInput}
            onChange={(e) => setTreasuryInput(e.target.value)}
          />
        </div>
        <div className="field">
          <span className="field-label">Preferences</span>
          <div className="segmented" role="group" aria-label="Preference mode">
            {(
              [
                ["none", "Return only"],
                ["questionnaire", "Questionnaire"],
                ["manual", "Set weights"],
              ] as [PreferenceMode, string][]
            ).map(([id, label]) => (
              <button
                key={id}
                type="button"
                className={mode === id ? "active" : ""}
                onClick={() => setMode(id)}
              >
                {label}
              </button>
            ))}
          </div>
        </div>
      </div>

      {mode === "questionnaire" && (
        <fieldset className="questionnaire">
          <legend>Tell us what matters</legend>
          <div className="field">
            <label htmlFor="q-goal">1. What is your primary goal?</label>
            <select
              id="q-goal"
              value={answers.primary_goal}
              onChange={(e) =>
                setAnswers({ ...answers, primary_goal: e.target.value as PrimaryGoal })
              }
            >
              {GOALS.map((g) => (
                <option key={g.id} value={g.id}>
                  {g.label}
                </option>
              ))}
            </select>
          </div>
          <div className="field">
            <label htmlFor="q-risk">
              2. Risk tolerance: <strong>{TOLERANCE_LABELS[answers.risk_tolerance - 1]}</strong>
            </label>
            <input
              id="q-risk"
              type="range"
              min={1}
              max={5}
              step={1}
              value={answers.risk_tolerance}
              onChange={(e) => setAnswers({ ...answers, risk_tolerance: Number(e.target.value) })}
            />
          </div>
          <div className="field">
            <label htmlFor="q-income">
              3. How much do you need current cash flow?{" "}
              <strong>{NEED_LABELS[answers.income_need - 1]}</strong>
            </label>
            <input
              id="q-income"
              type="range"
              min={1}
              max={5}
              step={1}
              value={answers.income_need}
              onChange={(e) => setAnswers({ ...answers, income_need: Number(e.target.value) })}
            />
          </div>
        </fieldset>
      )}

      {mode === "manual" && (
        <fieldset className="questionnaire">
          <legend>Relative importance (any scale — normalized)</legend>
          {(
            [
              ["irr", "Return (IRR vs. hurdle)"],
              ["cash_flow", "Cash flow (unlevered year-one cash yield)"],
              ["risk", "Safety (DSCR, low leverage)"],
            ] as [keyof typeof manual, string][]
          ).map(([key, label]) => (
            <div className="field" key={key}>
              <label htmlFor={`w-${key}`}>{label}</label>
              <input
                id={`w-${key}`}
                type="number"
                min="0"
                step="5"
                value={manual[key]}
                onChange={(e) => setManual({ ...manual, [key]: e.target.value })}
              />
            </div>
          ))}
          {manualInvalid && (
            <p className="field-error-text">At least one weight must be above 0.</p>
          )}
        </fieldset>
      )}

      {result && (
        <p className="provenance-line">
          10-yr Treasury {formatPercent(result.treasury.yield)} (
          {SOURCE_LABELS[result.treasury.source] ?? result.treasury.source}
          {result.treasury.as_of ? `, ${result.treasury.as_of}` : ""}).
          {weights && mode !== "none" && (
            <>
              {" "}
              Weights — return {formatPercent(weights.irr, 0)}, cash flow{" "}
              {formatPercent(weights.cash_flow, 0)}, safety {formatPercent(weights.risk, 0)}.
            </>
          )}
        </p>
      )}
      {result?.treasury.source === "fallback" && (
        <div className="status-banner info" role="status">
          Couldn&apos;t reach FRED or the US Treasury, so the hurdle uses a configured default
          Treasury yield. Enter an override above to use today&apos;s figure.
        </div>
      )}

      {loading && (
        <span className="inline-status" role="status">
          <span className="spinner" aria-hidden="true" /> Ranking…
        </span>
      )}
      {error && (
        <div className="status-banner error" role="alert">
          Couldn&apos;t rank the selected deals. {error}
          <button type="button" className="link" onClick={() => setReloadKey((k) => k + 1)}>
            Retry
          </button>
        </div>
      )}

      {result && (
        <>
          <div className="table-scroll">
            <table className={`data-table ranking-table${loading ? " is-stale" : ""}`}>
              <thead>
                <tr>
                  <th scope="col">Rank</th>
                  <th scope="col" className="deal-col">
                    Deal
                  </th>
                  <th scope="col" className="col-ranking-basis">
                    Unlevered IRR (before costs)
                  </th>
                  <th scope="col">Hurdle</th>
                  <th scope="col" className="col-ranking-basis">
                    Spread
                  </th>
                  <th scope="col">Lowest DSCR</th>
                  <th scope="col">Year-1 cash yield</th>
                  {mode !== "none" && <th scope="col">Score (0–100)</th>}
                  <th scope="col" className="col-reference">
                    Levered IRR
                    <span className="row-tag tag-reference">Reference only</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {result.ranked.map((r) => (
                  <tr key={r.deal.id} className={r.rank === 1 ? "rank-1" : undefined}>
                    <td className="rank-cell">#{r.rank}</td>
                    <td className="deal-cell">
                      {r.deal.name}
                      <div className="sub-class">
                        {SUB_ASSET_CLASS_LABELS[r.deal.sub_asset_class]}
                      </div>
                      {r.warnings.map((w) => (
                        <div key={w} className="sub-class" role="note">
                          ⚠ {w}
                        </div>
                      ))}
                    </td>
                    <td className="col-ranking-basis">
                      {formatPercent(r.metrics.unlevered_irr_before_costs)}
                    </td>
                    <td
                      title={`${formatPercent(r.hurdle.treasury_yield)} Treasury + ${formatPercent(
                        r.hurdle.spread_bps / 10000,
                      )} spread + ${formatPercent(r.hurdle.noi_growth)} NOI growth (${
                        r.hurdle.survey_quarter
                      })`}
                    >
                      {formatPercent(r.hurdle.total)}
                    </td>
                    <td className={`col-ranking-basis ${r.spread >= 0 ? "positive" : "negative"}`}>
                      {signed(r.spread)}
                    </td>
                    <td
                      title={
                        r.metrics.min_dscr === null
                          ? undefined
                          : `Lowest combined DSCR over the hold (the gate); year 1: ${formatMultiple(r.metrics.year_one_dscr)}`
                      }
                    >
                      {r.metrics.min_dscr === null
                        ? "n/a (no debt)"
                        : formatMultiple(r.metrics.min_dscr)}
                    </td>
                    <td>{formatPercent(r.metrics.unlevered_cash_yield)}</td>
                    {mode !== "none" && (
                      <td
                        title={`return ${r.factors.irr.toFixed(2)} · cash flow ${r.factors.cash_flow.toFixed(2)} · safety ${r.factors.risk.toFixed(2)}`}
                      >
                        {(r.score * 100).toFixed(0)}
                      </td>
                    )}
                    <td className="col-reference">{formatPercent(r.metrics.levered_irr)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {result.ranked.length === 0 && (
            <div className="empty-state">
              <p>Every selected deal was excluded (see below).</p>
            </div>
          )}
          <p className="hurdle-hint">
            Hover a hurdle or score for its breakdown, or a DSCR for its year-one value. Lowest DSCR
            is the minimum over the hold, which is what the gate tests. Each factor is scored
            against fixed anchors, so adding or removing other deals doesn&apos;t change a
            deal&apos;s score.
          </p>

          {result.excluded.length > 0 && (
            <section className="excluded-panel" aria-label="Excluded deals">
              <h3>Excluded from ranking ({result.excluded.length})</h3>
              <ul>
                {result.excluded.map((e) => (
                  <li key={e.deal.id}>
                    <strong>{e.deal.name}</strong> — {e.reason}
                    {e.spread !== null
                      ? ` Its spread vs. hurdle is ${formatPercent(e.spread)} (shown for reference; it is not ranked).`
                      : ""}
                  </li>
                ))}
              </ul>
            </section>
          )}
        </>
      )}
    </div>
  );
}
