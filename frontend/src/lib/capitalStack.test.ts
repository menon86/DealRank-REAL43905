import { describe, expect, it } from "vitest";
import { blankLayer, validateLayers } from "./capitalStack";
import type { LayerForm } from "./capitalStack";

const TOTAL_COST = 10_000_000;

function layer(type: LayerForm["type"], amount: string, extra: Partial<LayerForm> = {}): LayerForm {
  return { ...blankLayer(type), amount, ...extra };
}

const senior = (amount: string, extra: Partial<LayerForm> = {}) =>
  layer("agency_fannie_mae", amount, { interest_rate_pct: "6", ...extra });

describe("validateLayers", () => {
  it("accepts a normal senior loan plus sponsor equity", () => {
    expect(validateLayers([senior("6500000"), layer("sponsor_gp", "3500000")], TOTAL_COST)).toEqual(
      [],
    );
  });

  it("requires exactly one senior layer and at least one equity layer", () => {
    expect(validateLayers([layer("sponsor_gp", "1")], TOTAL_COST)[0]).toMatch(/senior/i);
    expect(
      validateLayers([senior("1"), senior("1"), layer("sponsor_gp", "1")], TOTAL_COST).join(" "),
    ).toMatch(/Only one senior/);
    expect(validateLayers([senior("6500000")], TOTAL_COST).join(" ")).toMatch(/equity layer/);
  });

  it("rejects debt and preferred equity that leave under 5% common equity", () => {
    const errors = validateLayers(
      [
        senior("8000000"),
        layer("mezzanine", "1600000", { interest_rate_pct: "11" }),
        layer("sponsor_gp", "500000"),
      ],
      TOTAL_COST,
    );
    expect(errors.join(" ")).toMatch(/5% of total cost/);
  });

  it("rejects negative amounts", () => {
    const errors = validateLayers([senior("-5"), layer("sponsor_gp", "1")], TOTAL_COST);
    expect(errors.length).toBeGreaterThan(0);
  });

  it("rejects interest-only months longer than the term", () => {
    const errors = validateLayers(
      [senior("6500000", { io_months: "72", term_years: "5" }), layer("sponsor_gp", "3500000")],
      TOTAL_COST,
    );
    expect(errors.join(" ")).toMatch(/exceed the term/);
  });
});
