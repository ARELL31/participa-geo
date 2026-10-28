import type { FeatureCollection, Geometry, GeoJsonProperties } from "geojson";

import type { components } from "./api.generated";
import type { ElectionYear, GlobalFilters, TerritoryLevel } from "../app/filters";

type Schemas = components["schemas"];

export type TerritoryDTO = Schemas["TerritoryDTO"];
export type HistoryDTO = Schemas["HistoryDTO"];
export type ModelDTO = Schemas["ModelDTO"];
export type PredictionDTO = Schemas["PredictionDTO"];
export type PredictionQuality = Schemas["PredictionQuality"];
export type ScenarioDTO = Schemas["ScenarioDTO"];
export type ScenarioRequest = Schemas["ScenarioRequest"];
export type ScenarioResultDTO = Schemas["ScenarioResultDTO"];
export type RecommendationDTO = Schemas["RecommendationDTO"];
export type ReportArtifactDTO = Schemas["ReportArtifactDTO"];
export type ReportRequest = Schemas["ReportRequest"];
export type ReportKind = ReportArtifactDTO["kind"];
export type StateParticipationSummary = Schemas["StateParticipationSummary"];

/**
 * ``Page[T]`` is derived from the generated OpenAPI envelope; only the item
 * payload is narrowed. No response DTO is hand-written here.
 */
export type Page<T> = Omit<Schemas["Page_HistoryDTO_"], "items"> & {
  items: T[];
};

export type TerritoryPage = Page<TerritoryDTO>;
export type HistoryPage = Page<HistoryDTO>;
export type ModelPage = Page<ModelDTO>;
export type PredictionPage = Page<PredictionDTO>;
export type RecommendationPage = Page<RecommendationDTO>;
export type ReportPage = Page<ReportArtifactDTO>;

/** Standard GeoJSON, not a second copy of the API DTOs. */
export type MunicipalityFeatureCollection = FeatureCollection<
  Geometry,
  GeoJsonProperties
> & {
  features: Array<{
    type: "Feature";
    id?: string | number;
    geometry: Geometry;
    properties: {
      municipality_code?: string;
      name?: string;
      year?: number;
      participation_pct?: number | null;
      abstention_pct?: number | null;
      unknown_share?: number | null;
      eligible?: boolean | null;
      [key: string]: unknown;
    } | null;
  }>;
};

export class ApiProblem extends Error {
  readonly status: number;
  readonly statusText: string;
  readonly code?: string;

  constructor(status: number, statusText: string, message: string, code?: string) {
    super(message);
    this.name = "ApiProblem";
    this.status = status;
    this.statusText = statusText;
    this.code = code;
  }
}

type ProblemBody = {
  title?: unknown;
  detail?: unknown;
  code?: unknown;
  status?: unknown;
};

async function readProblem(response: Response): Promise<ApiProblem> {
  let body: ProblemBody = {};
  try {
    body = (await response.json()) as ProblemBody;
  } catch {
    // A non-JSON error body still gets a readable, non-leaking message.
  }
  const title = typeof body.title === "string" ? body.title : response.statusText;
  const detail = typeof body.detail === "string" ? body.detail : "";
  const code = typeof body.code === "string" ? body.code : undefined;
  const message = detail ? `${title}. ${detail}` : title;
  return new ApiProblem(
    typeof body.status === "number" ? body.status : response.status,
    response.statusText,
    message,
    code,
  );
}

async function getJson<T>(path: string, signal?: AbortSignal): Promise<T> {
  const response = await fetch(path, {
    signal,
    headers: { Accept: "application/json" },
    credentials: "same-origin",
  });
  if (!response.ok) {
    throw await readProblem(response);
  }
  return (await response.json()) as T;
}

function withQuery(path: string, params: Record<string, string | number | null | undefined>): string {
  const query = new URLSearchParams();
  for (const [name, value] of Object.entries(params)) {
    if (value !== null && value !== undefined && value !== "") {
      query.set(name, String(value));
    }
  }
  const serialized = query.toString();
  return serialized ? `${path}?${serialized}` : path;
}

export async function fetchTerritories(
  options: {
    stateCode?: string;
    level?: TerritoryLevel;
    page?: number;
    pageSize?: number;
    signal?: AbortSignal;
  } = {},
): Promise<TerritoryPage> {
  const path = withQuery("/api/v1/territories", {
    state_code: options.stateCode ?? "14",
    level: options.level ?? "municipality",
    page: options.page ?? 1,
    page_size: options.pageSize ?? 125,
  });
  return getJson<TerritoryPage>(path, options.signal);
}

