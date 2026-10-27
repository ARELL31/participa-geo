import { describe, expect, it } from "vitest";

import {
  DEFAULT_FILTERS,
  HISTORICAL_YEARS,
  parseFilters,
  serializeFilters,
  type GlobalFilters,
} from "./filters";

describe("global URL filters", () => {
  it("round trips the global historical filters", () => {
    const filters = { territoryId: null, historicalYear: 2021 as const };
    expect(parseFilters(serializeFilters(filters))).toEqual(filters);
    expect(() => parseFilters(new URLSearchParams("year=2023"))).toThrow(
      RangeError,
    );
  });

  it("keeps the selected municipality UUID and year in the URL", () => {
    const filters: GlobalFilters = {
      territoryId: "3f8d0f5e-9a4c-4b7d-9f2a-6d1c8e5b7a10",
      historicalYear: 2024,
    };
    const params = serializeFilters(filters);
    expect(params.get("territory_id")).toBe(filters.territoryId);
    expect(params.get("year")).toBe("2024");
    expect(parseFilters(params)).toEqual(filters);
  });

  it("uses the latest approved year when the URL has no filter", () => {
    expect(parseFilters(new URLSearchParams())).toEqual(DEFAULT_FILTERS);
    expect(DEFAULT_FILTERS.historicalYear).toBe(2024);
    expect(DEFAULT_FILTERS.territoryId).toBeNull();
  });

  it("only accepts the six approved historical years", () => {
    for (const year of HISTORICAL_YEARS) {
      expect(
        parseFilters(new URLSearchParams(`year=${year}`)).historicalYear,
      ).toBe(year);
    }
    for (const year of ["2008", "2023", "2025", "2027", "abc"]) {
      expect(() => parseFilters(new URLSearchParams(`year=${year}`))).toThrow(
        RangeError,
      );
    }
  });

  it("rejects a malformed municipality identifier instead of forwarding it", () => {
    expect(() =>
      parseFilters(new URLSearchParams("territory_id=not-a-uuid&year=2024")),
    ).toThrow(RangeError);
  });

  it("keeps target 2027 out of the historical filter state", () => {
    const params = serializeFilters({
      territoryId: null,
      historicalYear: 2024,
    });
    expect(params.has("target_year")).toBe(false);
    expect(params.get("year")).toBe("2024");
  });
});
