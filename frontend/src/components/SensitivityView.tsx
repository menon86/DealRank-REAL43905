import { useEffect, useMemo, useState } from "react";
import * as client from "../lib/client";
import { formatMoney, formatMultiple, formatPercent } from "../lib/format";
import type {
  DealOut,
  MonteCarloResponse,
  SweepPoint,
  SweepResponse,
  SweepVariable,
} from "../lib/types";

interface SensitivityViewProps {
  deals: DealOut[];
}

const VARIABLES: { id: SweepVariable; label: string }[] = [
  { id: "exit_cap_rate", label: "Exit cap rate" },
  { id: "rent_growth_rate", label: "Annual rent growth" },
];

function baseIndex(sweep: SweepResponse): number {
  let best = 0;
  sweep.points.forEach((p, i) => {
    if (
      Math.abs(p.value - sweep.base_value) < Math.abs(sweep.points[best].value - sweep.base_value)
    )
      best = i;
  });
  return best;
}

function IrrLine({ points, index }: { points: SweepPoint[]; index: number }) {
  // Non-converging points are skipped, not plotted as 0%.
  const known = points
    .map((p, i) => ({ i, v: p.unlevered_irr }))
    .filter((p): p is { i: number; v: number } => p.v !== null);
  if (known.length === 0) return null;
  const irrs = known.map((p) => p.v);
  const lo = Math.min(...irrs);
  const hi = Math.max(...irrs);
  const span = hi - lo || 1;
  const x = (i: number) => 8 + (i / (points.length - 1)) * 304;
  const y = (v: number) => 52 - ((v - lo) / span) * 44;
  const current = points[index].unlevered_irr;
  return (
    <svg
      viewBox="0 0 320 60"
      className="sens-chart"
      role="img"
      aria-label="Unlevered IRR across the range"
    >
      <polyline
        fill="none"
        stroke="var(--color-primary)"
        strokeWidth="2"
        points={known.map((p) => `${x(p.i)},${y(p.v)}`).join(" ")}
      />
      {current !== null && (
        <circle cx={x(index)} cy={y(current)} r="5" fill="var(--color-primary)" />
      )}
    </svg>
  );
}

function SweepSlider({ sweep, variable }: { sweep: SweepResponse; variable: SweepVariable }) {
  const base = useMemo(() => baseIndex(sweep), [sweep]);
  const [index, setIndex] = useState(base);
  useEffect(() => setIndex(base), [base]);

  const point = sweep.points[index];
  const basePoint = sweep.points[base];
  const label = VARIABLES.find((v) => v.id === variable)?.label ?? variable;
  const delta =
    point.unlevered_irr !== null && basePoint.unlevered_irr !== null
      ? point.unlevered_irr - basePoint.unlevered_irr
      : null;

  return (
    <div className="sens-block">
      <label htmlFor={`slider-${variable}`}>
        {label}: <strong>{formatPercent(point.value)}</strong>
        {index === base && <span className="row-tag tag-reference">Base case</span>}
      </label>
      <input
        id={`slider-${variable}`}
        type="range"
        min={0}
        max={sweep.points.length - 1}
        step={1}
        value={index}
        onChange={(e) => setIndex(Number(e.target.value))}
      />
      <div className="sens-range">
        <span>{formatPercent(sweep.points[0].value)}</span>
        <button type="button" className="link" onClick={() => setIndex(base)}>
          Reset to {formatPercent(sweep.base_value)}
        </button>
        <span>{formatPercent(sweep.points[sweep.points.length - 1].value)}</span>
      </div>
      <IrrLine points={sweep.points} index={index} />
      <dl className="sens-readout">
        <div>
          <dt>Unlevered IRR</dt>
          <dd>
            {formatPercent(point.unlevered_irr)}
            {delta !== null && index !== base && (
              <span className={delta >= 0 ? "positive" : "negative"}>
                {" "}
                ({delta >= 0 ? "+" : ""}
                {(delta * 100).toFixed(2)} pts)
              </span>
            )}
          </dd>
        </div>
        <div>
          <dt>Levered IRR</dt>
          <dd>{formatPercent(point.levered_irr)}</dd>
        </div>
        <div>
          <dt>Equity multiple</dt>
          <dd>{formatMultiple(point.equity_multiple)}</dd>
        </div>
        <div>
          <dt>Year-one cash-on-cash</dt>
          <dd>{formatPercent(point.cash_on_cash)}</dd>
        </div>
        <div>
          <dt>Lowest DSCR over hold</dt>
          <dd>{formatMultiple(point.min_dscr)}</dd>
        </div>
        <div>
          <dt>Exit value</dt>
          <dd>{formatMoney(point.exit_value)}</dd>
        </div>
      </dl>
    </div>
  );
}

