import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";

import type { ElectionYear } from "../app/filters";
import { ApiProblem, fetchAllPredictions, fetchHistory, fetchNationalStateFeatures, fetchParticipationSummary, fetchPredictions, fetchTerritories, fetchMunicipalityFeatures, wmsTerritoryUrl } from "./api";
import {
  historyYear,
  page,
  prediction,
  TERRITORY_A,
} from "../test/fixtures";
import { server } from "../test/server";

describe("fetchHistory year contract", () => {
  it("sends year only when requested and surfaces the 422 for 2023", async () => {
    const seen: URLSearchParams[] = [];
    server.use(
      http.get("*/api/v1/participation/history", ({ request }) => {
        const url = new URL(request.url);
        seen.push(url.searchParams);
        if (url.searchParams.get("year") === "2023") {
          return HttpResponse.json(
            {
              type: "urn:participa-geo:error:validation_error",
              title: "Validación fallida",
              status: 422,
              detail: "La entrada no supera la validación de esquema.",
              instance: url.pathname,
              code: "validation_error",
              request_id: "00000000-0000-0000-0000-000000000003",
            },
            { status: 422 },
          );
        }
        return HttpResponse.json(page([historyYear(TERRITORY_A, 2024)]));
      }),
    );

    const selected = await fetchHistory({
      territoryId: TERRITORY_A,
      year: 2024,
    });
    expect(selected.items[0]?.year).toBe(2024);
    expect(seen[0]?.get("year")).toBe("2024");

    // The six-year series request must stay unfiltered.
    await fetchHistory({ territoryId: TERRITORY_A });
    expect(seen[1]?.has("year")).toBe(false);

    await expect(
      fetchHistory({ year: 2023 as unknown as ElectionYear }),
    ).rejects.toBeInstanceOf(ApiProblem);
    await expect(
      fetchHistory({ year: 2023 as unknown as ElectionYear }),
    ).rejects.toMatchObject({ status: 422, code: "validation_error" });
  });
});

describe("fetchPredictions target year contract", () => {
  it("sends the fixed target_year=2027 explicitly", async () => {
    const seen: Array<string | null> = [];
    server.use(
      http.get("*/api/v1/predictions", ({ request }) => {
        const url = new URL(request.url);
        seen.push(url.searchParams.get("target_year"));
        return HttpResponse.json(page([prediction()]));
      }),
    );

    const response = await fetchPredictions();
    expect(seen).toEqual(["2027"]);
    expect(response.items[0]?.target_year).toBe(2027);
  });

  it("fetches every prediction page before reporting national cohort values", async () => {
    const requestedPages: string[] = [];
    server.use(
      http.get("*/api/v1/predictions", ({ request }) => {
        const url = new URL(request.url);
        const currentPage = url.searchParams.get("page") ?? "1";
        requestedPages.push(currentPage);
        const start = (Number(currentPage) - 1) * 500;
        const items = Array.from({ length: Math.min(500, 1001 - start) }, (_, index) =>
          prediction({ municipality_code: String(start + index + 1).padStart(5, "0") }),
        );
        return HttpResponse.json({
          ...page(items),
          page: Number(currentPage),
          page_size: 500,
          total: 1001,
        });
      }),
    );

    const response = await fetchAllPredictions({ pageSize: 500 });

    expect(requestedPages).toEqual(["1", "2", "3"]);
    expect(response.items).toHaveLength(1001);
    expect(response.total).toBe(1001);
    expect(response.items.at(-1)?.municipality_code).toBe("01001");
  });
});

describe("national API requests", () => {
  it("loads the 32-state summary and limits municipality geometry to a selected state", async () => {
    const seen: Array<{ path: string; params: URLSearchParams }> = [];
    server.use(
      http.get("*/api/v1/participation/summary", ({ request }) => {
        const url = new URL(request.url);
        seen.push({ path: url.pathname, params: url.searchParams });
        return HttpResponse.json([]);
      }),
      http.get("*/api/v1/territories", ({ request }) => {
        const url = new URL(request.url);
        seen.push({ path: url.pathname, params: url.searchParams });
        return HttpResponse.json(page([]));
      }),
      http.get("*/api/v1/gis/wfs", ({ request }) => {
        const url = new URL(request.url);
        seen.push({ path: url.pathname, params: url.searchParams });
        return HttpResponse.json({ type: "FeatureCollection", features: [] });
      }),
    );

    await fetchParticipationSummary({ level: "municipality", year: 2024 });
    await fetchTerritories({ stateCode: "14", level: "municipality", pageSize: 500 });
    await fetchMunicipalityFeatures("14");

    expect(seen[0]?.params.get("level")).toBe("municipality");
    expect(seen[0]?.params.get("year")).toBe("2024");
    expect(seen[1]?.params.get("state_code")).toBe("14");
    expect(seen[1]?.params.get("page_size")).toBe("500");
    expect(seen[2]?.params.get("state_code")).toBe("14");
    expect(seen[2]?.params.get("typeNames")).toBe(
      "participa_geo_national:municipalities",
    );
    expect(seen[2]?.params.has("year")).toBe(false);
    expect(seen[2]?.params.get("count")).toBe("500");
    expect(seen[2]?.params.get("state_code")).not.toBe("all");
    expect(wmsTerritoryUrl()).toContain("participa_geo_national%3Astates");
  });

  it("requests only the 32 national state geometries for the choropleth", async () => {
    const seen: URLSearchParams[] = [];
    server.use(
      http.get("*/api/v1/gis/wfs", ({ request }) => {
        seen.push(new URL(request.url).searchParams);
        return HttpResponse.json({ type: "FeatureCollection", features: [] });
      }),
    );

    await fetchNationalStateFeatures();

    expect(seen[0]?.get("typeNames")).toBe("participa_geo_national:states");
    expect(seen[0]?.get("count")).toBe("32");
    expect(seen[0]?.get("bbox")).toBe("14.5,-118.5,32.8,-86.8");
    expect(seen[0]?.get("state_code")).toBeNull();
    expect(seen[0]?.has("year")).toBe(false);
  });
});
