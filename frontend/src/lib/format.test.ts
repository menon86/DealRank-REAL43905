import { describe, expect, it } from "vitest";
import {
  bpsInputToFraction,
  formatMoney,
  formatMultiple,
  formatNumber,
  formatPercent,
  fractionToPercentInput,
  percentInputToFraction,
} from "./format";

describe("percent conversion (D7: the one boundary)", () => {
  it("round-trips without float noise", () => {
    expect(fractionToPercentInput(0.07)).toBe("7");
    expect(fractionToPercentInput(0.06125)).toBe("6.125");
    expect(percentInputToFraction("6.125")).toBe(0.06125);
  });

  it("treats unparseable input as zero rather than NaN", () => {
    expect(percentInputToFraction("abc")).toBe(0);
    expect(percentInputToFraction("")).toBe(0);
  });
});

describe("formatters", () => {
  it("show a dash for missing values", () => {
    expect(formatPercent(null)).toBe("—");
    expect(formatMoney(Number.NaN)).toBe("—");
  });
  it("format numbers", () => {
    expect(formatPercent(0.0625)).toBe("6.25%");
    expect(formatMoney(1234567)).toBe("$1,234,567");
  });
});

describe("non-finite values", () => {
  it("show the same dash as NaN for ±Infinity", () => {
    for (const value of [Number.POSITIVE_INFINITY, Number.NEGATIVE_INFINITY, Number.NaN]) {
      expect(formatPercent(value)).toBe("—");
      expect(formatMultiple(value)).toBe("—");
      expect(formatNumber(value)).toBe("—");
      expect(formatMoney(value)).toBe("—");
    }
  });
  it("still format finite values", () => {
    expect(formatMultiple(1.234)).toBe("1.23x");
    expect(formatNumber(-0.5)).toBe("-0.50");
  });
});

describe("bpsInputToFraction", () => {
  it("converts basis points to a fraction", () => {
    expect(bpsInputToFraction("50")).toBe(0.005);
    expect(bpsInputToFraction("12.5")).toBe(0.00125);
  });
  it("treats unparseable input as zero", () => {
    expect(bpsInputToFraction("")).toBe(0);
  });
});
