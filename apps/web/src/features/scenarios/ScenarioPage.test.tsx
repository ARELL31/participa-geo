import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it, vi } from "vitest";

import { ScenarioPage } from "./ScenarioPage";
import { GlobalFiltersContext } from "../../app/filters";
import {
  forecastCohort,
  modelsHandler,
  predictionsHandler,
  reportArtifact,
  reportCreateHandler,
  reportDownloadHandler,
  scenarioCreateHandler,
  scenarioDTO,
  scenarioHandler,
  SCENARIO_ID,
  lastCreatedReport,
  wfsErrorHandler,
  wfsHandler,
} from "../../test/fixtures";
import { server } from "../../test/server";

const PREDICTIONS = forecastCohort();
const ELIGIBLE = PREDICTIONS.find((item) => item.municipality_code === "002")!;
const INSUFFICIENT = PREDICTIONS.find((item) => item.municipality_code === "001")!;

function renderPage(path = "/scenarios") {
  window.history.replaceState({}, "", path);
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <GlobalFiltersContext.Provider
        value={{ territoryId: null, historicalYear: 2024, setFilters: () => {} }}
      >
        <ScenarioPage />
      </GlobalFiltersContext.Provider>
    </QueryClientProvider>,
  );
}

function baseHandlers() {
  return [
    modelsHandler(),
    predictionsHandler(PREDICTIONS),
    wfsHandler([
      {
        type: "Feature" as const,
        id: "participation_history.001",
        geometry: {
          type: "Polygon" as const,
          coordinates: [
            [
              [-103.4, 20.6],
              [-103.2, 20.6],
              [-103.2, 20.8],
              [-103.4, 20.8],
              [-103.4, 20.6],
            ],
          ],
        },
        properties: {
          year: 2024,
          municipality_code: "001",
          name: "ACATIC",
          participation_pct: 52,
          abstention_pct: 43,
          unknown_share: 0.05,
          eligible: true,
        },
      },
      {
        type: "Feature" as const,
        id: "participation_history.002",
        geometry: {
          type: "Polygon" as const,
          coordinates: [
            [
              [-103.0, 20.4],
              [-102.8, 20.4],
              [-102.8, 20.6],
              [-103.0, 20.6],
              [-103.0, 20.4],
            ],
          ],
        },
        properties: {
          year: 2024,
          municipality_code: "002",
          name: "ACATLAN DE JUAREZ",
          participation_pct: 55,
          abstention_pct: 45,
          unknown_share: 0.02,
          eligible: true,
        },
      },
    ]),
  ];
}

async function fillValidForm(user: ReturnType<typeof userEvent.setup>) {
  const municipalities = await screen.findByLabelText("Municipios");
  await user.selectOptions(municipalities, [ELIGIBLE.territory_id]);
  const reduction = screen.getByLabelText(
    "Reducción hipotética (puntos porcentuales)",
  );
  await user.clear(reduction);
  await user.type(reduction, "3");
  await user.selectOptions(screen.getByLabelText("Supuesto"), "preventive_exploration");
  return { municipalities, reduction };
}