export async function fetchHistory(
  options: {
    level?: TerritoryLevel;
    stateCode?: string;
    territoryId?: string | null;
    year?: ElectionYear | null;
    page?: number;
    pageSize?: number;
    signal?: AbortSignal;
  } = {},
): Promise<HistoryPage> {
  const path = withQuery("/api/v1/participation/history", {
    territory_id: options.territoryId ?? null,
    level: options.level ?? "municipality",
    state_code: options.stateCode ?? null,
    year: options.year ?? null,
    page: options.page ?? 1,
    page_size: options.pageSize ?? 125,
  });
  return getJson<HistoryPage>(path, options.signal);
}

export async function fetchModels(
  options: { level?: TerritoryLevel; pageSize?: number; signal?: AbortSignal } = {},
): Promise<ModelPage> {
  const path = withQuery("/api/v1/models", {
    page: 1,
    page_size: options.pageSize ?? 25,
    level: options.level ?? "municipality",
  });
  return getJson<ModelPage>(path, options.signal);
}

export async function fetchModel(
  modelRunId: string,
  signal?: AbortSignal,
): Promise<ModelDTO> {
  return getJson<ModelDTO>(
    `/api/v1/models/${encodeURIComponent(modelRunId)}`,
    signal,
  );
}

/**
 * ``target_year`` is fixed at 2027 and is sent explicitly. The API coerces the
 * query string to the integer literal, so 2027 is accepted and any other year
 * is rejected with a validation problem.
 */
export async function fetchPredictions(
  options: {
    level?: TerritoryLevel;
    stateCode?: string;
    territoryId?: string | null;
    modelRunId?: string | null;
    pageSize?: number;
    signal?: AbortSignal;
  } = {},
): Promise<PredictionPage> {
  const path = withQuery("/api/v1/predictions", {
    model_run_id: options.modelRunId ?? null,
    level: options.level ?? "municipality",
    state_code: options.stateCode ?? null,
    territory_id: options.territoryId ?? null,
    target_year: 2027,
    page: 1,
    page_size: options.pageSize ?? 125,
  });
  return getJson<PredictionPage>(path, options.signal);
}

export async function fetchRecommendations(
  options: {
    level?: TerritoryLevel;
    stateCode?: string;
    modelRunId?: string | null;
    pageSize?: number;
    signal?: AbortSignal;
  } = {},
): Promise<RecommendationPage> {
  const path = withQuery("/api/v1/recommendations", {
    model_run_id: options.modelRunId ?? null,
    level: options.level ?? "municipality",
    state_code: options.stateCode ?? null,
    page: 1,
    page_size: options.pageSize ?? 125,
  });
  return getJson<RecommendationPage>(path, options.signal);
}

export async function createScenario(
  body: ScenarioRequest,
  signal?: AbortSignal,
): Promise<ScenarioDTO> {
  const response = await fetch("/api/v1/scenarios", {
    method: "POST",
    signal,
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
    },
    credentials: "same-origin",
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    throw await readProblem(response);
  }
  return (await response.json()) as ScenarioDTO;
}

export async function fetchScenario(
  scenarioId: string,
  signal?: AbortSignal,
): Promise<ScenarioDTO> {
  return getJson<ScenarioDTO>(
    `/api/v1/scenarios/${encodeURIComponent(scenarioId)}`,
    signal,
  );
}

export async function createReport(
  body: ReportRequest,
  signal?: AbortSignal,
): Promise<ReportArtifactDTO> {
  const response = await fetch("/api/v1/reports", {
    method: "POST",
    signal,
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
    },
    credentials: "same-origin",
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    throw await readProblem(response);
  }
  return (await response.json()) as ReportArtifactDTO;
}

export async function fetchReports(
  options: { pageSize?: number; signal?: AbortSignal } = {},
): Promise<ReportPage> {
  const path = withQuery("/api/v1/reports", {
    page: 1,
    page_size: options.pageSize ?? 50,
  });
  return getJson<ReportPage>(path, options.signal);
}

export async function fetchReport(
  reportId: string,
  signal?: AbortSignal,
): Promise<ReportArtifactDTO> {
  return getJson<ReportArtifactDTO>(
    `/api/v1/reports/${encodeURIComponent(reportId)}`,
    signal,
  );
}

