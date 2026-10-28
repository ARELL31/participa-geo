import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { GlobalFiltersContext } from "../app/filters";
import { LevelSwitcher } from "./LevelSwitcher";

describe("LevelSwitcher", () => {
  it("switches level while leaving the selected historical year untouched", () => {
    const setFilters = vi.fn();
    render(
      <GlobalFiltersContext.Provider value={{
        level: "municipality",
        stateCode: "14",
        territoryId: null,
        historicalYear: 2021,
        setFilters,
      }}>
        <LevelSwitcher />
      </GlobalFiltersContext.Provider>,
    );

    fireEvent.change(screen.getByLabelText("Nivel territorial"), { target: { value: "federal_district" } });
    expect(setFilters).toHaveBeenCalledWith({ level: "federal_district", territoryId: null });
    expect(screen.getByLabelText("Entidad")).toHaveValue("14");
  });
});
