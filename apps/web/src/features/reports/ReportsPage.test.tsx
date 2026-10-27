import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it, vi } from "vitest";

import { GlobalFiltersContext } from "../../app/filters";
import { ReportsPage } from "./ReportsPage";
import {
  lastCreatedReport,
  reportArtifact,
  reportCreateHandler,
  reportDownloadHandler,
  reportsHandler,
} from "../../test/fixtures";
import { server } from "../../test/server";

const TERRITORY_ID = "3f8d0f5e-9a4c-4b7d-9f2a-6d1c8e5b7a10";

function renderPage() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <GlobalFiltersContext.Provider
        value={{
          territoryId: TERRITORY_ID,
          historicalYear: 2024,
          setFilters: () => {},
        }}
      >
        <ReportsPage />
      </GlobalFiltersContext.Provider>
    </QueryClientProvider>,
  );
}

function downloadHandlers() {
  return [
    reportCreateHandler((body) =>
      reportArtifact({
        kind: body.kind as "history_csv" | "history_xlsx",
        filename:
          body.kind === "history_xlsx"
            ? "participa-geo-historial-2024.xlsx"
            : "participa-geo-historial-2024.csv",
      }),
    ),
    reportDownloadHandler(() => ({
      body: "municipality_code,abstention_pct\n001,43.0\n002,\n",
      headers: { "Content-Type": "text/csv" },
    })),
  ];
}

describe("ReportsPage", () => {
  it("offers only real history exports and explains missing institutional docs", async () => {
    server.use(reportsHandler([]), ...downloadHandlers());
    const clickSpy = vi
      .spyOn(HTMLAnchorElement.prototype, "click")
      .mockImplementation(() => {});
    const user = userEvent.setup();
    renderPage();

    expect(
      await screen.findByRole("heading", { level: 1, name: "Reportes y exportaciones" }),
    ).toBeVisible();
    const csvButton = await screen.findByRole(
      "button",
      { name: "Descargar historial CSV" },
      { timeout: 4_000 },
    );
    expect(csvButton).toBeEnabled();
    expect(
      screen.getByRole("button", { name: "Descargar historial XLSX" }),
    ).toBeEnabled();
    expect(
      screen.getByText(/Aún no hay documentos institucionales generados/),
    ).toBeVisible();
    expect(
      screen.queryByRole("button", { name: /metodolog/i }),
    ).not.toBeInTheDocument();

    await user.click(
      screen.getByRole("button", { name: "Descargar historial CSV" }),
    );
    await waitFor(() => expect(lastCreatedReport()?.kind).toBe("history_csv"));
    await waitFor(() => expect(clickSpy).toHaveBeenCalled());
    expect(
      await screen.findByText(/Archivo generado: participa-geo-historial-2024.csv/),
    ).toBeVisible();
    clickSpy.mockRestore();
  });

  it("offers user-facing model evidence CSV/XLSX exports", async () => {
    server.use(reportsHandler([]), ...downloadHandlers());
    const clickSpy = vi
      .spyOn(HTMLAnchorElement.prototype, "click")
      .mockImplementation(() => {});
    const user = userEvent.setup();
    renderPage();

    const csv = await screen.findByRole("button", {
      name: "Descargar evidencia CSV",
    });
    expect(csv).toBeEnabled();
    expect(
      screen.getByRole("button", { name: "Descargar evidencia XLSX" }),
    ).toBeEnabled();

    await user.click(csv);
    await waitFor(() =>
      expect(lastCreatedReport()?.kind).toBe("model_evidence_csv"),
    );
    await waitFor(() => expect(clickSpy).toHaveBeenCalled());
    clickSpy.mockRestore();
  });

  it("shows the problem detail and blocks duplicate clicks while exporting", async () => {
    let calls = 0;
    server.use(
      reportsHandler([]),
      http.post("*/api/v1/reports", async () => {
        calls += 1;
        await new Promise((resolve) => setTimeout(resolve, 25));
        return HttpResponse.json(
          {
            type: "urn:participa-geo:error:unavailable",
            title: "Servicio no disponible",
            status: 503,
            detail: "No se pudo generar el archivo: GeoServer no disponible.",
            code: "unavailable",
          },
          { status: 503 },
        );
      }),
    );
    const user = userEvent.setup();
    renderPage();

    const csv = await screen.findByRole("button", {
      name: "Descargar historial CSV",
    });
    await user.click(csv);
    expect(csv).toBeDisabled();
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "No se pudo generar el archivo: GeoServer no disponible.",
    );
    expect(calls).toBe(1);
    expect(csv).toBeEnabled();
  });

  it("lists and downloads an institutional artifact once the CLI published it", async () => {
    const methodology = reportArtifact({
      kind: "methodology_pdf",
      format: "pdf",
      filename: "methodology.pdf",
      size_bytes: 60587,
    });
    server.use(
      reportsHandler([methodology]),
      reportDownloadHandler(() => ({
        body: "%PDF-1.4\n",
        headers: { "Content-Type": "application/pdf" },
      })),
    );
    const clickSpy = vi
      .spyOn(HTMLAnchorElement.prototype, "click")
      .mockImplementation(() => {});
    renderPage();

    expect(
      await screen.findByText("Reporte metodológico · PDF"),
    ).toBeVisible();
    expect(
      screen.getByRole("button", { name: "Descargar" }),
    ).toBeEnabled();
    expect(
      screen.queryByText(/Aún no hay documentos institucionales generados/),
    ).not.toBeInTheDocument();
    clickSpy.mockRestore();
  });
});
