/**
 * D7 (docs/build-plan.md section 2): percentages are whole numbers in the
 * UI, decimal fractions everywhere behind it. This file is the ONLY place
 * that conversion happens — nothing else in the frontend multiplies or
 * divides by 100 for a rate field.
 */

/** 0.0625 -> 6.25, for showing a rate field in an <input>. */
export function fractionToPercentInput(fraction: number): string {
  // toFixed strips float noise: 0.07 * 100 is 7.000000000000001 in JS.
  return Number((fraction * 100).toFixed(6)).toString();
}

/** "6.25" (whatever the user typed) -> 0.0625, for sending to the client. */
export function percentInputToFraction(percentInput: string): number {
  const parsed = Number.parseFloat(percentInput);
  return Number.isFinite(parsed) ? Number((parsed / 100).toFixed(8)) : 0;
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

/**
 * Keeps only what a plain number can hold: digits, one decimal point, and a
 * leading minus. Commas the user types or pastes are dropped, so form state
 * always holds a string `Number()` can read.
 */
export function stripNumberInput(text: string): string {
  const negative = text.trimStart().startsWith("-");
  const [whole, ...rest] = text.replace(/[^\d.]/g, "").split(".");
  const fraction = rest.length > 0 ? `.${rest.join("")}` : "";
  return `${negative ? "-" : ""}${whole}${fraction}`;
}

/** "650000.5" -> "650,000.5", for showing a money or count field in an <input>. */
export function groupThousands(raw: string): string {
  const match = /^(-?)(\d*)(.*)$/.exec(raw);
  if (!match) return raw;
  const [, sign, whole, rest] = match;
  return `${sign}${whole.replace(/\B(?=(\d{3})+(?!\d))/g, ",")}${rest}`;
}
