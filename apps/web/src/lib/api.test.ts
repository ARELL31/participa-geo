import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";

import type { ElectionYear } from "../app/filters";
import { ApiProblem, fetchHistory, fetchPredictions } from "./api";
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
});
