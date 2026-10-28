/**
 * Pure helpers behind the deal form's unit mix table and its "Apply ..."
 * buttons. Rent in the unit mix is always monthly rent per UNIT; per-bed
 * rent is that total divided by the total beds.
 */

export interface UnitMixRowInput {
  units: string;
  bedsPerUnit: string;
  avgSqFt: string;
  rent: string;
}

export interface UnitMixTotals {
  units: number;
  beds: number;
  /** Sum of units x monthly rent per unit. */
  monthlyGpr: number;
  avgRentPerUnit: number;
  avgRentPerBed: number;
  avgRentPerSqFt: number;
}

export function unitMixTotals(rows: UnitMixRowInput[]): UnitMixTotals {
  let units = 0;
  let beds = 0;
  let monthlyGpr = 0;
  let sqft = 0;
  for (const row of rows) {
    const count = Number(row.units) || 0;
    units += count;
    beds += count * (Number(row.bedsPerUnit) || 1);
    monthlyGpr += count * (Number(row.rent) || 0);
    sqft += count * (Number(row.avgSqFt) || 0);
  }
  return {
    units,
    beds,
    monthlyGpr,
    avgRentPerUnit: units > 0 ? monthlyGpr / units : 0,
    avgRentPerBed: beds > 0 ? monthlyGpr / beds : 0,
    avgRentPerSqFt: sqft > 0 ? monthlyGpr / sqft : 0,
  };
}

/**
 * Whether filling `next` into a field that holds `current` would overwrite
 * something the user entered: true only when the field holds a non-zero
 * value that differs from the new one.
 */
export function wouldOverwrite(current: string, next: string): boolean {
  const trimmed = current.trim();
  if (trimmed === "") return false;
  const currentValue = Number(trimmed);
  if (currentValue === 0) return false;
  const nextValue = Number(next);
  if (Number.isFinite(currentValue) && Number.isFinite(nextValue)) {
    return Math.abs(currentValue - nextValue) > 1e-9;
  }
  return trimmed !== next.trim();
}

/** A positive whole number typed into a count field ("150", not "150.5" or "-3"). */
export function isPositiveInteger(value: string): boolean {
  const trimmed = value.trim();
  if (trimmed === "") return false;
  const parsed = Number(trimmed);
  return Number.isInteger(parsed) && parsed > 0;
}
