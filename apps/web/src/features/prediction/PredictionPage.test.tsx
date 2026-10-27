import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";

import { PredictionPage } from "./PredictionPage";
import { GlobalFiltersContext } from "../../app/filters";
import {
  forecastCohort,
  modelsHandler,
  modelRun,
  page,
  predictionsHandler,
} from "../../test/fixtures";
import { server } from "../../test/server";

function renderPage() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  });
  return render(
    <QueryClientProvider client={client}>
      <GlobalFiltersContext.Provider
        value={{ territoryId: null, historicalYear: 2024, setFilters: () => {} }}
      >
        <PredictionPage />
      </GlobalFiltersContext.Provider>
    </QueryClientProvider>,
  );
}

async function predictionTable() {
  return screen.findByRole("table", {
    name: "Predicciones municipales 2027",
  });
}

describe("PredictionPage", () => {
  it("labels the 2027 prediction as distinct from a historical observation", async () => {
    server.use(modelsHandler(), predictionsHandler());
    renderPage();

    expect(
      await screen.findByRole("heading", { level: 1, name: "Predicción 2027" }),
    ).toBeVisible();
    expect(
      await screen.findByText(
        /La observación histórica se consulta en Inteligencia territorial/,
      ),
    ).toBeVisible();
    expect(
      screen.getByText(
        /No es una observación histórica y el año histórico no cambia el horizonte 2027/,
      ),
    ).toBeVisible();

    const table = await predictionTable();
    expect(table).toBeVisible();
    expect(
      screen.getByText(
        /Predicción 2027 del modelo M0.*No es una observación histórica/,
      ),
    ).toBeVisible();
  });

  it("labels insufficient risk as information unavailable, never zero or low risk", async () => {
    server.use(modelsHandler(), predictionsHandler());
    const { container } = renderPage();

    const table = await predictionTable();
    const row = within(table).getByRole("row", { name: /ACATIC/ });
    const cells = within(row).getAllByRole("cell");

    expect(cells[2]).toHaveTextContent("Información insuficiente");
    expect(cells[2]).not.toHaveTextContent("0.0");
    expect(cells[3]).toHaveTextContent("No disponible");
    expect(within(row).queryByText("Riesgo bajo")).not.toBeInTheDocument();
    expect(within(row).getAllByText("Información insuficiente").length).toBeGreaterThan(0);

    const badge = row.querySelector(".risk-badge");
    expect(badge).toHaveAttribute("data-risk", "insufficient");
    expect(container.querySelector('.risk-badge[data-risk="insufficient"]')).toBeTruthy();
  });

  it("states that served M0 uses one production feature, not the shared six-field order", async () => {
    server.use(modelsHandler(), predictionsHandler());
    renderPage();

    expect(
      await screen.findByText(
        "1 variable de producción: abstención del mismo tipo (t-6)",
      ),
    ).toBeVisible();
    expect(screen.queryByText(/6 variables temporales/)).not.toBeInTheDocument();
    expect(
      screen.getByText(/En producción, M0 no utiliza variables sociodemográficas/),
    ).toBeVisible();
  });

  it("shows loading instead of zero for the unstable count while predictions load", async () => {
    let release: () => void = () => {};
    const gate = new Promise<void>((resolve) => {
      release = resolve;
    });
    server.use(
      modelsHandler(),
      http.get("*/api/v1/predictions", async () => {
        await gate;
        return HttpResponse.json(page(forecastCohort()));
      }),
    );
    renderPage();

    const unstable = await screen.findByTestId("unstable-kpi");
    expect(unstable).toHaveTextContent("Cargando…");
    expect(unstable).not.toHaveTextContent("0 de 85");
    expect(screen.getByTestId("exclusion-note")).toHaveTextContent(/cargando/i);
    expect(screen.getByTestId("exclusion-note")).not.toHaveTextContent(
      /0 municipios no elegibles/,
    );

    release();
    await waitFor(() => expect(unstable).toHaveTextContent("70 de 85"));
  });

  it("shows unavailable instead of zero for unstable/exclusions when predictions fail", async () => {
    server.use(
      modelsHandler(),
      http.get("*/api/v1/predictions", () =>
        HttpResponse.json(
          {
            type: "urn:participa-geo:error:unavailable",
            title: "Servicio no disponible",
            status: 503,
            detail: "No fue posible cargar las predicciones.",
            code: "unavailable",
          },
          { status: 503 },
        ),
      ),
    );
    renderPage();

    const unstable = await screen.findByTestId("unstable-kpi");
    await waitFor(() => expect(unstable).toHaveTextContent("No disponible"));
    expect(unstable).not.toHaveTextContent("0 de 85");
    expect(screen.getByTestId("exclusion-note")).toHaveTextContent(
      /no disponibles/i,
    );
    expect(screen.getByTestId("exclusion-note")).not.toHaveTextContent(
      /0 municipios no elegibles/,
    );
  });

  it("refuses to label data as 2027 when the response targets another year", async () => {
    server.use(
      modelsHandler(),
      predictionsHandler(
        forecastCohort().map((item) => ({ ...item, target_year: 2024 })),
      ),
    );
    renderPage();

    expect(
      await screen.findByRole("heading", {
        name: "Respuesta de predicción incompatible",
      }),
    ).toBeVisible();
    expect(
      screen.getByText(/no corresponde al horizonte fijo 2027/),
    ).toBeVisible();
    expect(
      screen.queryByText("Cobertura y exclusiones 2027"),
    ).not.toBeInTheDocument();
  });

  it("keeps validation 2021 and test 2024 metrics in separate columns", async () => {
    server.use(modelsHandler(), predictionsHandler());
    renderPage();

    const metrics = await screen.findByRole("table", {
      name: "Métricas por familia y periodo",
    });
    const headers = within(metrics).getAllByRole("columnheader");
    expect(headers.map((header) => header.textContent)).toEqual([
      "Familia",
      "Estado",
      "MAE validación 2021",
      "MAE prueba 2024",
      "Sesgo validación 2021",
      "Sesgo prueba 2024",
    ]);

    const m0 = within(metrics).getByRole("row", { name: /^M0/ });
    const m0Cells = within(m0).getAllByRole("cell");
    expect(m0Cells[2]).toHaveTextContent("4.93 pp");
    expect(m0Cells[3]).toHaveTextContent("3.43 pp");

    const m1 = within(metrics).getByRole("row", { name: /^M1/ });
    const m1Cells = within(m1).getAllByRole("cell");
    expect(m1Cells[2]).toHaveTextContent("8.90 pp");
    expect(m1Cells[3]).toHaveTextContent("4.82 pp");
    expect(
      screen.getByText(/La validación 2021 se usó para elegir la familia/),
    ).toBeVisible();
    expect(
      screen.getByText(/no garantiza el desempeño futuro/),
    ).toBeVisible();
  });

  it("explains the baseline winner honestly without claiming M1 won or is served", async () => {
    server.use(modelsHandler(), predictionsHandler());
    renderPage();

    const explanation = await screen.findByTestId("selection-explanation");
    expect(explanation).toHaveTextContent(
      "M0 fue seleccionado porque obtuvo el menor MAE en la validación 2021 (4.93 pp frente a 8.90 pp de M1). M1 añade variables sociodemográficas, no fue seleccionado y no se utiliza en producción.",
    );
    expect(screen.getByText("M0 seleccionado")).toBeVisible();
    expect(
      screen.getByText("Candidato · no seleccionado", { exact: false }),
    ).toBeVisible();
    expect(screen.queryByText(/M1 ganó/i)).not.toBeInTheDocument();
    expect(
      screen.getByText(/En producción, M0 no utiliza variables sociodemográficas/),
    ).toBeVisible();
  });

  it("shows coverage, exclusions, the historical-error reference band and the unstable flag", async () => {
    server.use(modelsHandler(), predictionsHandler());
    renderPage();

    expect(
      await screen.findByText("85 de 125", { exact: false }),
    ).toBeVisible();
    expect(screen.getByText("40", { exact: true })).toBeVisible();
    const table = await predictionTable();
    expect(await screen.findByText("70 de 85")).toBeVisible();
    expect(
      screen.getByText("Rango de error histórico de referencia"),
    ).toBeVisible();
    expect(screen.getByText("8.56 pp")).toBeVisible();
    expect(
      screen.getByText(/No es un intervalo de confianza del 90 %/),
    ).toBeVisible();
    expect(
      screen.getByText(/40 municipios no elegibles por alta proporción de no especificados/),
    ).toBeVisible();
    expect(
      screen.getByText(/La banda cruza un umbral de riesgo/),
    ).toBeVisible();

    const unstableRow = within(table).getByRole("row", { name: /ACATLAN DE JUAREZ/ });
    expect(within(unstableRow).getByText("Inestable")).toBeVisible();
  });

  it("shows the M1 additive coefficients as associations in the transformed scale", async () => {
    server.use(modelsHandler(), predictionsHandler());
    renderPage();

    expect(
      await screen.findByRole("heading", {
        name: "Contribuciones aditivas del candidato M1",
      }),
    ).toBeVisible();
    const coefficients = screen.getByRole("table", {
      name: "Coeficientes aditivos del candidato M1",
    });
    expect(
      within(coefficients).getByRole("row", {
        name: /Abstención del mismo tipo \(t-6\)/,
      }),
    ).toHaveTextContent("+5.68");
    expect(
      within(coefficients).getByRole("row", { name: /Elección intermedia/ }),
    ).toHaveTextContent("-3.36");
    expect(
      within(coefficients).getByRole("row", {
        name: /Abstención del mismo tipo \(t-6\)/,
      }),
    ).toHaveTextContent("Aumenta la estimación");
    expect(screen.getByText("Intercepto 36.33 pp")).toBeVisible();
    expect(
      screen.getByText(
        /describen asociaciones en la escala transformada; no identifican causas ni efectos/,
      ),
    ).toBeVisible();
    expect(
      screen.getByText(/M1 no está en producción ni se usa para las predicciones publicadas/),
    ).toBeVisible();
  });

  it("shows a recoverable error when model evidence fails", async () => {
    server.use(
      predictionsHandler(),
      http.get("*/api/v1/models", () =>
        HttpResponse.json(
          {
            type: "urn:participa-geo:error:unavailable",
            title: "Servicio no disponible",
            status: 503,
            detail: "No fue posible cargar la evidencia del modelo.",
            code: "unavailable",
          },
          { status: 503 },
        ),
      ),
    );
    renderPage();

    expect(
      await screen.findByRole("heading", {
        level: 1,
        name: "No se pudo cargar la evidencia del modelo",
      }),
    ).toBeVisible();
    expect(screen.getByRole("button", { name: /Reintentar/ })).toBeVisible();
  });

  it("keeps the selected model when the catalogue response arrives", async () => {
    server.use(modelsHandler([modelRun()]), predictionsHandler(forecastCohort()));
    renderPage();

    const selector = await screen.findByLabelText("Ejecución de modelo");
    expect(selector).toHaveValue("5bc387ce-6646-5b49-9c4f-ad302f4c422a");
    await waitFor(() =>
      expect(
        screen.getByText(/M0 reference: same-municipality same-type abstention/),
      ).toBeVisible(),
    );
  });
});
