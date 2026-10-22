import { describe, expect, it } from "vitest";
import { buildReportUrl } from "./client";

describe("buildReportUrl", () => {
  it("builds the flat-hurdle report from a rate", () => {
    const url = new URL(buildReportUrl("pdf", ["a", "b"], 0.08));
    expect(url.pathname).toBe("/reports/pdf");
    expect(url.searchParams.getAll("deal_ids")).toEqual(["a", "b"]);
    expect(url.searchParams.get("hurdle_rate")).toBe("0.08");
  });

  it("builds the risk-adjusted report from the ranking view's inputs", () => {
    const url = new URL(
      buildReportUrl("pptx", ["a"], {
        dscrMinimum: 1.25,
        treasuryYield: 0.046,
        weights: { irr: 2, cash_flow: 1, risk: 1 },
        answers: null,
      }),
    );
    expect(url.pathname).toBe("/reports/pptx");
    expect(url.searchParams.has("hurdle_rate")).toBe(false);
    expect(url.searchParams.get("dscr_minimum")).toBe("1.25");
    expect(url.searchParams.get("treasury_yield")).toBe("0.046");
    expect(url.searchParams.get("weight_irr")).toBe("2");
  });

  it("sends questionnaire answers and omits a blank Treasury override", () => {
    const url = new URL(
      buildReportUrl("pdf", ["a"], {
        dscrMinimum: 1.3,
        treasuryYield: null,
        weights: null,
        answers: { primary_goal: "cash_flow", risk_tolerance: 2, income_need: 4 },
      }),
    );
    expect(url.searchParams.has("treasury_yield")).toBe(false);
    expect(url.searchParams.get("primary_goal")).toBe("cash_flow");
    expect(url.searchParams.get("income_need")).toBe("4");
  });
});
