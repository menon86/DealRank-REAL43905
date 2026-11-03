import { describe, expect, it } from "vitest";
import { isPositiveInteger, unitMixTotals, wouldOverwrite } from "./unitMix";

describe("unitMixTotals", () => {
  it("treats rent as per unit and derives per-bed rent from total beds", () => {
    const totals = unitMixTotals([
      { units: "10", bedsPerUnit: "1", avgSqFt: "500", rent: "1000" },
      { units: "10", bedsPerUnit: "4", avgSqFt: "1500", rent: "3000" },
    ]);
    expect(totals.units).toBe(20);
    expect(totals.beds).toBe(50);
    expect(totals.monthlyGpr).toBe(40000);
    expect(totals.avgRentPerUnit).toBe(2000);
    expect(totals.avgRentPerBed).toBe(800);
    expect(totals.avgRentPerSqFt).toBe(2);
  });

  it("returns zero averages for an empty mix", () => {
    const totals = unitMixTotals([{ units: "", bedsPerUnit: "", avgSqFt: "", rent: "" }]);
    expect(totals.avgRentPerUnit).toBe(0);
    expect(totals.avgRentPerBed).toBe(0);
    expect(totals.avgRentPerSqFt).toBe(0);
  });
});

describe("wouldOverwrite", () => {
  it("is false for a blank or zero field, or the same value", () => {
    expect(wouldOverwrite("", "100")).toBe(false);
    expect(wouldOverwrite("0", "100")).toBe(false);
    expect(wouldOverwrite("100", "100.00")).toBe(false);
  });
  it("is true when a different non-zero value is there", () => {
    expect(wouldOverwrite("48000", "51000")).toBe(true);
  });
});

describe("isPositiveInteger", () => {
  it("accepts whole numbers above zero only", () => {
    expect(isPositiveInteger("150")).toBe(true);
    expect(isPositiveInteger("150.5")).toBe(false);
    expect(isPositiveInteger("0")).toBe(false);
    expect(isPositiveInteger("-3")).toBe(false);
    expect(isPositiveInteger("")).toBe(false);
  });
});
