import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ExecutivePage } from "./ExecutivePage";
import {
  forecastCohort,
  modelsHandler,
  predictionsHandler,
  recommendation,
  recommendationsHandler,
} from "../../test/fixtures";
import { server } from "../../test/server";

function renderPage() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  });
  return render(
    <QueryClientProvider client={client}>
      <ExecutivePage />
    </QueryClientProvider>,
  );
}

describe("ExecutivePage", () => {
  it("derives coverage, model evidence and signals from the API", async () => {
    const predictions = forecastCohort();
    const highRisk = predictions.filter(
      (item) => item.eligible && item.risk === "high",
    );
    server.use(
      modelsHandler(),
      predictionsHandler(predictions),
      recommendationsHandler(predictions.map((item) => recommendation(item))),
    );
    renderPage();

    expect(
      await screen.findByRole("heading", { level: 1, name: "Panel ejecutivo" }),
    ).toBeVisible();
    expect(await screen.findByText("85 de 125")).toBeVisible();
    expect(
      screen.getByText(/68.0 % de municipios elegibles/),
    ).toBeVisible();
    expect(screen.getByTestId("executive-high-risk")).toHaveTextContent(
      String(highRisk.length),
    );
    expect(screen.getByText("MAE validación 2021")).toBeVisible();
    expect(screen.getByText("4.93 pp")).toBeVisible();
    expect(screen.getByText("MAE prueba 2024")).toBeVisible();
    expect(screen.getByText("3.43 pp")).toBeVisible();
    expect(screen.getByText("8.56 pp")).toBeVisible();
    expect(
      screen.getByText(/M0 no utiliza variables sociodemográficas en producción/),
    ).toBeVisible();
    expect(
      screen.getByText(/Reportes y exportaciones: Disponible en T9/),
    ).toBeVisible();

    const distribution = screen.getByRole("table", {
      name: "Distribución de riesgo predicho 2027",
    });
    const insufficient = within(distribution).getByRole("row", {
      name: /Información insuficiente/,
    });
    expect(within(insufficient).getByText("40")).toBeVisible();
    expect(within(insufficient).queryByText("0.0 %")).not.toBeInTheDocument();

    const signals = screen.getByRole("table", {
      name: "Señales prioritarias de abstención estimada 2027",
    });
    expect(
      within(signals).getByRole("columnheader", {
        name: "Recomendación preventiva",
      }),
    ).toBeVisible();
    expect(
      within(signals).getAllByText("Considerar revisión institucional").length,
    ).toBeGreaterThan(0);
  });
});
