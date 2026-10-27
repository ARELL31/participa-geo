import type { ModelDTO, PredictionDTO, PredictionQuality } from "../../lib/api";
import type { RiskLevel } from "../../components/RiskBadge";

export type MetricSummary = {
  mae: number | null;
  bias: number | null;
  n: number | null;
};

export type ModelMetrics = {
  validationYear: number;
  testYear: number;
  selectedFamily: string | null;
  m0: { validation: MetricSummary; test: MetricSummary };
  m1: { validation: MetricSummary; test: MetricSummary };
  bandAmplitudePp: number | null;
  bandErrors: number | null;
  cohort2027: {
    eligible: number | null;
    excluded: number | null;
    total: number | null;
  };
};

export type CandidateM1 = {
  intercept: number;
  coefficients: number[];
  features: string[];
};

type UnknownRecord = Record<string, unknown>;

function asRecord(value: unknown): UnknownRecord | null {
  return typeof value === "object" && value !== null && !Array.isArray(value)
    ? (value as UnknownRecord)
    : null;
}

function numberAt(root: unknown, path: ReadonlyArray<string>): number | null {
  let current: unknown = root;
  for (const key of path) {
    const record = asRecord(current);
    if (!record || !(key in record)) return null;
    current = record[key];
  }
  return typeof current === "number" && Number.isFinite(current) ? current : null;
}

function stringAt(root: unknown, path: ReadonlyArray<string>): string | null {
  let current: unknown = root;
  for (const key of path) {
    const record = asRecord(current);
    if (!record || !(key in record)) return null;
    current = record[key];
  }
  return typeof current === "string" ? current : null;
}

function metric(metrics: unknown, family: string, year: number): MetricSummary {
  return {
    mae: numberAt(metrics, ["metrics", family, String(year), "mae"]),
    bias: numberAt(metrics, ["metrics", family, String(year), "bias"]),
    n: numberAt(metrics, ["metrics", family, String(year), "n"]),
  };
}

/** Defensive parser: the API exposes model evidence as a JSON object. */
export function parseModelMetrics(metrics: unknown): ModelMetrics | null {
  if (!asRecord(metrics)) return null;
  const validationYear = numberAt(metrics, ["validation_year"]) ?? 2021;
  const testYear = numberAt(metrics, ["test_year"]) ?? 2024;
  return {
    validationYear,
    testYear,
    selectedFamily: stringAt(metrics, ["selected_family"]),
    m0: {
      validation: metric(metrics, "m0", validationYear),
      test: metric(metrics, "m0", testYear),
    },
    m1: {
      validation: metric(metrics, "m1", validationYear),
      test: metric(metrics, "m1", testYear),
    },
    bandAmplitudePp: numberAt(metrics, ["band", "amplitude_pp"]),
    bandErrors: numberAt(metrics, ["band", "n_errors_2021"]),
    cohort2027: {
      eligible: numberAt(metrics, ["cohorts", "2027", "eligible_count"]),
      excluded: numberAt(metrics, ["cohorts", "2027", "excluded_count"]),
      total: numberAt(metrics, ["cohorts", "2027", "total_count"]),
    },
  };
}

export function parseCandidateM1(
  model: ModelDTO | undefined,
): CandidateM1 | null {
  if (!model) return null;
  const parameters = asRecord(model.parameters);
  const candidate = asRecord(parameters?.candidate_m1);
  if (!candidate) return null;
  const intercept = numberAt(candidate, ["intercept"]);
  const rawCoefficients = candidate.coefficients;
  if (intercept === null || !Array.isArray(rawCoefficients)) return null;
  const coefficients = rawCoefficients.filter(
    (value): value is number => typeof value === "number" && Number.isFinite(value),
  );
  if (coefficients.length !== rawCoefficients.length) return null;
  const rawFeatures = parameters?.feature_order;
  const features = Array.isArray(rawFeatures)
    ? rawFeatures.filter((value): value is string => typeof value === "string")
    : model.features ?? [];
  return {
    intercept,
    coefficients,
    features,
  };
}

const FEATURE_LABELS: Record<string, { label: string; unit: string }> = {
  same_type_abstention_pct: {
    label: "Abstención del mismo tipo (t-6)",
    unit: "por desviación estándar",
  },
  previous_abstention_pct: {
    label: "Abstención previa",
    unit: "por desviación estándar",
  },
  previous_young_share: {
    label: "Proporción de jóvenes previa",
    unit: "por desviación estándar",
  },
  previous_senior_share: {
    label: "Proporción de adultos mayores previa",
    unit: "por desviación estándar",
  },
  previous_rural_share: {
    label: "Proporción rural previa",
    unit: "por desviación estándar",
  },
  is_midterm: {
    label: "Elección intermedia",
    unit: "al pasar a elección intermedia",
  },
};

export function featureLabel(feature: string): string {
  return FEATURE_LABELS[feature]?.label ?? feature;
}

export function coefficientUnit(feature: string): string {
  return FEATURE_LABELS[feature]?.unit ?? "en la escala transformada";
}

export function coefficientDirection(value: number): string {
  if (value > 0) return "Aumenta la estimación";
  if (value < 0) return "Reduce la estimación";
  return "Sin contribución";
}

export function formatPct(value: number | null | undefined, digits = 1): string {
  return typeof value === "number" && Number.isFinite(value)
    ? `${value.toFixed(digits)} %`
    : "Información insuficiente";
}

export function formatPp(value: number | null | undefined, digits = 2): string {
  return typeof value === "number" && Number.isFinite(value)
    ? `${value.toFixed(digits)} pp`
    : "No disponible";
}

export function formatSignedPp(
  value: number | null | undefined,
  digits = 2,
): string {
  if (typeof value !== "number" || !Number.isFinite(value)) return "No disponible";
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toFixed(digits)} pp`;
}

export function formatSignedCoefficient(value: number): string {
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toFixed(2)}`;
}

export function formatRange(
  lower: number | null | undefined,
  upper: number | null | undefined,
): string {
  if (
    typeof lower !== "number" ||
    !Number.isFinite(lower) ||
    typeof upper !== "number" ||
    !Number.isFinite(upper)
  ) {
    return "No disponible";
  }
  return `${lower.toFixed(1)}–${upper.toFixed(1)} pp`;
}

export function asRiskLevel(risk: string | null | undefined): RiskLevel {
  return risk === "low" || risk === "medium" || risk === "high"
    ? risk
    : "insufficient";
}

const REASON_LABELS: Record<string, string> = {
  high_unknown_share: "alta proporción de no especificados",
  identity_not_verified: "identidad municipal no verificada",
  footprint_not_verified: "huella geográfica no verificada",
  missing_previous_election: "sin elección previa comparable",
};

export function qualityReasons(quality: PredictionQuality | null | undefined): string[] {
  return (quality?.reasons ?? []).map(
    (reason) => REASON_LABELS[reason] ?? reason,
  );
}

export type PredictionSummary = {
  eligible: number;
  insufficient: number;
  unstable: number;
  total: number;
};

export function summarizePredictions(
  predictions: PredictionDTO[],
  metrics: ModelMetrics | null,
): PredictionSummary {
  const eligibleRows = predictions.filter((item) => item.eligible);
  return {
    eligible: metrics?.cohort2027.eligible ?? eligibleRows.length,
    insufficient:
      metrics?.cohort2027.excluded ??
      predictions.filter((item) => !item.eligible).length,
    unstable: eligibleRows.filter((item) => item.risk_unstable).length,
    total: metrics?.cohort2027.total ?? predictions.length,
  };
}
