import { http, HttpResponse } from "msw";

import type { HistoryDTO, Page, TerritoryDTO } from "../lib/api";

export const TERRITORY_A = "3f8d0f5e-9a4c-4b7d-9f2a-6d1c8e5b7a10";
export const TERRITORY_B = "8c2e4b1a-7d3f-4e6a-8b5c-1f9d2a7e4c30";

export function territory(
  id: string,
  municipalityCode: string,
  name: string,
): TerritoryDTO {
  return {
    id,
    name,
    state_code: "14",
    municipality_code: municipalityCode,
    identity_status: "verified",
    footprint_status: "same",
    reference_date: "2025-12-15",
  };
}

export function historyYear(
  territoryId: string | null,
  year: number,
  overrides: Partial<HistoryDTO> = {},
): HistoryDTO {
  return {
    territory_id: territoryId,
    year,
    name: territoryId ? `Municipio ${territoryId.slice(0, 4)}` : null,
    municipality_code: territoryId ? "001" : null,
    ln: 100_000,
    sv: 52_000,
    nv: 43_000,
    ns: 5_000,
    participation_pct: 52,
    abstention_pct: 43,
    unknown_share: 0.05,
    ns_lower_pct: 38,
    ns_upper_pct: 48,
    eligible: true,
    identity_status: "verified",
    footprint_status: "same",
    ...overrides,
  };
}

export function page<T>(
  items: T[],
  filters: Record<string, unknown> = {},
): Page<T> {
  return {
    items,
    page: 1,
    page_size: 125,
    total: items.length,
    meta: {
      dataset_version_ids: [],
      reference_date: "2025-12-15",
      model_run_id: null,
      generated_at: "2026-10-26T12:00:00Z",
      geographic_warning:
        "Referencia cartográfica: diciembre de 2025 (INE 15DIC2025).",
      filters,
    },
  } as Page<T>;
}

export function territoriesHandler(items: TerritoryDTO[]) {
  return http.get("*/api/v1/territories", () =>
    HttpResponse.json(page(items)),
  );
}

export function historyHandler(
  resolve: (search: URLSearchParams) => HistoryDTO[] | Promise<HistoryDTO[]>,
) {
  return http.get("*/api/v1/participation/history", async ({ request }) => {
    const url = new URL(request.url);
    const items = await resolve(url.searchParams);
    return HttpResponse.json(page(items, Object.fromEntries(url.searchParams)));
  });
}

export type MunicipalityFeatureInput = {
  municipalityCode: string;
  name: string;
  participationPct: number | null;
  abstentionPct: number | null;
  unknownShare: number | null;
};

export function municipalityFeature(input: MunicipalityFeatureInput) {
  return {
    type: "Feature" as const,
    id: `participation_history.${input.municipalityCode}`,
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
      municipality_code: input.municipalityCode,
      name: input.name,
      participation_pct: input.participationPct,
      abstention_pct: input.abstentionPct,
      unknown_share: input.unknownShare,
      eligible: true,
    },
  };
}

export function wfsHandler(features: ReturnType<typeof municipalityFeature>[]) {
  return http.get("*/api/v1/gis/wfs", () =>
    HttpResponse.json({ type: "FeatureCollection", features }),
  );
}

export function emptyWfsHandler() {
  return wfsHandler([]);
}