describe("ScenarioPage", () => {
  it("requires a catalogue assumption before creating a scenario", async () => {
    server.use(...baseHandlers());
    renderPage();

    const assumption = await screen.findByLabelText("Supuesto");
    expect(assumption).toBeRequired();
    const options = within(assumption).getAllByRole("option");
    expect(options.map((option) => option.textContent)).toEqual([
      "Seleccione un supuesto",
      "Exploración preventiva",
      "Sensibilidad del modelo",
    ]);

    expect(
      screen.getByText("Escenario hipotético — no implica efecto causal"),
    ).toBeVisible();
    expect(
      screen.queryByRole("button", { name: "Exportar CSV" }),
    ).not.toBeInTheDocument();
  });

  it("does not offer insufficient municipalities in the bounded checklist", async () => {
    server.use(...baseHandlers());
    renderPage();

    const municipalities = await screen.findByLabelText("Municipios");
    const options = within(municipalities).getAllByRole("option");
    expect(options).toHaveLength(85);
    expect(
      within(municipalities).queryByRole("option", { name: /ACATIC/ }),
    ).not.toBeInTheDocument();
    expect(
      screen.getByText(
        /40 municipios con información insuficiente no se pueden seleccionar/,
      ),
    ).toBeVisible();
  });

  it("shows a confirmation summary and applies the reduction only to selected municipalities", async () => {
    let posted: unknown = null;
    server.use(
      ...baseHandlers(),
      scenarioCreateHandler((body) => {
        posted = body;
        return scenarioDTO(PREDICTIONS, {
          reduction: body.reduction_pp,
          selectedTerritoryIds: body.territory_ids,
          assumptionCode: body.assumption_code,
        });
      }),
    );
    const user = userEvent.setup();
    renderPage();

    const { municipalities, reduction } = await fillValidForm(user);
    await user.click(screen.getByRole("button", { name: "Crear escenario" }));

    const summary = await screen.findByRole("region", {
      name: "Confirme el escenario",
    });
    expect(within(summary).getByText("Municipios seleccionados: 1")).toBeVisible();
    expect(within(summary).getByText("Reducción solicitada: 3 pp")).toBeVisible();
    expect(within(summary).getByText(/Exploración preventiva/)).toBeVisible();
    expect(posted).toBeNull();

    await user.click(
      screen.getByRole("button", { name: "Confirmar y crear escenario" }),
    );

    expect(
      await screen.findByRole("heading", { name: "Resultado persistido" }),
    ).toBeVisible();
    expect(posted).toEqual({
      model_run_id: "5bc387ce-6646-5b49-9c4f-ad302f4c422a",
      target_year: 2027,
      territory_ids: [ELIGIBLE.territory_id],
      reduction_pp: 3,
      assumption_code: "preventive_exploration",
    });
    expect(window.location.search).toContain(`scenario_id=${SCENARIO_ID}`);
    expect(screen.getAllByText("Escenario hipotético — no implica efecto causal").length).toBeGreaterThan(0);
    expect(screen.getByText("Escala compartida A/B — mismos cortes y leyenda")).toBeVisible();

    const panelA = screen.getByRole("region", { name: "A · Línea base 2027" });
    const panelB = screen.getByRole("region", {
      name: "B · Escenario hipotético 2027",
    });
    expect(panelA).toHaveAttribute("aria-describedby", "scenario-ab-legend");
    expect(panelB).toHaveAttribute("aria-describedby", "scenario-ab-legend");

    const table = screen.getByRole("table", {
      name: "Comparación A/B por municipio",
    });
    const selectedRow = within(table).getByRole("row", {
      name: /ACATLAN DE JUAREZ/,
    });
    const selectedCells = within(selectedRow).getAllByRole("cell");
    expect(selectedCells[2]).toHaveTextContent("45.1 %");
    expect(selectedCells[3]).toHaveTextContent("42.1 %");
    expect(selectedCells[4]).toHaveTextContent("-3.0 pp");
    expect(selectedCells[7]).toHaveTextContent("Seleccionado");

    const unselectedRow = within(table).getByRole("row", {
      name: /AHUALULCO DE MERCADO/,
    });
    const unselectedCells = within(unselectedRow).getAllByRole("cell");
    expect(unselectedCells[2]).toHaveTextContent("33.1 %");
    expect(unselectedCells[3]).toHaveTextContent("33.1 %");
    expect(unselectedCells[4]).toHaveTextContent("Sin cambio");
    expect(unselectedCells[7]).toHaveTextContent("No seleccionado");

    const insufficientRow = within(table).getByRole("row", { name: /ACATIC/ });
    const insufficientCells = within(insufficientRow).getAllByRole("cell");
    expect(insufficientCells[2]).toHaveTextContent("Información insuficiente");
    expect(insufficientCells[3]).toHaveTextContent("Información insuficiente");
    expect(insufficientCells[4]).toHaveTextContent("—");
    expect(insufficientCells[2]).not.toHaveTextContent("0.0");
    expect(
      insufficientCells[5]?.querySelector(".risk-badge"),
    ).toHaveAttribute("data-risk", "insufficient");

    expect(municipalities).toHaveValue([ELIGIBLE.territory_id]);
    expect(reduction).toHaveValue(3);
  });

  it("retains the form values and shows the problem detail when creation fails", async () => {
    server.use(
      ...baseHandlers(),
      http.post("*/api/v1/scenarios", () =>
        HttpResponse.json(
          {
            type: "urn:participa-geo:error:validation_error",
            title: "Validación fallida",
            status: 422,
            detail:
              "El municipio seleccionado tiene información insuficiente y no puede incluirse.",
            code: "validation_error",
            instance: "/api/v1/scenarios",
            errors: [
              {
                loc: ["body", "territory_ids"],
                msg: "El territorio tiene información insuficiente.",
                reason: "ineligible_territory",
                territory_id: INSUFFICIENT.territory_id,
              },
            ],
          },
          { status: 422 },
        ),
      ),
    );
    const user = userEvent.setup();
    renderPage();

    const { municipalities, reduction } = await fillValidForm(user);
    await user.click(screen.getByRole("button", { name: "Crear escenario" }));
    await user.click(
      screen.getByRole("button", { name: "Confirmar y crear escenario" }),
    );

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("Validación fallida");
    expect(alert).toHaveTextContent(
      "El municipio seleccionado tiene información insuficiente y no puede incluirse.",
    );
    expect(municipalities).toHaveValue([ELIGIBLE.territory_id]);
    expect(reduction).toHaveValue(3);
    expect(screen.getByLabelText("Supuesto")).toHaveValue("preventive_exploration");
    expect(
      screen.queryByRole("heading", { name: "Resultado persistido" }),
    ).not.toBeInTheDocument();
  });

  it("loads a persisted scenario from the share URL on reload", async () => {
    const persisted = scenarioDTO(PREDICTIONS, {
      reduction: 3,
      selectedTerritoryIds: [ELIGIBLE.territory_id],
    });
    server.use(
      ...baseHandlers(),
      scenarioHandler(persisted),
    );
    renderPage(`/scenarios?scenario_id=${SCENARIO_ID}`);

    expect(
      await screen.findByRole("heading", { name: "Resultado persistido" }),
    ).toBeVisible();
    expect(screen.getByText(SCENARIO_ID)).toBeVisible();
    expect(screen.getByText(/Escenario persistido/)).toBeVisible();
    expect(
      screen.getByText(
        /El identificador del escenario está en la dirección de esta página/,
      ),
    ).toBeVisible();
    await waitFor(() =>
      expect(screen.getByText(SCENARIO_ID)).toBeVisible(),
    );
  });

  it("exports the persisted scenario through the real report API", async () => {
    const persisted = scenarioDTO(PREDICTIONS, {
      reduction: 3,
      selectedTerritoryIds: [ELIGIBLE.territory_id],
    });
    server.use(
      ...baseHandlers(),
      scenarioHandler(persisted),
      reportCreateHandler((body) =>
        reportArtifact({
          kind: body.kind as "scenario_csv",
          filename: "participa-geo-escenario.csv",
        }),
      ),
      reportDownloadHandler(() => ({
        body: "municipality_code,abstention_pct\n002,45.113438\n",
        headers: { "Content-Type": "text/csv" },
      })),
    );
    const clickSpy = vi
      .spyOn(HTMLAnchorElement.prototype, "click")
      .mockImplementation(() => {});
    const user = userEvent.setup();
    renderPage(`/scenarios?scenario_id=${SCENARIO_ID}`);

    const csv = await screen.findByRole(
      "button",
      { name: "Exportar CSV" },
      { timeout: 4_000 },
    );
    expect(csv).toBeEnabled();
    expect(screen.getByRole("button", { name: "Exportar GeoJSON" })).toBeEnabled();
    expect(screen.getByRole("button", { name: "Mapa PNG" })).toBeEnabled();
    expect(screen.getByRole("button", { name: "Mapa PDF" })).toBeEnabled();
    await user.click(csv);

    await waitFor(() => {
      expect(lastCreatedReport()?.kind).toBe("scenario_csv");
    });
    expect(clickSpy).toHaveBeenCalled();
    expect(
      await screen.findByText(/Archivo generado: participa-geo-escenario.csv/),
    ).toBeVisible();
    clickSpy.mockRestore();
  });

  it("keeps the A/B table and an explicit error when GIS fails", async () => {
    const persisted = scenarioDTO(PREDICTIONS, {
      reduction: 3,
      selectedTerritoryIds: [ELIGIBLE.territory_id],
    });
    server.use(
      modelsHandler(),
      predictionsHandler(PREDICTIONS),
      scenarioHandler(persisted),
      wfsErrorHandler(503),
    );
    const { container } = renderPage(`/scenarios?scenario_id=${SCENARIO_ID}`);

    expect(
      await screen.findByText(
        "No se pudo cargar la capa cartográfica municipal. La tabla A/B sigue disponible.",
      ),
    ).toBeVisible();
    expect(
      screen.getByRole("table", { name: "Comparación A/B por municipio" }),
    ).toBeVisible();
    expect(container.querySelector(".scenario-map")).toBeNull();
  });

  it("shows an empty state when the model catalogue is empty instead of waiting forever", async () => {
    server.use(modelsHandler([]));
    renderPage();

    expect(
      await screen.findByRole("heading", { level: 1, name: "Sin modelo publicado" }),
    ).toBeVisible();
    expect(
      screen.queryByText("Preparando el simulador municipal"),
    ).not.toBeInTheDocument();
  });

  it("shows loading and empty states without fake figures", async () => {
    server.use(
      modelsHandler(),
      predictionsHandler([]),
      wfsHandler([]),
    );
    renderPage();

    expect(
      await screen.findByText("Sin municipios elegibles"),
    ).toBeVisible();
    expect(screen.queryByRole("button", { name: "Crear escenario" })).not.toBeInTheDocument();
  });
});
