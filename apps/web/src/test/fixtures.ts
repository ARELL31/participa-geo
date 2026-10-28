import { http, HttpResponse } from "msw";

import type {
  HistoryDTO,
  ModelDTO,
  Page,
  PredictionDTO,
  RecommendationDTO,
  ReportArtifactDTO,
  ScenarioDTO,
  ScenarioResultDTO,
  StateParticipationSummary,
  TerritoryDTO,
} from "../lib/api";

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
    level: "municipality",
    territory_code: municipalityCode,
    municipality_code: municipalityCode,
    district_plan: null,
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
    level: "municipality",
    territory_code: territoryId ? "001" : null,
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

export function summaryHandler(items: StateParticipationSummary[] = []) {
  return http.get("*/api/v1/participation/summary", () =>
    HttpResponse.json(items),
  );
}

export function territoriesErrorHandler(status = 503) {
  return http.get("*/api/v1/territories", () =>
    HttpResponse.json(
      {
        type: "urn:participa-geo:error:unavailable",
        title: "Servicio no disponible",
        status,
        detail: "No fue posible cargar la lista de municipios.",
        code: "unavailable",
      },
      { status },
    ),
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

export const MODEL_RUN_ID = "5bc387ce-6646-5b49-9c4f-ad302f4c422a";
export const SCENARIO_ID = "9b2c5f1e-4d3a-4c6b-8e7f-1a2b3c4d5e6f";

const SELECTED_BAND_LABEL =
  "rango de error histórico de referencia trasladado condicionalmente; no es un intervalo causal";

function territoryUuid(code: string): string {
  return `00000000-0000-4000-8000-${code.padStart(12, "0")}`;
}

function riskFor(value: number | null): "low" | "medium" | "high" | "insufficient" {
  if (value === null) return "insufficient";
  if (value < 40) return "low";
  if (value < 50) return "medium";
  return "high";
}

/**
 * The real model evidence is exposed through ``ModelDTO.metrics``. The fixture
 * mirrors the persisted evaluation exactly so the UI is tested against the
 * selected-family truth (M0 4.93 vs M1 8.90 in validation 2021).
 */
export function modelRun(overrides: Partial<ModelDTO> = {}): ModelDTO {
  return {
    model_run_id: MODEL_RUN_ID,
    family: "M0",
    level: "municipality",
    district_plan: null,
    target_year: 2027,
    reference_date: "2025-12-15",
    features: [
      "same_type_abstention_pct",
      "previous_abstention_pct",
      "previous_young_share",
      "previous_senior_share",
      "previous_rural_share",
      "is_midterm",
    ],
    parameters: {
      alpha: 1.0,
      description:
        "M0 reference: same-municipality same-type abstention at t-6 (2021).",
      limitations: [
        "Reference cartography 2025-12-15; identity_status=verified_catalogue is a prerequisite and footprint_status=not_verified (no historical boundary equality verified).",
        "Association only; coefficients are additive contributions in the transformed scale and carry no causal interpretation.",
      ],
      feature_order: [
        "same_type_abstention_pct",
        "previous_abstention_pct",
        "previous_young_share",
        "previous_senior_share",
        "previous_rural_share",
        "is_midterm",
      ],
      candidate_m1: {
        note: "Candidate with sociodemographics (not selected); fitted on 2015/2018 for the 2021 selection.",
        intercept: 36.33175773517596,
        coefficients: [
          5.6780063510597705,
          1.7960028211993655,
          -1.1363858048551327,
          -2.8070461676487373,
          -0.8227393484111305,
          -3.3618270133221575,
        ],
      },
      explanations: [
        {
          municipality_code: "002",
          intercept: 0,
          contributions: { same_type_abstention_pct: 45.11343804537522 },
          pre_clip_sum: 45.11343804537522,
        },
      ],
      candidate_m1_explanations: [
        {
          municipality_code: "002",
          intercept: 36.33175773517596,
          contributions: {
            same_type_abstention_pct: 5.68,
            previous_abstention_pct: 1.8,
            previous_young_share: -1.14,
            previous_senior_share: -2.81,
            previous_rural_share: -0.82,
            is_midterm: -3.36,
          },
          pre_clip_sum: 35.68,
        },
      ],
    },
    cut_dates: {
      validation_year: 2021,
      test_year: 2024,
      target_year: 2027,
      reference_date: "2025-12-15",
    },
    metrics: {
      metrics: {
        m0: {
          "2021": {
            mae: 4.93363617513041,
            bias: -4.720197497571386,
            n: 91,
            rmse: 5.6533344695760155,
          },
          "2024": {
            mae: 3.431783670594166,
            bias: -3.041854696197415,
            n: 75,
            rmse: 4.532157034905183,
          },
        },
        m1: {
          "2021": {
            mae: 8.89982962915524,
            bias: -8.89982962915524,
            n: 91,
            rmse: 9.465587637630087,
          },
          "2024": {
            mae: 4.816708316733803,
            bias: 2.1803851875009332,
            n: 75,
            rmse: 5.95949667586275,
          },
        },
      },
      selection: { m0_mae_2021: 4.93363617513041, m1_mae_2021: 8.89982962915524 },
      selected_family: "M0",
      validation_year: 2021,
      test_year: 2024,
      band: {
        amplitude_pp: 8.561771770259021,
        n_errors_2021: 91,
        label: "historical error reference (rango de error histórico de referencia)",
        empirical_coverage_2024: {
          n: 75,
          within: 71,
          share: 71 / 75,
          amplitude_pp: 8.561771770259021,
          minimum_n: 30,
        },
      },
      cohorts: {
        "2024": { eligible_count: 75, excluded_count: 50, total_count: 125 },
        "2027": {
          eligible_count: 85,
          excluded_count: 40,
          total_count: 125,
          eligible_ln: 6054287,
          total_ln: 6619379,
          ln_coverage_base_year: 2024,
        },
      },
    },
    limitations: [
      "Association only; coefficients are additive contributions in the transformed scale and carry no causal interpretation.",
    ],
    created_at: "2026-10-26T12:00:00Z",
    ...overrides,
  };
}

export function prediction(overrides: Partial<PredictionDTO> = {}): PredictionDTO {
  return {
    territory_id: territoryUuid("999"),
    municipality_code: "999",
    level: "municipality",
    territory_code: "999",
    district_plan: null,
    municipality_name: "MUNICIPIO 999",
    target_year: 2027,
    estimated_abstention_pct: 42,
    historical_error_lower_pct: 33.44,
    historical_error_upper_pct: 50.56,
    risk: "medium",
    risk_unstable: false,
    eligible: true,
    quality: {
      eligible: true,
      reasons: [],
      identity_status: "verified_catalogue",
      footprint_status: "not_verified",
    },
    model_run_id: MODEL_RUN_ID,
    ...overrides,
  };
}

/**
 * 125 forecast rows: code 001 is insufficient, 002/003/004 are the readable
 * eligible municipalities used by scenario tests, and 70 of the 85 eligible
 * rows carry ``risk_unstable=true`` (the persisted truth).
 */
export function forecastCohort(): PredictionDTO[] {
  return Array.from({ length: 125 }, (_, index) => {
    const code = String(index + 1).padStart(3, "0");
    const eligible = index >= 1 && index <= 85;
    const knownValues: Record<string, { name: string; value: number }> = {
      "002": { name: "ACATLAN DE JUAREZ", value: 45.11343804537522 },
      "003": { name: "AHUALULCO DE MERCADO", value: 33.10344827586207 },
      "004": { name: "AMACUECA", value: 31.984418956935727 },
      "005": { name: "AMATITAN", value: 35.61550861118181 },
    };
    const known = knownValues[code];
    const value = eligible
      ? known?.value ?? 20 + (index % 35)
      : null;
    const name =
      code === "001"
        ? "ACATIC"
        : known?.name ?? `MUNICIPIO ${code}`;
    return prediction({
      territory_id: territoryUuid(code),
      municipality_code: code,
      municipality_name: name,
      estimated_abstention_pct: value,
      historical_error_lower_pct:
        value === null ? null : Math.max(0, value - 4.28),
      historical_error_upper_pct:
        value === null ? null : Math.min(100, value + 4.28),
      risk: riskFor(value),
      risk_unstable: eligible && index <= 70,
      eligible,
      quality: {
        eligible,
        reasons: eligible ? [] : ["high_unknown_share"],
        identity_status: "verified_catalogue",
        footprint_status: "not_verified",
      },
    });
  });
}

export function predictionsHandler(items: PredictionDTO[] = forecastCohort()) {
  return http.get("*/api/v1/predictions", ({ request }) => {
    const url = new URL(request.url);
    return HttpResponse.json(
      page(items, Object.fromEntries(url.searchParams)),
    );
  });
}

export function modelsHandler(items: ModelDTO[] = [modelRun()]) {
  return http.get("*/api/v1/models", () => HttpResponse.json(page(items)));
}

export function modelHandler(item: ModelDTO = modelRun()) {
  return http.get("*/api/v1/models/:modelRunId", () =>
    HttpResponse.json(item),
  );
}

export function scenarioResult(
  source: PredictionDTO,
  reduction: number,
  selected: boolean,
): ScenarioResultDTO {
  const baseline = source.eligible ? source.estimated_abstention_pct ?? null : null;
  const hypothetical =
    baseline === null ? null : selected ? Math.max(0, baseline - reduction) : baseline;
  const effective =
    baseline === null || hypothetical === null ? 0 : baseline - hypothetical;
  return {
    territory_id: source.territory_id,
    municipality_code: source.municipality_code ?? null,
    municipality_name: source.municipality_name,
    level: source.level,
    territory_code: source.territory_code ?? source.municipality_code ?? null,
    district_plan: source.district_plan ?? null,
    baseline_abstention_pct: baseline,
    hypothetical_abstention_pct: hypothetical,
    baseline_error_lower_pct: source.historical_error_lower_pct ?? null,
    baseline_error_upper_pct: source.historical_error_upper_pct ?? null,
    hypothetical_error_lower_pct:
      source.historical_error_lower_pct === null ||
      source.historical_error_lower_pct === undefined
        ? null
        : Math.max(0, source.historical_error_lower_pct - effective),
    hypothetical_error_upper_pct:
      source.historical_error_upper_pct === null ||
      source.historical_error_upper_pct === undefined
        ? null
        : Math.min(100, source.historical_error_upper_pct - effective),
    requested_reduction_pp: reduction,
    effective_reduction_pp: effective,
    risk_a: source.risk === "low" || source.risk === "medium" || source.risk === "high"
      ? source.risk
      : "insufficient",
    risk_b: riskFor(hypothetical),
    risk_a_unstable: source.risk_unstable,
    risk_b_unstable: selected ? source.risk_unstable : source.risk_unstable,
    selected,
  };
}

export function scenarioDTO(
  predictions: PredictionDTO[],
  options: {
    reduction?: number;
    selectedTerritoryIds?: string[];
    assumptionCode?: "preventive_exploration" | "model_sensitivity";
    scenarioId?: string;
  } = {},
): ScenarioDTO {
  const reduction = options.reduction ?? 3;
  const selectedIds = new Set(options.selectedTerritoryIds ?? []);
  const assumptionCode = options.assumptionCode ?? "preventive_exploration";
  return {
    scenario_id: options.scenarioId ?? SCENARIO_ID,
    model_run_id: MODEL_RUN_ID,
    target_year: 2027,
    requested_reduction_pp: reduction,
    assumption_code: assumptionCode,
    level: "municipality",
    district_plan: null,
    assumption_version: "1.0",
    rationale_text:
      assumptionCode === "preventive_exploration"
        ? "Supuesto de exploración preventiva: la reducción solicitada es un ejercicio aritmético de sensibilidad sobre municipios seleccionados; no representa una eficacia causal demostrada ni una proyección de personas movilizadas."
        : "Supuesto de sensibilidad del modelo: se compara un cambio hipotético acotado para observar si la clasificación de riesgo cambia; no agrega evidencia causal ni cuantifica la incertidumbre del efecto.",
    rules_version: "scenario-rules-1.0.0",
    input_sha256: "a".repeat(64),
    model_sha256: "b".repeat(64),
    error_band_label: SELECTED_BAND_LABEL,
    selected_territory_ids: [...selectedIds],
    results: predictions
      .slice()
      .sort((a, b) =>
        (a.territory_code ?? a.municipality_code ?? "").localeCompare(
          b.territory_code ?? b.municipality_code ?? "",
        ),
      )
      .map((item) => scenarioResult(item, reduction, selectedIds.has(item.territory_id))),
    created_at: "2026-10-26T12:00:00Z",
  };
}

export function scenarioHandler(item: ScenarioDTO = scenarioDTO(forecastCohort())) {
  return http.get("*/api/v1/scenarios/:scenarioId", () =>
    HttpResponse.json(item),
  );
}

export function scenarioCreateHandler(
  build: (body: {
    model_run_id: string;
    target_year: 2027;
    territory_ids: string[];
    reduction_pp: number;
    assumption_code: "preventive_exploration" | "model_sensitivity";
  }) => ScenarioDTO = (body) =>
    scenarioDTO(forecastCohort(), {
      reduction: body.reduction_pp,
      selectedTerritoryIds: body.territory_ids,
      assumptionCode: body.assumption_code,
    }),
) {
  return http.post("*/api/v1/scenarios", async ({ request }) => {
    const body = (await request.json()) as Parameters<typeof build>[0];
    return HttpResponse.json(build(body), { status: 201 });
  });
}

export function recommendation(
  source: PredictionDTO,
): RecommendationDTO {
  const rule =
    source.risk === "high"
      ? {
          code: "institutional_review",
          priority: "high" as const,
          title: "Considerar revisión institucional",
          action:
            "Considerar información cívica y revisión institucional; no constituye una obligación ni una asignación de recursos.",
          reasons: ["risk_high"],
        }
      : source.risk === "medium"
        ? {
            code: "preventive_monitoring",
            priority: "medium" as const,
            title: "Mantener seguimiento preventivo",
            action:
              "Mantener seguimiento preventivo de la categoría de riesgo y revisar la banda de error histórica antes de priorizar.",
            reasons: ["risk_medium"],
          }
        : source.risk === "low"
          ? {
              code: "continue_monitoring",
              priority: "low" as const,
              title: "Continuar monitoreo",
              action:
                "Continuar el monitoreo periódico sin asignar recursos por esta señal aislada.",
              reasons: ["risk_low"],
            }
          : {
              code: "improve_data_quality",
              priority: "data" as const,
              title: "Mejorar datos antes de priorizar",
              action:
                "Revisar la calidad y completar la información del territorio antes de usarlo para priorización; no imputar un valor numérico ni presentar la ausencia como abstención cero.",
              reasons: ["high_unknown_share"],
            };
  return {
    territory_id: source.territory_id,
    municipality_code:
      source.territory_code ?? source.municipality_code ?? "",
    municipality_name: source.municipality_name,
    target_year: 2027,
    risk:
      source.risk === "low" ||
      source.risk === "medium" ||
      source.risk === "high"
        ? source.risk
        : "insufficient",
    risk_unstable: source.risk_unstable,
    eligible: source.eligible,
    model_run_id: MODEL_RUN_ID,
    rules_version: "recommendation-rules-1.0.0",
    recommendations: [
      {
        ...rule,
        version: "recommendation-rules-1.0.0",
      },
    ],
  };
}

export function recommendationsHandler(
  items: RecommendationDTO[] = forecastCohort().map(recommendation),
) {
  return http.get("*/api/v1/recommendations", ({ request }) => {
    const url = new URL(request.url);
    return HttpResponse.json(
      page(items, Object.fromEntries(url.searchParams)),
    );
  });
}

export function wfsErrorHandler(status = 503) {
  return http.get("*/api/v1/gis/wfs", () =>
    HttpResponse.json(
      {
        type: "urn:participa-geo:error:unavailable",
        title: "Servicio no disponible",
        status,
        detail: "No fue posible cargar la cartografía municipal.",
        code: "unavailable",
      },
      { status },
    ),
  );
}

export const REPORT_ID = "a1b2c3d4-5e6f-4a7b-8c9d-0e1f2a3b4c5d";

export function reportArtifact(
  overrides: Partial<ReportArtifactDTO> = {},
): ReportArtifactDTO {
  return {
    report_id: REPORT_ID,
    kind: "history_csv",
    format: "csv",
    status: "ready",
    size_bytes: 2048,
    sha256:
      "68de0514fe0fc8c45989c9282cc58af033bb510c4640f75c7b571cf205e31a4d",
    created_at: "2026-10-26T12:00:00Z",
    download_url: `/api/v1/reports/${REPORT_ID}/download`,
    filename: "participa-geo-historial-2024.csv",
    cached: false,
    sources: {},
    ...overrides,
  };
}

export function reportsHandler(items: ReportArtifactDTO[] = []) {
  return http.get("*/api/v1/reports", () => HttpResponse.json(page(items)));
}

let lastReportRequest: ReportArtifactDTO | null = null;

export function reportCreateHandler(
  resolve: (body: Record<string, unknown>) => ReportArtifactDTO = () =>
    reportArtifact(),
) {
  return http.post("*/api/v1/reports", async ({ request }) => {
    const body = (await request.json()) as Record<string, unknown>;
    const artifact = resolve(body);
    lastReportRequest = artifact;
    return HttpResponse.json(artifact, { status: 201 });
  });
}

export function lastCreatedReport(): ReportArtifactDTO | null {
  return lastReportRequest;
}

export function reportDownloadHandler(
  resolve: (reportId: string) => { body: string; headers?: Record<string, string> } = () => ({
    body: "municipality_code,abstention_pct\n001,43.0\n",
    headers: { "Content-Type": "text/csv" },
  }),
) {
  return http.get("*/api/v1/reports/:reportId/download", ({ params }) => {
    const result = resolve(String(params.reportId));
    return new HttpResponse(result.body, {
      status: 200,
      headers: result.headers ?? { "Content-Type": "application/octet-stream" },
    });
  });
}
