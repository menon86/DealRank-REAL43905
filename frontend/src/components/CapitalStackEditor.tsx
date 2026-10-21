import {
  GROUP_LABELS,
  LAYER_OPTIONS,
  blankLayer,
  isDebtType,
  isOtherType,
  layerAmount,
  layerDisplayName,
  layerGroup,
  layerOption,
  yearOneDebtService,
} from "../lib/capitalStack";
import type { LayerForm } from "../lib/capitalStack";
import { formatMoney } from "../lib/format";
import { NumberInput } from "./NumberInput";
import type { LayerGroup, LayerType } from "../lib/types";

interface CapitalStackEditorProps {
  layers: LayerForm[];
  onChange: (layers: LayerForm[]) => void;
  /** Purchase price + closing costs: the base for "% of total cost". */
  totalCost: number;
  errors: string[];
}

const GROUP_ORDER: LayerGroup[] = ["senior", "subordinate", "equity"];

/** Senior first, then subordinate, then equity; entry order within a group. */
function bottomUp(layers: LayerForm[]): LayerForm[] {
  return GROUP_ORDER.flatMap((group) => layers.filter((l) => layerGroup(l.type) === group));
}

function percentOf(amount: number, total: number): string {
  return total > 0 ? `${((amount / total) * 100).toFixed(1)}%` : "—";
}

