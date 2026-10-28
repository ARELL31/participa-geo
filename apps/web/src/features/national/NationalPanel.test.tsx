import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { GlobalFiltersContext } from "../../app/filters";
import { NationalPanel } from "./NationalPanel";
import { server } from "../../test/server";
import { http, HttpResponse } from "msw";

function renderPanel(stateCode = "all") {
  const setFilters = vi.fn();
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  });
  const view = render(
    <QueryClientProvider client={client}>
      <GlobalFiltersContext.Provider
        value={{
          level: "municipality",
          stateCode: stateCode as "all" | `${number}${number}`,
          territoryId: null,
          historicalYear: 2024,
          setFilters,
        }}
      >
        <NationalPanel />
      </GlobalFiltersContext.Provider>
    </QueryClientProvider>,
  );
  return { ...view, setFilters };
}

const summaries = Array.from({ length: 32 }, (_, index) => ({
  level: "municipality" as const,
  state_code: String(index + 1).padStart(2, "0"),
  state_name: `Entidad ${index + 1}`,
  year: 2024,
  ln: 1000,
  sv: 500,
  nv: 450,
  ns: 50,
  observed_abstention_pct: index === 0 ? null : 45,
  eligible_count: 20,
  insufficient_count: 5,
  high_risk_count: 3,
  coverage_share: 0.8,
}));

describe("NationalPanel", () => {
  it("shows 32 entity summaries, retaining unavailable observations as unavailable", async () => {
    server.use(
      http.get("*/api/v1/participation/summary", () =>
        HttpResponse.json(summaries),
      ),
    );
    renderPanel();
    const table = await screen.findByRole("table", { name: "Resumen por entidad" });
    expect(within(table).getAllByRole("row")).toHaveLength(33);
    expect(within(table).getByText("Información insuficiente")).toBeVisible();
    expect(within(table).getAllByText("5").length).toBeGreaterThan(0);
  });

  it("selects an entity to drill into its municipalities", async () => {
    server.use(
      http.get("*/api/v1/participation/summary", () =>
        HttpResponse.json(summaries),
      ),
    );
    const { setFilters } = renderPanel();
    fireEvent.click(await screen.findByRole("button", { name: "Ver municipios de Entidad 14" }));
    expect(setFilters).toHaveBeenCalledWith({ stateCode: "14", territoryId: null });
  });
});
