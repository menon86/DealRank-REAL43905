import { describe, expect, it } from "vitest";
import {
  blankLayer,
  formToLayer,
  upfrontCost,
  validateLayers,
  withDefaultTreasury,
  yearOneDebtService,
} from "./capitalStack";
import type { LayerForm } from "./capitalStack";

const TOTAL_COST = 10_000_000;

function layer(type: LayerForm["type"], amount: string, extra: Partial<LayerForm> = {}): LayerForm {
  return { ...blankLayer(type), amount, ...extra };
}

const senior = (amount: string, extra: Partial<LayerForm> = {}) =>
  // Agency loans default to yield maintenance, so a usable one carries the
  // Treasury rate the form pre-fills from the market.
  layer("agency_fannie_mae", amount, {
    interest_rate_pct: "6",
    prepayment_treasury_pct: "4.25",
    ...extra,
  });

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

describe("prepayment and mortgage insurance", () => {
  it("defaults each loan type to its typical prepayment terms", () => {
    expect(blankLayer("agency_fannie_mae").prepayment_type).toBe("yield_maintenance");
    expect(blankLayer("agency_fannie_mae").term_years).toBe("10");
    expect(blankLayer("cmbs").prepayment_type).toBe("defeasance");
    expect(blankLayer("bank_credit_union").prepayment_schedule).toBe("5, 4, 3, 2, 1");
    expect(blankLayer("bridge_debt_fund").prepayment_type).toBe("none");
    expect(blankLayer("sponsor_gp").prepayment_type).toBe("none");

    const hud = blankLayer("hud_223f");
    expect(hud.prepayment_type).toBe("step_down");
    expect(hud.mip_annual_pct).toBe("0.25");
    expect(hud.mip_upfront_pct).toBe("0.25");
    expect(hud.amortization_years).toBe("35");
  });

  it("needs a Treasury rate for yield maintenance, and fills a blank one", () => {
    const blank = senior("6500000", { prepayment_treasury_pct: "" });
    const errors = validateLayers([blank, layer("sponsor_gp", "1")], TOTAL_COST);
    expect(errors.join(" ")).toMatch(/Treasury rate/);

    const [filled] = withDefaultTreasury([blank], "4.1");
    expect(filled.prepayment_treasury_pct).toBe("4.1");
    // A rate the user typed is kept.
    expect(withDefaultTreasury([senior("1")], "4.1")[0].prepayment_treasury_pct).toBe("4.25");
  });

  it("sends step-down percentages and insurance as fractions", () => {
    const hud = layer("hud_223f", "1000000", { interest_rate_pct: "5.5" });
    const api = formToLayer(hud, TOTAL_COST);
    expect(api.prepayment_type).toBe("step_down");
    expect(api.prepayment_schedule.slice(0, 3)).toEqual([0.1, 0.09, 0.08]);
    expect(api.mip_annual_rate).toBeCloseTo(0.0025);
    expect(api.mip_upfront_rate).toBeCloseTo(0.0025);

    // Mortgage insurance is dropped on a loan type that can't carry it.
    const agency = senior("1000000", { mip_annual_pct: "0.25" });
    expect(formToLayer(agency, TOTAL_COST).mip_annual_rate).toBe(0);
  });

  it("adds mortgage insurance to debt service and the upfront check", () => {
    const plain = layer("hud_223f", "1000000", {
      interest_rate_pct: "6",
      amortization_years: "",
      mip_annual_pct: "0",
      mip_upfront_pct: "0",
    });
    const insured = { ...plain, mip_annual_pct: "0.25", mip_upfront_pct: "0.25" };
    // Interest-only, so the balance (and the premium) is flat: 0.25% x $1M.
    expect(
      yearOneDebtService(insured, TOTAL_COST) - yearOneDebtService(plain, TOTAL_COST),
    ).toBeCloseTo(2500);
    expect(upfrontCost(insured, TOTAL_COST)).toBeCloseTo(2500);
  });
});