export function CapitalStackEditor({
  layers,
  onChange,
  totalCost,
  errors,
}: CapitalStackEditorProps) {
  function update(key: string, patch: Partial<LayerForm>) {
    onChange(layers.map((layer) => (layer.key === key ? { ...layer, ...patch } : layer)));
  }

  function changeType(layer: LayerForm, type: LayerType) {
    // Keep what the user typed, but reset the defaults that depend on type.
    const fresh = blankLayer(type);
    update(layer.key, {
      type,
      rate_type: isDebtType(type) ? layer.rate_type : "fixed",
      amortization_years: isDebtType(layer.type)
        ? layer.amortization_years
        : fresh.amortization_years,
      expanded: fresh.expanded,
    });
  }

  function addLayer() {
    const hasSenior = layers.some((l) => layerGroup(l.type) === "senior");
    const allCash = layers.some((l) => l.type === "all_cash");
    const type: LayerType = !hasSenior && !allCash ? "agency_fannie_mae" : "sponsor_gp";
    onChange([...layers, blankLayer(type)]);
  }

  function remove(key: string) {
    onChange(layers.filter((layer) => layer.key !== key));
  }

  // --- Live summary ---
  const debtLayers = layers.filter((l) => isDebtType(l.type));
  const totalDebt = debtLayers.reduce((sum, l) => sum + layerAmount(l, totalCost), 0);
  const preferred = layers
    .filter((l) => l.type === "preferred_equity")
    .reduce((sum, l) => sum + layerAmount(l, totalCost), 0);
  const upfront = layers.reduce((sum, l) => {
    if (layerGroup(l.type) === "equity") return sum;
    const fee = ((Number(l.origination_fee_pct) || 0) / 100) * layerAmount(l, totalCost);
    const cap = isDebtType(l.type) && l.rate_type === "floating" ? Number(l.rate_cap_cost) || 0 : 0;
    return sum + fee + cap;
  }, 0);
  const commonEquity = totalCost + upfront - totalDebt - preferred;
  const yearOneService = debtLayers.reduce((sum, l) => sum + yearOneDebtService(l, totalCost), 0);
  const seniorService = debtLayers
    .filter((l) => layerGroup(l.type) === "senior")
    .reduce((sum, l) => sum + yearOneDebtService(l, totalCost), 0);

  const barLayers = bottomUp(layers).filter((l) => layerAmount(l, totalCost) > 0);
  const barTotal = barLayers.reduce((sum, l) => sum + layerAmount(l, totalCost), 0);

  return (
    <section className="capital-stack" aria-labelledby="capital-stack-title">
      <div className="capital-stack-header">
        <h4 id="capital-stack-title">Capital stack</h4>
        <button type="button" className="import-btn" onClick={addLayer}>
          + Add layer
        </button>
      </div>
      <p className="housing-helper-note">
        One senior loan (or All cash), any subordinate layers, and at least one equity source.
        Common equity in the returns is what&apos;s left after debt and preferred equity.
      </p>

      <div className="capital-stack-body">
        <div className="capital-stack-layers">
          {layers.length === 0 && (
            <div className="empty-state">No layers yet. Add the senior loan first.</div>
          )}
          {layers.map((layer, index) => (
            <LayerRow
              key={layer.key}
              index={index}
              layer={layer}
              totalCost={totalCost}
              onUpdate={(patch) => update(layer.key, patch)}
              onTypeChange={(type) => changeType(layer, type)}
              onRemove={() => remove(layer.key)}
            />
          ))}
        </div>

        {barLayers.length > 0 && (
          <div className="stack-visual" aria-label="Capital stack, senior debt at the bottom">
            <div className="stack-bar" role="img" aria-hidden="true">
              {barLayers.map((layer, i) => (
                <div
                  key={layer.key}
                  className={`stack-seg seg-${layerGroup(layer.type)}`}
                  style={{
                    flexGrow: layerAmount(layer, totalCost) / barTotal,
                    opacity: 1 - (i % 3) * 0.18,
                  }}
                  title={`${layerDisplayName(layer.type, layer.label)}: ${formatMoney(layerAmount(layer, totalCost))}`}
                />
              ))}
            </div>
            <ul className="stack-legend">
              {[...barLayers].reverse().map((layer) => (
                <li key={layer.key}>
                  <span className={`legend-swatch seg-${layerGroup(layer.type)}`} />
                  <span className="legend-name">{layerDisplayName(layer.type, layer.label)}</span>
                  <span className="legend-amount">
                    {formatMoney(layerAmount(layer, totalCost))} ·{" "}
                    {percentOf(layerAmount(layer, totalCost), totalCost)}
                  </span>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>

      {errors.length > 0 && (
        <ul className="stack-errors" role="alert">
          {errors.map((error) => (
            <li key={error}>{error}</li>
          ))}
        </ul>
      )}

      <div className="financing-summary-card">
        <div className="financing-stat">
          <span className="stat-label">Year 1 debt service (est.)</span>
          <span className="stat-value">{formatMoney(Math.round(yearOneService))}</span>
          {seniorService !== yearOneService && (
            <span className="stat-sub">Senior: {formatMoney(Math.round(seniorService))}</span>
          )}
        </div>
        <div className="financing-stat">
          <span className="stat-label">Total debt / LTC</span>
          <span className="stat-value">
            {formatMoney(Math.round(totalDebt))}
            <span className="stat-sub"> {percentOf(totalDebt, totalCost)}</span>
          </span>
        </div>
        <div className="financing-stat">
          <span className="stat-label">Preferred equity</span>
          <span className="stat-value">{formatMoney(Math.round(preferred))}</span>
        </div>
        <div className="financing-stat">
          <span className="stat-label">Common equity required</span>
          <span className="stat-value">{formatMoney(Math.round(commonEquity))}</span>
          {upfront > 0 && (
            <span className="stat-sub">
              incl. {formatMoney(Math.round(upfront))} fees &amp; caps
            </span>
          )}
        </div>
      </div>
      <p className="methodology-note capital-stack-note">
        Financing affects levered returns and DSCR only. Rankings use unlevered IRR.
      </p>
    </section>
  );
}

interface LayerRowProps {
  index: number;
  layer: LayerForm;
  totalCost: number;
  onUpdate: (patch: Partial<LayerForm>) => void;
  onTypeChange: (type: LayerType) => void;
  onRemove: () => void;
}

function LayerRow({ index, layer, totalCost, onUpdate, onTypeChange, onRemove }: LayerRowProps) {
  const group = layerGroup(layer.type);
  const debt = isDebtType(layer.type);
  const preferred = layer.type === "preferred_equity";
  const hasTerms = debt || preferred;
  const other = isOtherType(layer.type);
  const showLabel = other || group === "equity";
  const id = (field: string) => `${layer.key}-${field}`;
  const amount = layerAmount(layer, totalCost);

  return (
    <div className={`stack-layer group-${group}`}>
      <div className="stack-layer-main">
        <div className="field">
          <label htmlFor={id("type")}>Layer {index + 1}</label>
          <select
            id={id("type")}
            value={layer.type}
            onChange={(e) => onTypeChange(e.target.value as LayerType)}
          >
            {GROUP_ORDER.map((g) => (
              <optgroup key={g} label={GROUP_LABELS[g]}>
                {LAYER_OPTIONS.filter((o) => o.group === g).map((o) => (
                  <option key={o.type} value={o.type}>
                    {o.label}
                  </option>
                ))}
              </optgroup>
            ))}
          </select>
        </div>

        {showLabel && (
          <div className="field">
            <label htmlFor={id("label")}>{other ? "Name (required)" : "Name (optional)"}</label>
            <input
              id={id("label")}
              value={layer.label}
              maxLength={100}
              placeholder={other ? "e.g. Family office loan" : "e.g. Fund II"}
              aria-invalid={other && layer.label.trim() === ""}
              onChange={(e) => onUpdate({ label: e.target.value })}
            />
          </div>
        )}

        <div className="field stack-amount">
          <label htmlFor={id("amount")}>
            {layer.amountMode === "dollars" ? "Amount ($)" : "Amount (% of total cost)"}
          </label>
          <div className="amount-input">
            {layer.amountMode === "dollars" ? (
              <NumberInput
                id={id("amount")}
                value={layer.amount}
                onChange={(v) => onUpdate({ amount: v })}
              />
            ) : (
              <input
                id={id("amount")}
                type="number"
                step="0.1"
                value={layer.amountPct}
                onChange={(e) => onUpdate({ amountPct: e.target.value })}
              />
            )}
            <div className="unit-toggle" role="group" aria-label="Enter amount as">
              <button
                type="button"
                className={layer.amountMode === "dollars" ? "active" : ""}
                aria-pressed={layer.amountMode === "dollars"}
                onClick={() =>
                  onUpdate({ amountMode: "dollars", amount: String(Math.round(amount)) })
                }
              >
                $
              </button>
              <button
                type="button"
                className={layer.amountMode === "percent" ? "active" : ""}
                aria-pressed={layer.amountMode === "percent"}
                onClick={() =>
                  onUpdate({
                    amountMode: "percent",
                    amountPct: totalCost > 0 ? ((amount / totalCost) * 100).toFixed(2) : "",
                  })
                }
              >
                %
              </button>
            </div>
          </div>
          {layer.amountMode === "percent" && (
            <span className="field-hint">{formatMoney(Math.round(amount))}</span>
          )}
        </div>

        <div className="stack-layer-actions">
          {hasTerms && (
            <button
              type="button"
              className="link"
              aria-expanded={layer.expanded}
              aria-controls={id("terms")}
              onClick={() => onUpdate({ expanded: !layer.expanded })}
            >
              {layer.expanded ? "Hide terms" : "Terms"}
            </button>
          )}
          <button type="button" className="link danger" onClick={onRemove}>
            Remove
          </button>
        </div>
      </div>
      {layerOption(layer.type).note && (
        <p className="stack-layer-note">{layerOption(layer.type).note}</p>
      )}

      {hasTerms && layer.expanded && (
        <div className="field-grid stack-terms" id={id("terms")}>
          {debt && (
            <>
              <div className="field">
                <label htmlFor={id("rate_type")}>Rate type</label>
                <select
                  id={id("rate_type")}
                  value={layer.rate_type}
                  onChange={(e) =>
                    onUpdate({ rate_type: e.target.value as LayerForm["rate_type"] })
                  }
                >
                  <option value="fixed">Fixed</option>
                  <option value="floating">Floating (index + spread)</option>
                </select>
              </div>
              {layer.rate_type === "fixed" ? (
                <div className="field">
                  <label htmlFor={id("rate")}>Interest rate (%)</label>
                  <input
                    id={id("rate")}
                    type="number"
                    step="0.01"
                    value={layer.interest_rate_pct}
                    onChange={(e) => onUpdate({ interest_rate_pct: e.target.value })}
                  />
                </div>
              ) : (
                <>
                  <div className="field">
                    <label htmlFor={id("index_name")}>Index</label>
                    <input
                      id={id("index_name")}
                      value={layer.index_name}
                      maxLength={50}
                      onChange={(e) => onUpdate({ index_name: e.target.value })}
                    />
                  </div>
                  <div className="field">
                    <label htmlFor={id("index_rate")}>Index rate (%)</label>
                    <input
                      id={id("index_rate")}
                      type="number"
                      step="0.01"
                      value={layer.index_rate_pct}
                      onChange={(e) => onUpdate({ index_rate_pct: e.target.value })}
                    />
                  </div>
                  <div className="field">
                    <label htmlFor={id("spread")}>Spread (bps)</label>
                    <input
                      id={id("spread")}
                      type="number"
                      step="5"
                      value={layer.spread_bps}
                      onChange={(e) => onUpdate({ spread_bps: e.target.value })}
                    />
                  </div>
                  <div className="field">
                    <label htmlFor={id("rate_cap")}>Rate cap cost ($)</label>
                    <NumberInput
                      id={id("rate_cap")}
                      value={layer.rate_cap_cost}
                      onChange={(v) => onUpdate({ rate_cap_cost: v })}
                    />
                  </div>
                </>
              )}
              <div className="field">
                <label htmlFor={id("io")}>Interest-only period (months)</label>
                <input
                  id={id("io")}
                  type="number"
                  min="0"
                  value={layer.io_months}
                  onChange={(e) => onUpdate({ io_months: e.target.value })}
                />
              </div>
              <div className="field">
                <label htmlFor={id("amort")}>Amortization (years)</label>
                <input
                  id={id("amort")}
                  type="number"
                  placeholder="Blank = interest-only"
                  value={layer.amortization_years}
                  onChange={(e) => onUpdate({ amortization_years: e.target.value })}
                />
              </div>
              <div className="field">
                <label htmlFor={id("term")}>Term / maturity (years)</label>
                <input
                  id={id("term")}
                  type="number"
                  placeholder="Blank = past the exit"
                  value={layer.term_years}
                  onChange={(e) => onUpdate({ term_years: e.target.value })}
                />
              </div>
              <div className="field">
                <label htmlFor={id("recourse")}>Recourse</label>
                <select
                  id={id("recourse")}
                  value={layer.recourse}
                  onChange={(e) => onUpdate({ recourse: e.target.value as LayerForm["recourse"] })}
                >
                  <option value="">Not specified</option>
                  <option value="non_recourse">Non-recourse</option>
                  <option value="recourse">Recourse</option>
                </select>
              </div>
            </>
          )}
          {preferred && (
            <div className="field">
              <label htmlFor={id("pref")}>Preferred return (%/yr)</label>
              <input
                id={id("pref")}
                type="number"
                step="0.1"
                value={layer.preferred_return_pct}
                onChange={(e) => onUpdate({ preferred_return_pct: e.target.value })}
              />
            </div>
          )}
          <div className="field">
            <label htmlFor={id("fee")}>Origination fee (%)</label>
            <input
              id={id("fee")}
              type="number"
              step="0.05"
              value={layer.origination_fee_pct}
              onChange={(e) => onUpdate({ origination_fee_pct: e.target.value })}
            />
          </div>
          {debt && layer.term_years !== "" && (
            <p className="field-hint stack-terms-hint">
              A term shorter than the hold is repaid as a balloon at maturity, out of that
              year&apos;s cash flow (no refinancing is modeled).
            </p>
          )}
        </div>
      )}
    </div>
  );
}
