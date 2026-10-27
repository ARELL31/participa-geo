import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { App } from "../../app/App";
import {
  historyHandler,
  historyYear,
  municipalityFeature,
  TERRITORY_A,
  TERRITORY_B,
  territoriesHandler,
  territory,
  wfsHandler,
} from "../../test/fixtures";
import { server } from "../../test/server";

const TERRITORIES = [
  territory(TERRITORY_A, "001", "ACATIC"),
  territory(TERRITORY_B, "002", "TEPATITLAN"),
];

function renderAt(search: string) {
  window.history.replaceState({}, "", `/territory${search}`);
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  });
  return render(
    <QueryClientProvider client={client}>
      <App />
    </QueryClientProvider>,
  );
}

function featureFor(id: string) {
  return municipalityFeature({
    municipalityCode: id === TERRITORY_A ? "001" : "002",
    name: id === TERRITORY_A ? "ACATIC" : "TEPATITLAN",
    participationPct: 52,
    abstentionPct: id === TERRITORY_A ? 43 : 47,
    unknownShare: 0.05,
  });
}

describe("TerritoryPage", () => {
  it("always shows the geography notice", () => {
    server.use(
      territoriesHandler(TERRITORIES),
      historyHandler(() => []),
      wfsHandler([featureFor(TERRITORY_A), featureFor(TERRITORY_B)]),
    );
    renderAt("?year=2024");
    expect(
      screen.getByText(
        "Referencia cartográfica INE: 15 de diciembre de 2025. No implica igualdad de límites históricos.",
      ),
    ).toBeVisible();
  });

  it("shows an explicit label instead of zero for a null historical rate", async () => {
    server.use(
      territoriesHandler(TERRITORIES),
      historyHandler((params) => {
        const territoryId = params.get("territory_id") ?? TERRITORY_A;
        return [2009, 2012, 2015, 2018, 2021, 2024].map((year) =>
          historyYear(territoryId, year, {
            abstention_pct: year === 2018 ? null : 43,
            participation_pct: year === 2018 ? null : 52,
            eligible: year !== 2018,
          }),
        );
      }),
      wfsHandler([featureFor(TERRITORY_A), featureFor(TERRITORY_B)]),
    );
    renderAt(`?territory_id=${TERRITORY_A}&year=2018`);

    const abstention = await screen.findByTestId("kpi-abstention");
    expect(abstention).toHaveTextContent("Información insuficiente");
    expect(abstention).not.toHaveTextContent(/\b0\b/);

    const table = await screen.findByRole("table", {
      name: "Historia de participación por año",
    });
    const row = within(table).getByRole("row", { name: /2018/ });
    expect(within(row).getAllByText("No disponible").length).toBeGreaterThan(0);
    expect(within(row).queryByText("0")).not.toBeInTheDocument();
  });

  it("keeps the newest selection when an older history response resolves late", async () => {
    let releaseA: () => void = () => {};
    const gateA = new Promise<void>((resolve) => {
      releaseA = resolve;
    });
    let abortedA = false;

    server.use(
      territoriesHandler(TERRITORIES),
      historyHandler(async (params) => {
        const territoryId = params.get("territory_id");
        if (territoryId === TERRITORY_A) {
          return new Promise((resolve) => {
            gateA.then(() => resolve([historyYear(TERRITORY_A, 2024, { abstention_pct: 11 })]));
          });
        }
        if (territoryId === TERRITORY_B) {
          return [historyYear(TERRITORY_B, 2024, { abstention_pct: 77 })];
        }
        return [historyYear(null, 2024, { abstention_pct: 50 })];
      }),
      wfsHandler([featureFor(TERRITORY_A), featureFor(TERRITORY_B)]),
    );

    // Track the AbortSignal exposed to the query function.
    server.events.on("request:start", ({ request }) => {
      const url = new URL(request.url);
      if (url.pathname.endsWith("/participation/history") && url.searchParams.get("territory_id") === TERRITORY_A) {
        request.signal.addEventListener("abort", () => {
          abortedA = true;
        });
      }
    });

    const user = userEvent.setup();
    renderAt(`?territory_id=${TERRITORY_A}&year=2024`);

    // Select B while A is still in flight, then release A afterwards.
    await screen.findByRole("option", { name: /TEPATITLAN/ });
    await user.selectOptions(screen.getByLabelText("Municipio"), TERRITORY_B);
    expect(
      await screen.findByRole("heading", { name: "TEPATITLAN · 002" }),
    ).toBeInTheDocument();
    expect(screen.getByTestId("kpi-abstention")).toHaveTextContent("77");

    releaseA();
    await waitFor(() => expect(abortedA).toBe(true));
    await new Promise((resolve) => setTimeout(resolve, 50));
    expect(
      screen.getByRole("heading", { name: "TEPATITLAN · 002" }),
    ).toBeInTheDocument();
    expect(screen.getByTestId("kpi-abstention")).toHaveTextContent("77");
    expect(screen.queryByText(/ACATIC · 001/)).not.toBeInTheDocument();
  });

  it("keeps the tabular alternative when the map cannot render", async () => {
    server.use(
      territoriesHandler(TERRITORIES),
      historyHandler(() => [historyYear(null, 2024)]),
      wfsHandler([featureFor(TERRITORY_A), featureFor(TERRITORY_B)]),
    );
    renderAt("?year=2024");

    expect(
      await screen.findByText(
        "No se pudo mostrar el mapa. La tabla de municipios sigue disponible.",
      ),
    ).toBeInTheDocument();
    const table = await screen.findByRole("table", {
      name: "Municipios de Jalisco",
    });
    expect(within(table).getByRole("button", { name: "Seleccionar ACATIC" })).toBeInTheDocument();
  });

  it("updates the URL when a municipality is selected from the map table", async () => {
    server.use(
      territoriesHandler(TERRITORIES),
      historyHandler((params) =>
        [historyYear(params.get("territory_id"), 2024, { abstention_pct: 44 })],
      ),
      wfsHandler([featureFor(TERRITORY_A), featureFor(TERRITORY_B)]),
    );
    const user = userEvent.setup();
    renderAt("?year=2024");

    const table = await screen.findByRole("table", {
      name: "Municipios de Jalisco",
    });
    await user.click(
      await within(table).findByRole("button", {
        name: "Seleccionar TEPATITLAN",
      }),
    );
    await waitFor(() =>
      expect(window.location.search).toContain(`territory_id=${TERRITORY_B}`),
    );
    expect(
      await screen.findByRole("heading", { name: "TEPATITLAN · 002" }),
    ).toBeInTheDocument();
  });
});
