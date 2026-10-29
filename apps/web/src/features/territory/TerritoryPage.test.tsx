import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { App } from "../../app/App";
import { prediction } from "../../test/fixtures";
import {
  historyHandler,
  historyYear,
  modelsHandler,
  municipalityFeature,
  observationsHandler,
  page,
  predictionsHandler,
  TERRITORY_A,
  TERRITORY_B,
  territoriesErrorHandler,
  territoriesHandler,
  territory,
  wfsHandler,
} from "../../test/fixtures";
import { server } from "../../test/server";

const TERRITORIES = [
  territory(TERRITORY_A, "001", "ACATIC"),
  territory(TERRITORY_B, "002", "TEPATITLAN"),
];

function renderAt(search: string, setup?: () => void) {
  const query = new URLSearchParams(search);
  if (!query.has("state") && !query.has("state_code")) query.set("state", "14");
  window.history.replaceState({}, "", `/territory?${query.toString()}`);
  server.use(modelsHandler(), predictionsHandler(), observationsHandler([]));
  setup?.();
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
  it("shows an insufficient municipal prediction without zero or green treatment and scopes WFS to state", async () => {
    const wfsQueries: URLSearchParams[] = [];
    renderAt(`?territory_id=${TERRITORY_A}&state=14&year=2024`, () => server.use(
      territoriesHandler(TERRITORIES),
      historyHandler((params) => [historyYear(params.get("territory_id"), 2024)]),
      observationsHandler([historyYear(TERRITORY_A, 2024, { state_code: "14", municipality_code: "001" })]),
      http.get("*/api/v1/gis/wfs", ({ request }) => {
        wfsQueries.push(new URL(request.url).searchParams);
        return HttpResponse.json({ type: "FeatureCollection", features: [] });
      }),
      http.get("*/api/v1/predictions", () => HttpResponse.json(page([
        prediction({ territory_id: TERRITORY_A, municipality_code: "001", territory_code: "001", municipality_name: "ACATIC", estimated_abstention_pct: null, risk: "insufficient", eligible: false }),
      ]))),
    ));

    await screen.findByRole(
      "heading",
      { name: "ACATIC · 001" },
      { timeout: 5_000 },
    );
    expect(await screen.findByText(/Información insuficiente para publicar una predicción 2027/)).toBeVisible();
    expect(screen.queryByText("0.0 %")).not.toBeInTheDocument();
    await waitFor(() => expect(wfsQueries).toHaveLength(2));
    const municipalityQuery = wfsQueries.find((params) => params.get("typeNames")?.endsWith(":municipalities"));
    const outlineQuery = wfsQueries.find((params) => params.get("typeNames")?.endsWith(":states"));
    expect(municipalityQuery?.get("state_code")).toBe("14");
    expect(municipalityQuery?.get("count")).toBe("1000");
    expect(outlineQuery?.get("state_code")).toBe("14");
    expect(outlineQuery?.get("count")).toBe("1");
  });

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
      observationsHandler([historyYear(TERRITORY_A, 2018, { state_code: "14", municipality_code: "001", abstention_pct: null, participation_pct: null })]),
      wfsHandler([featureFor(TERRITORY_A), featureFor(TERRITORY_B)]),
    );
    renderAt(`?territory_id=${TERRITORY_A}&year=2018`);

    const abstention = await screen.findByTestId("kpi-abstention");
    await waitFor(() =>
      expect(abstention).toHaveTextContent("Información insuficiente"),
    );
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
      name: "Municipios de la entidad seleccionada",
    });
    expect(within(table).getByRole("button", { name: "Seleccionar ACATIC" })).toBeInTheDocument();
  });

  it("shows a 2024 observed district profile with plan and aggregate municipality intersections only", async () => {
    const districtId = "c1a1a5b4-0000-4000-8000-000000000001";
    const districtTerritory = {
      ...territory(districtId, "05", "Distrito 05"),
      level: "federal_district" as const,
      district_plan: "DERFE2023" as const,
    };
    const wfsQueries: URLSearchParams[] = [];
    server.use(
      http.get("*/api/v1/territories", () => HttpResponse.json(page([districtTerritory]))),
      historyHandler((params) => params.get("level") === "federal_district"
        ? [historyYear(districtId, 2024, { level: "federal_district", name: "Distrito 05", territory_code: "05", district_plan: "DERFE2023", coverage_share: 0.9513, ln: 1000, sv: 500, nv: 450, ns: 50, abstention_pct: 47.368, eligible: false })]
        : []),
      http.get(/\/api\/v1\/territories\/[^/]+\/municipal-districts$/, () => HttpResponse.json(page([
        { state_code: "14", municipality_code: "001", municipality_name: "Acatic", district_code: "05", district_name: "Distrito 05", district_plan: "DERFE2023", is_split: true, section_count: 3, section_share: 0.6, ln: 600, sv: 300, nv: 270, ns: 30, abstention_pct: 47.368, coverage_share: 0.95 },
        { state_code: "14", municipality_code: "002", municipality_name: "Tepatitlán", district_code: "05", district_name: "Distrito 05", district_plan: "DERFE2023", is_split: false, section_count: 2, section_share: 0.4, ln: 400, sv: 200, nv: 180, ns: 20, abstention_pct: 47.368, coverage_share: 0.95 },
      ]))),
      http.get("*/api/v1/gis/wfs", ({ request }) => {
        wfsQueries.push(new URL(request.url).searchParams);
        return HttpResponse.json({ type: "FeatureCollection", features: [] });
      }),
    );
    renderAt(`?level=federal_district&territory_id=${districtId}&state=14`);

    expect(await screen.findByRole("heading", { name: /Distrito 05 · marco 2023/i })).toBeVisible();
    expect(screen.getByText("Observado 2024")).toBeVisible();
    expect(screen.getByText("Cobertura")).toBeVisible();
    expect(screen.getByText(/Todas las secciones CCPC asignadas al DEF2023 oficial/)).toBeVisible();
    expect(await screen.findByRole("table", { name: /Municipios que intersectan/i })).toBeVisible();
    expect(screen.getByText(/sólo incluyen secciones vinculadas a geometría/)).toBeVisible();
    expect(within(screen.getByRole("table", { name: /Municipios que intersectan/i })).getByRole("button", { name: /Acatic/ })).toBeVisible();
    expect(screen.queryByText(/Predicción 2027|Banda/i)).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Escenario/i })).not.toBeInTheDocument();
    await waitFor(() => expect(wfsQueries).toHaveLength(1));
    expect(wfsQueries[0]?.get("level")).toBe("federal_district");
    expect(wfsQueries[0]?.get("count")).toBe("500");
  });

  it("lists every district intersection for a split municipality without a dominant-district label", async () => {
    const municipalityId = TERRITORY_A;
    const intersections = Array.from({ length: 3 }, (_, index) => ({
      state_code: "14", municipality_code: "001", municipality_name: "Acatic",
      district_code: `0${index + 1}`, district_name: `Distrito 0${index + 1}`,
      district_plan: "DERFE2023", is_split: true, section_count: 1, section_share: 1 / 3,
      ln: 100, sv: 50, nv: 45, ns: 5, abstention_pct: 47.368, coverage_share: 0.95,
    }));
    server.use(
      territoriesHandler(TERRITORIES),
      historyHandler((params) => [historyYear(params.get("territory_id"), 2024)]),
      http.get(/\/api\/v1\/territories\/[^/]+\/municipal-districts$/, () => HttpResponse.json(page(intersections))),
      wfsHandler([featureFor(TERRITORY_A), featureFor(TERRITORY_B)]),
    );
    renderAt(`?territory_id=${municipalityId}&state=14`);

    const table = await screen.findByRole("table", { name: /Distritos que intersectan/i });
    for (const district of intersections) expect(within(table).getByRole("button", { name: new RegExp(district.district_name) })).toBeVisible();
    expect(screen.queryByText(/distrito dominante/i)).not.toBeInTheDocument();
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
      name: "Municipios de la entidad seleccionada",
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

  it("does not refetch the six-year series when only the historical year changes", async () => {
    let seriesRequests = 0;
    let yearRequests = 0;
    const records = [2009, 2012, 2015, 2018, 2021, 2024].map((year) =>
      historyYear(TERRITORY_A, year, {
        name: "ACATIC",
        municipality_code: "001",
        abstention_pct: year === 2021 ? 48.2 : 46.7,
      }),
    );
    server.use(
      territoriesHandler(TERRITORIES),
      http.get("*/api/v1/participation/history", ({ request }) => {
        const url = new URL(request.url);
        const year = url.searchParams.get("year");
        if (year) {
          yearRequests += 1;
          return HttpResponse.json(
            page(records.filter((record) => String(record.year) === year)),
          );
        }
        seriesRequests += 1;
        return HttpResponse.json(page(records));
      }),
      wfsHandler([featureFor(TERRITORY_A), featureFor(TERRITORY_B)]),
    );
    const user = userEvent.setup();
    renderAt(`?territory_id=${TERRITORY_A}&year=2024`);

    expect(
      await screen.findByRole("heading", { name: "ACATIC · 001" }),
    ).toBeInTheDocument();
    await waitFor(() =>
      expect(screen.getByTestId("kpi-abstention")).toHaveTextContent("46.7 %"),
    );

    await user.selectOptions(screen.getByLabelText("Año histórico"), "2021");
    await waitFor(() => expect(window.location.search).toContain("year=2021"));
    await waitFor(() =>
      expect(screen.getByTestId("kpi-abstention")).toHaveTextContent("48.2 %"),
    );

    expect(seriesRequests).toBe(1);
    expect(yearRequests).toBe(2);
  });

  it("labels a deep-linked municipality from history when the catalogue fails", async () => {
    server.use(
      territoriesErrorHandler(503),
      historyHandler((params) => [
        historyYear(params.get("territory_id") ?? TERRITORY_A, 2024, {
          name: "ACATIC",
          municipality_code: "001",
          abstention_pct: 46.7,
        }),
      ]),
      wfsHandler([featureFor(TERRITORY_A)]),
    );
    renderAt(`?territory_id=${TERRITORY_A}&year=2024`);

    expect(
      await screen.findByRole("heading", { name: "ACATIC · 001" }),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("heading", { name: "Agregado estatal de Jalisco" }),
    ).not.toBeInTheDocument();
    expect(
      screen.getByText(/Observación histórica de ACATIC · 001/),
    ).toBeInTheDocument();
  });

  it("describes the state aggregate as summed counts and marks eligibility as not applicable", async () => {
    const stateRecords = [2009, 2012, 2015, 2018, 2021, 2024].map((year) =>
      historyYear(null, year, {
        eligible: false,
        abstention_pct: year === 2024 ? 42.9 : 47.9,
      }),
    );
    server.use(
      territoriesHandler(TERRITORIES),
      historyHandler(() => stateRecords),
      wfsHandler([featureFor(TERRITORY_A), featureFor(TERRITORY_B)]),
    );
    renderAt("?year=2024");

    expect(
      await screen.findByRole("heading", {
        name: "Agregado estatal de Jalisco",
      }),
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        /Agregado estatal calculado sumando conteos municipales antes de recalcular tasas/,
      ),
    ).toBeVisible();
    expect(
      screen.queryByText(/El registro no es elegible para comparación/),
    ).not.toBeInTheDocument();

    const table = await screen.findByRole("table", {
      name: "Historia de participación por año",
    });
    expect(within(table).getAllByText("No aplica")).toHaveLength(6);
  });
});
