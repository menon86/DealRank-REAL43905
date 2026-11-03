import { describe, expect, it } from "vitest";
import { ApiError, describeError, describeValidationItem } from "./client";

describe("describeValidationItem", () => {
  it("prefixes the message with the field path, minus the request part", () => {
    expect(
      describeValidationItem({
        loc: ["body", "capital_stack", 0, "spread"],
        msg: "Input should be greater than or equal to 0",
      }),
    ).toBe("capital_stack.0.spread: Input should be greater than or equal to 0");
    expect(describeValidationItem({ loc: ["body", "unit_count"], msg: "bad" })).toBe(
      "unit_count: bad",
    );
  });

  it("falls back to the message alone without a usable loc", () => {
    expect(describeValidationItem({ msg: "Value error" })).toBe("Value error");
    expect(describeValidationItem({ loc: ["body"], msg: "Value error" })).toBe("Value error");
  });

  it("skips entries without a message", () => {
    expect(describeValidationItem({ loc: ["body", "x"] })).toBeNull();
  });
});

describe("describeError", () => {
  it("names each rejected field of a 422", () => {
    const body = JSON.stringify({
      detail: [
        { loc: ["body", "unit_count"], msg: "Input should be a valid integer" },
        { loc: ["body", "name"], msg: "Field required" },
      ],
    });
    expect(describeError(new ApiError("POST", "/deals", 422, body))).toBe(
      "Server returned 422: unit_count: Input should be a valid integer; name: Field required",
    );
  });
});
