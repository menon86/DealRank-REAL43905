/**
 * Pure helpers behind the spreadsheet import review screen
 * (components/ImportReview.tsx): turning a cell the user picked into a
 * form value, and building unit mix rows from the detected table and the
 * column mapping the user confirmed.
 */

import type { ImportCandidate, ImportField, ImportUnitMix, UnitMixAttribute } from "./types";

/** Same shape as the deal form's unit mix rows. */
export interface ImportedMixRow {
  id: string;
  name: string;
  units: string;
  bedsPerUnit: string;
  avgSqFt: string;
  rent: string;
}

export const UNIT_MIX_ATTRIBUTES: { key: UnitMixAttribute; label: string }[] = [
  { key: "name", label: "Unit type" },
  { key: "units", label: "Units" },
  { key: "bedsPerUnit", label: "Beds per unit" },
  { key: "avgSqFt", label: "Avg sq ft" },
  { key: "rent", label: "Monthly rent" },
];

/** A picked cell's value in the field's form units ("" when it doesn't fit). */
export function candidateValue(field: ImportField, candidate: ImportCandidate): string {
  if (field.kind === "text") return candidate.text.slice(0, 255);
  if (field.kind === "choice") {
    const text = candidate.text.trim().toLowerCase();
    return (
      field.choices.find((c) => c.value === text || c.label.toLowerCase() === text)?.value ?? ""
    );
  }
  if (field.kind === "percent") return candidate.percent ?? "";
  return candidate.number ?? "";
}

/** "Sheet!B7 · Purchase Price · $24,500,000" */
export function describeCandidate(candidate: ImportCandidate): string {
  const label = candidate.label.length > 40 ? `${candidate.label.slice(0, 39)}…` : candidate.label;
  return `${candidate.sheet}!${candidate.cell} · ${label} · ${candidate.text}`;
}

/** Bedrooms from a unit type name: "Studio" 1, "2 Bed", "2BR", "2x2", "2/2" 2. */
export function inferBeds(name: string): number | null {
  const text = name.toLowerCase();
  if (/\bstudio\b|\beff(iciency)?\b/.test(text)) return 1;
  const match = text.match(/(\d+)\s*\+?\s*(?:bed|br|bd|x|\/|-?bedroom)/);
  if (match) return Math.max(1, Math.min(20, Number(match[1])));
  return null;
}

const STANDARD_TIERS: { id: string; test: RegExp }[] = [
  { id: "studio", test: /\bstudio\b|\beff(iciency)?\b/i },
  { id: "1bed", test: /\b1\s*(bed|br|bd|x|\/)/i },
  { id: "2bed", test: /\b2\s*(bed|br|bd|x|\/)/i },
  { id: "3bed", test: /\b3\s*(bed|br|bd|x|\/)/i },
  { id: "4bed_plus", test: /\b([4-9]|\d{2,})\s*\+?\s*(bed|br|bd|x|\/)/i },
];

/** Rows from the detected table, read through the user's column mapping. */
export function unitMixFromTable(
  table: ImportUnitMix,
  mapping: Record<UnitMixAttribute, number | null>,
): ImportedMixRow[] {
  const used = new Set<string>();
  const cellText = (cells: ImportUnitMix["rows"][number]["cells"], key: UnitMixAttribute) => {
    const index = mapping[key];
    return index === null || index === undefined ? null : (cells[index] ?? null);
  };
  return table.rows.map((row, i) => {
    const nameCell = cellText(row.cells, "name");
    const name = (nameCell?.text || `Row ${row.row}`).slice(0, 100);
    const number = (key: UnitMixAttribute) => cellText(row.cells, key)?.number ?? "";

    const bedsCell = cellText(row.cells, "bedsPerUnit");
    const beds =
      bedsCell?.number ?? String(inferBeds(bedsCell?.text ?? "") ?? inferBeds(name) ?? 1);

    // Keep the form's standard tier ids where the name says which one it is,
    // so later edits line up with the default rows; otherwise a unique id.
    const standard = STANDARD_TIERS.find((t) => t.test.test(name) && !used.has(t.id))?.id;
    const id = standard ?? `row_${row.row}_${i}`;
    used.add(id);

    return {
      id,
      name,
      units: number("units") || "0",
      bedsPerUnit: beds,
      avgSqFt: number("avgSqFt") || "0",
      rent: number("rent") || "0",
    };
  });
}

/**
 * A value as the user left it on the review screen, cleaned for the form:
 * numeric fields lose currency symbols, thousands commas, percent signs and
 * spaces ("$1,250", "5.5 %"). Anything that still isn't a number is kept
 * as typed so the form's validation flags it rather than it silently
 * becoming 0. Text and choice fields are only trimmed.
 */
export function cleanImportedValue(kind: ImportField["kind"], value: string): string {
  const trimmed = value.trim();
  if (kind === "text" || kind === "choice" || trimmed === "") return trimmed;
  const cleaned = trimmed.replace(/[$,%\s]/g, "");
  return cleaned !== "" && Number.isFinite(Number(cleaned)) ? cleaned : trimmed;
}
