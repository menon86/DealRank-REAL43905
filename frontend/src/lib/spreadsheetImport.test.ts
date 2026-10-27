import { describe, expect, it } from "vitest";
import { candidateValue, inferBeds, unitMixFromTable } from "./spreadsheetImport";
import type { ImportCandidate, ImportField, ImportUnitMix } from "./types";

function field(kind: ImportField["kind"], choices: ImportField["choices"] = []): ImportField {
  return {
    key: "k",
    label: "K",
    section: "property",
    group: "Deal",
    kind,
    unit: "",
    choices,
    value: null,
    source: null,
    candidate_id: null,
    confidence: null,
    note: null,
  };
}

const cell: ImportCandidate = {
  id: "Summary!D7",
  sheet: "Summary",
  cell: "D7",
  label: "Exit Cap",
  text: "5.75%",
  number: "0.0575",
  percent: "5.75",
};

describe("candidateValue", () => {
  it("reads a picked cell in the field's units", () => {
    expect(candidateValue(field("percent"), cell)).toBe("5.75");
    expect(candidateValue(field("money"), cell)).toBe("0.0575");
    expect(candidateValue(field("text"), cell)).toBe("5.75%");
  });

  it("matches a choice by value or label", () => {
    const choices = [{ value: "per_bed", label: "Per bed" }];
    expect(candidateValue(field("choice", choices), { ...cell, text: "Per Bed" })).toBe("per_bed");
    expect(candidateValue(field("choice", choices), cell)).toBe("");
  });
});

describe("inferBeds", () => {
  it("reads bedrooms from common unit type names", () => {
    expect(inferBeds("Studio")).toBe(1);
    expect(inferBeds("2 Bed / 2 Bath")).toBe(2);
    expect(inferBeds("B1 - 2x2")).toBe(2);
    expect(inferBeds("3BR")).toBe(3);
    expect(inferBeds("Penthouse")).toBeNull();
  });
});

describe("unitMixFromTable", () => {
  const table: ImportUnitMix = {
    sheet: "Rent Roll Summary",
    header_row: 2,
    columns: [
      { index: 0, letter: "A", header: "Floor Plan" },
      { index: 1, letter: "B", header: "# Units" },
      { index: 2, letter: "C", header: "Bed/Bath" },
      { index: 3, letter: "D", header: "Avg SF" },
      { index: 4, letter: "E", header: "Market Rent" },
    ],
    rows: [
      {
        row: 3,
        cells: [
          { text: "Studio", number: null },
          { text: "80", number: "80" },
          { text: "0/1", number: null },
          { text: "690", number: "690" },
          { text: "1,395", number: "1395" },
        ],
      },
      {
        row: 4,
        cells: [
          { text: "B1 - 2x2", number: null },
          { text: "100", number: "100" },
          { text: "2/2", number: null },
          { text: "1,010", number: "1010" },
          { text: "1,725", number: "1725" },
        ],
      },
    ],
    mapping: { name: 0, units: 1, bedsPerUnit: null, avgSqFt: 3, rent: 4 },
  };

  it("builds form rows through the mapping, guessing beds from the name", () => {
    expect(unitMixFromTable(table, table.mapping)).toEqual([
      { id: "studio", name: "Studio", units: "80", bedsPerUnit: "1", avgSqFt: "690", rent: "1395" },
      {
        id: "2bed",
        name: "B1 - 2x2",
        units: "100",
        bedsPerUnit: "2",
        avgSqFt: "1010",
        rent: "1725",
      },
    ]);
  });

  it("follows a remapped column", () => {
    const rows = unitMixFromTable(table, { ...table.mapping, rent: null, bedsPerUnit: 2 });
    expect(rows.map((r) => r.rent)).toEqual(["0", "0"]);
    expect(rows[1].bedsPerUnit).toBe("2");
  });
});