function Histogram({ result }: { result: MonteCarloResponse }) {
  const bins = result.unlevered_histogram;
  const max = Math.max(...bins.map((b) => b.count), 1);
  const hurdle = result.hurdle;
  return (
    <div className="histogram" role="img" aria-label="Distribution of unlevered IRR">
      {bins.map((b, i) => (
        <div
          key={i}
          className={`bar${hurdle !== null && b.high <= hurdle ? " below" : ""}`}
          style={{ height: `${(b.count / max) * 100}%` }}
          title={`${formatPercent(b.low)} – ${formatPercent(b.high)}: ${b.count} runs`}
        />
      ))}
    </div>
  );
}

export function SensitivityView({ deals }: SensitivityViewProps) {
  const [dealId, setDealId] = useState<string>(deals[0]?.id ?? "");
  const [sweeps, setSweeps] = useState<Partial<Record<SweepVariable, SweepResponse>>>({});
  const [sweepError, setSweepError] = useState<string | null>(null);
  const [sweepLoading, setSweepLoading] = useState(false);

  const [mc, setMc] = useState({
    simulations: "1000",
    exit_cap_bps: "50",
    rent_growth_pct: "1",
    vacancy_pct: "2",
    seed: "",
    dscr: "1.25",
  });
  const [mcResult, setMcResult] = useState<MonteCarloResponse | null>(null);
  const [mcLoading, setMcLoading] = useState(false);
  const [mcError, setMcError] = useState<string | null>(null);

  useEffect(() => {
    if (!dealId && deals.length > 0) setDealId(deals[0].id);
  }, [deals, dealId]);

  useEffect(() => {
    if (!dealId) return;
    let cancelled = false;
    setSweepLoading(true);
    setSweepError(null);
    setSweeps({});
    setMcResult(null);
    Promise.all(VARIABLES.map((v) => client.sweep(dealId, v.id)))
      .then(([cap, growth]) => {
        if (!cancelled) setSweeps({ exit_cap_rate: cap, rent_growth_rate: growth });
      })
      .catch((err) => {
        if (!cancelled) setSweepError(client.describeError(err));
      })
      .finally(() => {
        if (!cancelled) setSweepLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [dealId]);

  async function runMonteCarlo() {
    setMcLoading(true);
    setMcError(null);
    try {
      setMcResult(
        await client.monteCarlo(dealId, {
          simulations: Math.round(Number(mc.simulations)),
          seed: mc.seed.trim() === "" ? null : Math.round(Number(mc.seed)),
          exit_cap_sd: Number(mc.exit_cap_bps) / 10000,
          rent_growth_sd: Number(mc.rent_growth_pct) / 100,
          vacancy_sd: Number(mc.vacancy_pct) / 100,
          dscr_minimum: Number(mc.dscr),
        }),
      );
    } catch (err) {
      setMcError(client.describeError(err));
    } finally {
      setMcLoading(false);
    }
  }

  if (deals.length === 0) {
    return (
      <div className="card">
        <h2>Sensitivity</h2>
        <div className="empty-state">Add a deal on the Deals tab first.</div>
      </div>
    );
  }

  const dist = mcResult?.unlevered_irr;
  return (
    <>
      <div className="card">
        <div className="card-header">
          <div>
            <h2>Sensitivity sliders</h2>
            <p className="card-subtitle">
              Move one assumption at a time; everything else stays at the deal&apos;s own inputs.
            </p>
          </div>
          <div className="field">
            <label htmlFor="sens-deal">Deal</label>
            <select id="sens-deal" value={dealId} onChange={(e) => setDealId(e.target.value)}>
              {deals.map((d) => (
                <option key={d.id} value={d.id}>
                  {d.name}
                </option>
              ))}
            </select>
          </div>
        </div>
        {sweepLoading && (
          <span className="inline-status" role="status">
            <span className="spinner" aria-hidden="true" /> Running scenarios…
          </span>
        )}
        {sweepError && (
          <div className="status-banner error" role="alert">
            {sweepError}
          </div>
        )}
        <div className="sens-grid">
          {VARIABLES.map(
            (v) =>
              sweeps[v.id] && (
                <SweepSlider key={`${dealId}-${v.id}`} sweep={sweeps[v.id]!} variable={v.id} />
              ),
          )}
        </div>
      </div>

      <div className="card">
        <div className="card-header">
          <div>
            <h2>Monte Carlo</h2>
            <p className="card-subtitle">
              Draws exit cap rate, rent growth and vacancy together (independent normal draws around
              the deal&apos;s inputs) and re-runs the full model each time.
            </p>
          </div>
        </div>
        <div className="control-grid">
          {(
            [
              ["simulations", "Simulations (max 5,000)", "100"],
              ["exit_cap_bps", "Exit cap σ (bps)", "5"],
              ["rent_growth_pct", "Rent growth σ (%)", "0.25"],
              ["vacancy_pct", "Vacancy σ (%)", "0.5"],
              ["dscr", "DSCR minimum (x)", "0.05"],
              ["seed", "Seed (optional)", "1"],
            ] as [keyof typeof mc, string, string][]
          ).map(([key, label, step]) => (
            <div className="field" key={key}>
              <label htmlFor={`mc-${key}`}>{label}</label>
              <input
                id={`mc-${key}`}
                type="number"
                min="0"
                step={step}
                value={mc[key]}
                onChange={(e) => setMc({ ...mc, [key]: e.target.value })}
              />
            </div>
          ))}
        </div>
        <button
          type="button"
          className="primary"
          onClick={runMonteCarlo}
          disabled={mcLoading || !dealId}
        >
          {mcLoading ? "Running…" : "Run simulation"}
        </button>
        {mcError && (
          <div className="status-banner error" role="alert">
            {mcError}
          </div>
        )}
        {mcResult && dist && (
          <div className="mc-results">
            <dl className="sens-readout">
              <div>
                <dt>Median unlevered IRR</dt>
                <dd>{formatPercent(dist.p50)}</dd>
              </div>
              <div>
                <dt>5th – 95th percentile</dt>
                <dd>
                  {formatPercent(dist.p5)} – {formatPercent(dist.p95)}
                </dd>
              </div>
              <div>
                <dt>Std. deviation</dt>
                <dd>{formatPercent(dist.stdev)}</dd>
              </div>
              <div>
                <dt>
                  P(IRR &lt; {formatPercent(mcResult.hurdle)}{" "}
                  {mcResult.hurdle_source === "risk_adjusted" ? "risk-adj. hurdle" : "hurdle"})
                </dt>
                <dd>{formatPercent(mcResult.prob_below_hurdle, 1)}</dd>
              </div>
              <div>
                <dt>P(DSCR dips below {Number(mc.dscr).toFixed(2)}x)</dt>
                <dd>
                  {mcResult.prob_dscr_below_minimum === null
                    ? "n/a (no debt)"
                    : formatPercent(mcResult.prob_dscr_below_minimum, 1)}
                </dd>
              </div>
              <div>
                <dt>Median levered IRR</dt>
                <dd>{formatPercent(mcResult.levered_irr?.p50 ?? null)}</dd>
              </div>
            </dl>
            <Histogram result={mcResult} />
            <div className="sens-range">
              <span>{formatPercent(mcResult.unlevered_histogram[0]?.low ?? null)}</span>
              <span>Unlevered IRR (shaded = below hurdle)</span>
              <span>
                {formatPercent(
                  mcResult.unlevered_histogram[mcResult.unlevered_histogram.length - 1]?.high ??
                    null,
                )}
              </span>
            </div>
            <p className="provenance-line">
              {mcResult.converged} of {mcResult.simulations} runs produced an IRR
              {mcResult.seed !== null ? ` · seed ${mcResult.seed}` : ""}.
            </p>
          </div>
        )}
      </div>
    </>
  );
}
