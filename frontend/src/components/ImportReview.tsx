import { useMemo, useState } from "react";
import {
  UNIT_MIX_ATTRIBUTES,
  candidateValue,
  cleanImportedValue,
  describeCandidate,
  unitMixFromTable,
} from "../lib/spreadsheetImport";
import type { ImportedMixRow } from "../lib/spreadsheetImport";
import type { ImportField, ImportProposal, UnitMixAttribute } from "../lib/types";

export interface ConfirmedImport {
  /** Non-blank values only, keyed as the proposal's fields. */
  values: Record<string, string>;
  unitMix: ImportedMixRow[] | null;
}

interface ImportReviewProps {
  proposal: ImportProposal;
  onApply: (result: ConfirmedImport) => void;
  onCancel: () => void;
}

const SECTIONS: { key: ImportField["section"]; title: string }[] = [
  { key: "property", title: "Property and underwriting" },
  { key: "ancillary", title: "Ancillary income" },
  { key: "financing", title: "Financing" },
];

const TYPED = "__typed";

/**
 * The confirm-and-map step of a spreadsheet import: every value the
 * backend found, with the cell it came from, editable before anything
 * reaches the deal form. The user can retype a value, point a field at a
 * different cell, and remap the unit mix table's columns.
 */
export function ImportReview({ proposal, onApply, onCancel }: ImportReviewProps) {
  const candidates = useMemo(
    () => new Map(proposal.candidates.map((c) => [c.id, c])),
    [proposal.candidates],
  );
  const [values, setValues] = useState<Record<string, string>>(() =>
    Object.fromEntries(proposal.fields.map((f) => [f.key, f.value ?? ""])),
  );
  const [sources, setSources] = useState<Record<string, string>>(() =>
    Object.fromEntries(proposal.fields.map((f) => [f.key, f.candidate_id ?? ""])),
  );
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});
  const [mixMapping, setMixMapping] = useState<Record<UnitMixAttribute, number | null> | null>(
    proposal.unit_mix?.mapping ?? null,
  );
  const [includeMix, setIncludeMix] = useState(proposal.unit_mix !== null);

  const table = proposal.unit_mix;
  const mixRows = table && mixMapping ? unitMixFromTable(table, mixMapping) : [];
  const foundCount = proposal.fields.filter((f) => f.value !== null).length;
  const filledCount = proposal.fields.filter((f) => values[f.key].trim() !== "").length;

  function setValue(key: string, value: string) {
    setValues((prev) => ({ ...prev, [key]: value }));
    setSources((prev) => ({ ...prev, [key]: value.trim() === "" ? "" : TYPED }));
  }

  function setSource(field: ImportField, id: string) {
    setSources((prev) => ({ ...prev, [field.key]: id }));
    const candidate = candidates.get(id);
    setValues((prev) => ({
      ...prev,
      [field.key]: candidate ? candidateValue(field, candidate) : "",
    }));
  }

  function apply() {
    const kinds = new Map(proposal.fields.map((f) => [f.key, f.kind]));
    const confirmed = Object.fromEntries(
      Object.entries(values)
        .map(([k, v]) => [k, cleanImportedValue(kinds.get(k) ?? "text", v)] as const)
        .filter(([, v]) => v !== ""),
    );
    onApply({
      values: confirmed,
      unitMix: includeMix && mixRows.length > 0 ? mixRows : null,
    });
  }

  function renderRow(field: ImportField) {
    const source = sources[field.key];
    const original = proposal.fields.find((f) => f.key === field.key);
    const fromOriginal = source !== "" && source === original?.candidate_id;
    return (
      <tr key={field.key} className={values[field.key].trim() === "" ? "is-empty" : undefined}>
        <th scope="row">
          {field.label}
          {field.unit && <span className="import-review-unit">{field.unit}</span>}
        </th>
        <td>
          {field.kind === "choice" ? (
            <select
              aria-label={field.label}
              value={values[field.key]}
              onChange={(e) => setValue(field.key, e.target.value)}
            >
              <option value="">Not set</option>
              {field.choices.map((c) => (
                <option key={c.value} value={c.value}>
                  {c.label}
                </option>
              ))}
            </select>
          ) : (
            <input
              aria-label={field.label}
              inputMode={field.kind === "text" ? "text" : "decimal"}
              value={values[field.key]}
              onChange={(e) => setValue(field.key, e.target.value)}
            />
          )}
        </td>
        <td>
          <select
            aria-label={`Where ${field.label} comes from`}
            className="import-review-source"
            value={source}
            onChange={(e) => setSource(field, e.target.value)}
          >
            <option value="">Not in file</option>
            {source === TYPED && <option value={TYPED}>Typed in</option>}
            {proposal.candidates.map((c) => (
              <option key={c.id} value={c.id}>
                {describeCandidate(c)}
              </option>
            ))}
          </select>
          {fromOriginal && original?.note && (
            <span className="import-review-note">{original.note}</span>
          )}
        </td>
        <td className="import-review-flag">
          {fromOriginal && original?.confidence === "medium" && (
            <span className="import-review-badge check" title="Check this one">
              Check
            </span>
          )}
          {fromOriginal && original?.confidence === "high" && (
            <span className="import-review-badge ok" title="Label matched exactly">
              Matched
            </span>
          )}
        </td>
      </tr>
    );
  }

  return (
    <section className="import-review" aria-labelledby="import-review-title">
      <header className="import-review-header">
        <div>
          <h3 id="import-review-title">Review import from “{proposal.filename}”</h3>
          <p>
            Found {foundCount} of {proposal.fields.length} fields
            {table ? `, plus a unit mix table on ${table.sheet}` : ""}. Check each value and the
            cell it came from. Nothing changes on the form until you click Fill the form.
          </p>
        </div>
      </header>

      {proposal.warnings.map((w) => (
        <div key={w} className="import-alert error">
          <span>{w}</span>
        </div>
      ))}

      {SECTIONS.map((section) => {
        const fields = proposal.fields.filter((f) => f.section === section.key);
        const shown = fields.filter(
          (f) => expanded[section.key] || f.value !== null || values[f.key].trim() !== "",
        );
        const hidden = fields.length - shown.length;
        return (
          <div key={section.key} className="import-review-section">
            <h4>{section.title}</h4>
            {shown.length > 0 && (
              <div className="import-review-scroll">
                <table className="import-review-table">
                  <thead>
                    <tr>
                      <th>Field</th>
                      <th>Value</th>
                      <th>From</th>
                      <th aria-label="Match" />
                    </tr>
                  </thead>
                  <tbody>{shown.map(renderRow)}</tbody>
                </table>
              </div>
            )}
            {hidden > 0 && (
              <button
                type="button"
                className="import-review-more"
                onClick={() => setExpanded((prev) => ({ ...prev, [section.key]: true }))}
              >
                {shown.length === 0
                  ? `Nothing found. Map ${hidden} fields by hand`
                  : `Show ${hidden} fields not found`}
              </button>
            )}
          </div>
        );
      })}

      <div className="import-review-section">
        <h4>Unit mix</h4>
        {table && mixMapping ? (
          <>
            <label className="import-review-check">
              <input
                type="checkbox"
                checked={includeMix}
                onChange={(e) => setIncludeMix(e.target.checked)}
              />
              Import {table.rows.length} rows from {table.sheet}, starting row{" "}
              {table.header_row + 1}. This replaces the form&apos;s unit mix and sets units and
              average rent from it.
            </label>
            {includeMix && (
              <>
                <div className="import-review-mapping">
                  {UNIT_MIX_ATTRIBUTES.map((attr) => (
                    <label key={attr.key}>
                      <span>{attr.label}</span>
                      <select
                        value={mixMapping[attr.key] ?? ""}
                        onChange={(e) =>
                          setMixMapping({
                            ...mixMapping,
                            [attr.key]: e.target.value === "" ? null : Number(e.target.value),
                          })
                        }
                      >
                        <option value="">
                          {attr.key === "bedsPerUnit" ? "Guess from unit type" : "None"}
                        </option>
                        {table.columns.map((col) => (
                          <option key={col.index} value={col.index}>
                            Column {col.letter}
                            {col.header ? `: ${col.header}` : ""}
                          </option>
                        ))}
                      </select>
                    </label>
                  ))}
                </div>
                <div className="import-review-scroll">
                  <table className="import-review-table compact">
                    <thead>
                      <tr>
                        {UNIT_MIX_ATTRIBUTES.map((a) => (
                          <th key={a.key}>{a.label}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {mixRows.map((row) => (
                        <tr key={row.id}>
                          <td>{row.name}</td>
                          <td>{row.units}</td>
                          <td>{row.bedsPerUnit}</td>
                          <td>{row.avgSqFt}</td>
                          <td>{row.rent}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </>
            )}
          </>
        ) : (
          <p className="import-review-empty">
            No unit mix table found. The form&apos;s current unit mix is kept.
          </p>
        )}
      </div>

      <div className="form-actions import-review-actions">
        <button
          type="button"
          className="primary"
          onClick={apply}
          disabled={filledCount === 0 && !(includeMix && mixRows.length > 0)}
        >
          Fill the form
        </button>
        <button type="button" className="secondary" onClick={onCancel}>
          Cancel
        </button>
      </div>
    </section>
  );
}