/** Fetch a generated artifact and hand the bytes to the browser download. */
export async function downloadReport(
  artifact: ReportArtifactDTO,
  signal?: AbortSignal,
): Promise<void> {
  const response = await fetch(artifact.download_url, {
    signal,
    credentials: "same-origin",
    headers: { Accept: "*/*" },
  });
  if (!response.ok) {
    throw await readProblem(response);
  }
  const blob = await response.blob();
  const objectUrl = URL.createObjectURL(blob);
  try {
    const anchor = document.createElement("a");
    anchor.href = objectUrl;
    anchor.download = artifact.filename || `reporte-${artifact.report_id}`;
    anchor.rel = "noopener";
    document.body.append(anchor);
    anchor.click();
    anchor.remove();
  } finally {
    // Revoke after the click has been dispatched; the browser retains the blob.
    window.setTimeout(() => URL.revokeObjectURL(objectUrl), 1_000);
  }
}

export async function fetchMunicipalityFeatures(
  stateCode: string,
  signal?: AbortSignal,
): Promise<MunicipalityFeatureCollection> {
  const path = withQuery("/api/v1/gis/wfs", {
    service: "WFS",
    version: "2.0.0",
    request: "GetFeature",
    typeNames: "participa_geo_national:municipalities",
    outputFormat: "application/json",
    srsName: "EPSG:4326",
    count: 500,
    level: "municipality",
    state_code: stateCode,
  });
  return getJson<MunicipalityFeatureCollection>(path, signal);
}

/** Summary over all 32 entities; this endpoint is national by contract. */
export async function fetchParticipationSummary(
  options: {
    level?: TerritoryLevel;
    year?: ElectionYear;
    signal?: AbortSignal;
  } = {},
): Promise<StateParticipationSummary[]> {
  const path = withQuery("/api/v1/participation/summary", {
    level: options.level ?? "municipality",
    year: options.year ?? 2024,
  });
  return getJson<StateParticipationSummary[]>(path, options.signal);
}

/** National/state WMS layer. It is raster-only; the country is never fetched as WFS. */
export function wmsTerritoryUrl(): string {
  // The state layer is a light national WMS overview; municipality/district
  // features are requested only after narrowing the view to one territory.
  const layer = "states";
  const params = new URLSearchParams({
    service: "WMS",
    version: "1.3.0",
    request: "GetMap",
    layers: `participa_geo_national:${layer}`,
    styles: "",
    format: "image/png",
    transparent: "true",
    crs: "EPSG:4326",
    width: "1200",
    height: "700",
  });
  // WMS 1.3.0 EPSG:4326 uses latitude,longitude axis order.
  params.set("bbox", "14.5,-118.5,32.8,-86.8");
  return `/api/v1/gis/wms?${params.toString()}`;
}

/**
 * Raster WMS URL used by MapLibre. The gateway (never GeoServer directly)
 * receives only allowlisted parameters; ``year`` becomes an internal CQL filter.
 */
export function wmsAbstentionTileUrl(year: ElectionYear): string {
  const params = new URLSearchParams({
    service: "WMS",
    version: "1.3.0",
    request: "GetMap",
    layers: "participa_geo:participation_history",
    styles: "",
    format: "image/png",
    transparent: "true",
    crs: "EPSG:3857",
    width: "512",
    height: "512",
    year: String(year),
  });
  return `/api/v1/gis/wms?${params.toString()}&bbox={bbox-epsg-3857}`;
}

export const queryKeys = {
  territories: (stateCode = "14", level: TerritoryLevel = "municipality") => ["territories", stateCode, level] as const,
  history: (filters: GlobalFilters) =>
    [
      "history",
       { territoryId: filters.territoryId, year: filters.historicalYear, level: filters.level, stateCode: filters.stateCode },
    ] as const,
  historySeries: (territoryId: string | null, level: TerritoryLevel = "municipality", stateCode = "all") =>
    ["history", "series", { territoryId, level, stateCode }] as const,
  municipalFeatures: (stateCode = "14") =>
    ["gis", "wfs", "municipalities", stateCode] as const,
  summary: (level: TerritoryLevel, year: ElectionYear) => ["summary", level, year] as const,
  models: (level: TerritoryLevel = "municipality") => ["models", level] as const,
  predictions: (modelRunId: string | null, level: TerritoryLevel = "municipality", stateCode = "all", territoryId: string | null = null) =>
    ["predictions", { modelRunId, level, stateCode, territoryId, targetYear: 2027 }] as const,
  recommendations: (modelRunId: string | null) =>
    ["recommendations", { modelRunId, targetYear: 2027 }] as const,
  scenario: (scenarioId: string | null) =>
    ["scenario", scenarioId] as const,
  reports: () => ["reports"] as const,
};
