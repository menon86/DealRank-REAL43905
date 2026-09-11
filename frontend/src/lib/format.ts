/**
 * D7 (docs/build-plan.md section 2): percentages are whole numbers in the
 * UI, decimal fractions everywhere behind it. This file is the ONLY place
 * that conversion happens — nothing else in the frontend multiplies or
 * divides by 100 for a rate field.
 */

/** 0.0625 -> 6.25, for showing a rate field in an <input>. */
export function fractionToPercentInput(fraction: number): string {
  return (fraction * 100).toString();
}

/** "6.25" (whatever the user typed) -> 0.0625, for sending to the client. */
export function percentInputToFraction(percentInput: string): number {
  const parsed = Number.parseFloat(percentInput);
  return Number.isFinite(parsed) ? parsed / 100 : 0;
}

export function formatPercent(fraction: number | null, digits = 2): string {
  if (fraction === null || Number.isNaN(fraction)) return "—";
  return `${(fraction * 100).toFixed(digits)}%`;
}

export function formatMoney(amount: number | null, digits = 0): string {
  if (amount === null || Number.isNaN(amount)) return "—";
  return amount.toLocaleString("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

export function formatMultiple(value: number | null, digits = 2): string {
  if (value === null || Number.isNaN(value)) return "—";
  return `${value.toFixed(digits)}x`;
}

export function formatNumber(value: number | null, digits = 2): string {
  if (value === null || Number.isNaN(value)) return "—";
  return value.toFixed(digits);
}
