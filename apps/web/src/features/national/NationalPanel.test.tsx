import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { GlobalFiltersContext } from "../../app/filters";
import { NationalPanel } from "./NationalPanel";
import { server } from "../../test/server";
import { http, HttpResponse } from "msw";
import { forecastCohort, modelsHandler, predictionsHandler } from "../../test/fixtures";

function renderPanel(
  stateCode = "all",
  level: "municipality" | "federal_district" = "municipality",
) {
  const setFilters = vi.fn();
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  });
  const view = render(
    <QueryClientProvider client={client}>
      <GlobalFiltersContext.Provider
        value={{
          level,
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
  it("derives national municipal coverage from the complete prediction cohort", async () => {
    const predictions = forecastCohort();
    const params: URLSearchParams[] = [];
    server.use(
      modelsHandler(),
      http.get("*/api/v1/predictions", ({ request }) => {
        params.push(new URL(request.url).searchParams);
        return HttpResponse.json({
          items: predictions,
          total: predictions.length,
          page: 1,
          page_size: 500,
          meta: {},
        });
      }),
      http.get("*/api/v1/participation/summary", () => HttpResponse.json(summaries)),
      http.get("*/api/v1/gis/wfs", () => HttpResponse.json({ type: "FeatureCollection", features: [] })),
    );

    renderPanel();

    expect(await screen.findByText("85 de 125")).toBeVisible();
    expect(screen.getByTestId("national-high-risk")).toHaveTextContent(
      String(predictions.filter((item) => item.eligible && item.risk === "high").length),
    );
    expect(params[0]?.get("state_code")).toBe("all");
  });

  it("shows 32 entity summaries, retaining unavailable observations as unavailable", async () => {
    const requests: URLSearchParams[] = [];
    server.use(
      http.get("*/api/v1/participation/summary", () =>
        HttpResponse.json(summaries),
      ),
      modelsHandler(),
      predictionsHandler(),
      http.get("*/api/v1/gis/wfs", ({ request }) => { requests.push(new URL(request.url).searchParams); return HttpResponse.json({ type: "FeatureCollection", features: [] }); }),
    );
    renderPanel();
    const table = await screen.findByRole("table", { name: "Resumen por entidad" });
    expect(within(table).getAllByRole("row")).toHaveLength(33);
    expect(requests.some((params) => params.get("count") === "32" && !params.has("state_code"))).toBe(true);
    expect(within(table).getByText("Información insuficiente")).toBeVisible();
    expect(within(table).getAllByText("5").length).toBeGreaterThan(0);
  });

  it("selects an entity to drill into its municipalities", async () => {
    server.use(
      http.get("*/api/v1/participation/summary", () =>
        HttpResponse.json(summaries),
      ),
      modelsHandler(),
      predictionsHandler(),
      http.get("*/api/v1/gis/wfs", () => HttpResponse.json({ type: "FeatureCollection", features: [] })),
    );
    const { setFilters } = renderPanel();
    fireEvent.click(await screen.findByRole("button", { name: "Ver municipios de Entidad 14" }));
    expect(setFilters).toHaveBeenCalledWith({ stateCode: "14", territoryId: null });
  });

  it("colors the 32-state WMS map by observed abstention and keeps the summary table accessible", async () => {
    const summaryRequests: URLSearchParams[] = [];
    server.use(
      http.get("*/api/v1/participation/summary", ({ request }) => {
        summaryRequests.push(new URL(request.url).searchParams);
        return HttpResponse.json(summaries);
      }),
      modelsHandler(),
      predictionsHandler(),
      http.get("*/api/v1/gis/wfs", () => HttpResponse.json({
        type: "FeatureCollection",
        features: [
          { type: "Feature", geometry: { type: "Polygon", coordinates: [[[-110, 25], [-109, 25], [-109, 26], [-110, 26], [-110, 25]]] }, properties: { state_code: "01", name: "Entidad 1" } },
          { type: "Feature", geometry: { type: "Polygon", coordinates: [[[-109, 25], [-108, 25], [-108, 26], [-109, 26], [-109, 25]]] }, properties: { state_code: "02", name: "Entidad 2" } },
        ],
      })),
    );

    renderPanel();

    const legend = await screen.findByRole("group", { name: "Leyenda de abstención observada 2024" });
    expect(within(legend).getByText("Menos de 30 %")).toBeVisible();
    expect(within(legend).getByText("40–49.9 %")).toBeVisible();
    expect(within(legend).getByText("50 % o más")).toBeVisible();
    expect(screen.getByRole("img", { name: "Mapa WMS nacional con límites de las 32 entidades federativas" })).toBeVisible();
    await waitFor(() => {
      expect(document.querySelector('[data-state-code="01"]')).toHaveAttribute("fill", "#d1d5db");
      expect(document.querySelector('[data-state-code="02"]')).toHaveAttribute("fill", "#f4d58d");
    });
    const table = screen.getByRole("table", { name: "Resumen por entidad" });
    expect(within(table).getByText("Abstención observada")).toBeVisible();
    expect(within(table).getByText("Información insuficiente")).toBeVisible();
    expect(summaryRequests[0]?.get("level")).toBe("municipality");
    expect(summaryRequests[0]?.get("year")).toBe("2024");
  });

  it("shows observed-only district summaries without prediction or risk labels", async () => {
    server.use(
      http.get("*/api/v1/participation/summary", () => HttpResponse.json(summaries)),
    );

    renderPanel("all", "federal_district");

    const table = await screen.findByRole("table", { name: "Resumen por entidad" });
    expect(within(table).getByText("Abstención observada")).toBeVisible();
    expect(within(table).getByText("Cobertura")).toBeVisible();
    expect(within(table).queryByText(/Riesgo|predicción|elegibles/i)).not.toBeInTheDocument();
    expect(screen.getByText(/Distrito federal · Observado 2024 · Sin modelo 2027/)).toBeVisible();
    expect(screen.getByRole("button", { name: "Ver observación distrital de Entidad 14" })).toBeVisible();
  });

  it("lists plan-2023 district profiles for the selected state without a pending placeholder", async () => {
    server.use(
      http.get("*/api/v1/participation/summary", () => HttpResponse.json(summaries)),
      http.get("*/api/v1/territories", () => HttpResponse.json({ items: [{ id: "c1a1a5b4-0000-4000-8000-000000000001", name: "Distrito 05", state_code: "14", level: "federal_district", territory_code: "05", district_plan: "DERFE2023" }], page: 1, page_size: 500, total: 1, meta: {} })),
      http.get("*/api/v1/participation/history", () => HttpResponse.json({ items: [{ territory_id: "c1a1a5b4-0000-4000-8000-000000000001", year: 2024, name: "Distrito 05", level: "federal_district", ln: 1000, sv: 500, nv: 450, ns: 50, abstention_pct: 47.4, coverage_share: 0.95, eligible: false }], page: 1, page_size: 500, total: 1, meta: {} })),
    );
    renderPanel("14", "federal_district");

    expect(await screen.findByRole("table", { name: "Observación distrital por territorio" })).toBeVisible();
    expect(screen.getByRole("button", { name: /Abrir ficha de Distrito 05/ })).toBeVisible();
    expect(screen.queryByText(/perfil distrital pendiente/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/Predicción 2027|banda de confianza/i)).not.toBeInTheDocument();
  });
});
