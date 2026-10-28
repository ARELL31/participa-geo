import { useQuery } from "@tanstack/react-query";
import { Info, RefreshCw } from "lucide-react";
import { useMemo, useState } from "react";

import { useGlobalFilters } from "../../app/filters";
import { DataTable } from "../../components/DataTable";
import { GeographyNotice } from "../../components/GeographyNotice";
import { PageState } from "../../components/PageState";
import { RiskBadge } from "../../components/RiskBadge";
import {
  fetchModels,
  fetchPredictions,
  queryKeys,
  type PredictionDTO,
} from "../../lib/api";
import { ModelComparison } from "./ModelComparison";
import { PredictionExplanation } from "./PredictionExplanation";
import {
  asRiskLevel,
  formatPct,
  formatPp,
  formatRange,
  parseModelMetrics,
  qualityReasons,
  summarizePredictions,
} from "./modelEvidence";

type RiskFilter =
  | "all"
  | "eligible"
  | "insufficient"
  | "low"
  | "medium"
  | "high"
  | "unstable";

function filterPredictions(
  predictions: PredictionDTO[],
  filter: RiskFilter,
): PredictionDTO[] {
  if (filter === "all") return predictions;
  if (filter === "eligible") return predictions.filter((item) => item.eligible);
  if (filter === "insufficient") {
    return predictions.filter((item) => !item.eligible);
  }
  if (filter === "unstable") {
    return predictions.filter((item) => item.eligible && item.risk_unstable);
  }
  return predictions.filter(
    (item) => item.eligible && item.risk === filter,
  );
}

export function PredictionPage() {
  const { level, stateCode, territoryId } = useGlobalFilters();
  const [selectedModelId, setSelectedModelId] = useState<string | null>(null);
  const [riskFilter, setRiskFilter] = useState<RiskFilter>("all");

  const modelsQuery = useQuery({
    queryKey: queryKeys.models(level),
    queryFn: ({ signal }) => fetchModels({ level, signal }),
    enabled: level === "municipality",
    staleTime: 5 * 60_000,
  });

  const models = modelsQuery.data?.items ?? [];
  const selectedModel =
    models.find((model) => model.model_run_id === selectedModelId) ?? models[0];

  const predictionsQuery = useQuery({
    queryKey: queryKeys.predictions(selectedModel?.model_run_id ?? null, level, stateCode, territoryId),
    queryFn: ({ signal }) =>
      fetchPredictions({
        modelRunId: selectedModel?.model_run_id ?? null,
        level,
        stateCode,
        territoryId,
        pageSize: 500,
        signal,
      }),
    enabled: level === "municipality" && Boolean(selectedModel),
    staleTime: 60_000,
  });

  const metrics = useMemo(
    () => parseModelMetrics(selectedModel?.metrics),
    [selectedModel],
  );
  const predictions = predictionsQuery.data?.items ?? [];
  const summary = summarizePredictions(predictions, metrics);
  const filtered = filterPredictions(predictions, riskFilter);
  const predictionsReady = predictionsQuery.isSuccess;
  const exclusionReasons = Array.from(
    new Set(
      predictions
        .filter((item) => !item.eligible)
        .flatMap((item) => qualityReasons(item.quality)),
    ),
  );
  const exclusionText =
    exclusionReasons.length > 0
      ? exclusionReasons.join(", ")
      : "alta proporción de no especificados";
  const unstableValue = predictionsQuery.isPending
    ? "Cargando…"
    : predictionsQuery.isError
      ? "No disponible"
      : `${summary.unstable} de ${summary.eligible}`;
  const targetYearMismatch =
    predictionsReady && predictions.some((item) => item.target_year !== 2027);

  const selectedPrediction = territoryId
    ? predictions.find((item) => item.territory_id === territoryId)
    : undefined;

  if (level === "federal_district") {
    return (
      <div className="page prediction-page">
        <div className="page-heading"><p className="eyebrow">Observación distrital · marco 2023</p><h1>Perfil distrital pendiente</h1></div>
        <PageState variant="empty" title="Observado 2024 / perfil distrital pendiente" message="No existe un modelo distrital publicado. No hay predicción 2027, banda de error ni clasificación de riesgo para este nivel." />
      </div>
    );
  }

  if (modelsQuery.isPending) {
    return (
      <div className="page prediction-page">
        <PredictionHeading />
        <PageState
          variant="loading"
          title="Cargando evidencia del modelo"
          message="Consultando la ejecución publicada y sus métricas persistidas."
        />
      </div>
    );
  }

  if (modelsQuery.isError) {
    return (
      <div className="page prediction-page">
        <PredictionHeading />
        <PageState
          variant="error"
          headingLevel={1}
          title="No se pudo cargar la evidencia del modelo"
          message={
            modelsQuery.error instanceof Error
              ? modelsQuery.error.message
              : "La consulta de modelos no está disponible en este momento."
          }
          action={
            <button
              type="button"
              className="button button--primary"
              onClick={() => void modelsQuery.refetch()}
            >
              <RefreshCw aria-hidden="true" size={16} strokeWidth={1.8} />
              Reintentar consulta
            </button>
          }
        />
      </div>
    );
  }

  if (!selectedModel) {
    return (
      <div className="page prediction-page">
        <PredictionHeading />
        <PageState
          variant="empty"
          title="Sin ejecuciones de modelo publicadas"
          message="No hay una predicción persistida para 2027. La pantalla no muestra cifras de ejemplo."
        />
      </div>
    );
  }

  if (targetYearMismatch) {
    return (
      <div className="page prediction-page">
        <PredictionHeading />
        <PageState
          variant="error"
          title="Respuesta de predicción incompatible"
          message="La API devolvió filas cuyo target_year no corresponde al horizonte fijo 2027. No se etiquetan como predicción 2027 ni se muestran como evidencia."
        />
      </div>
    );
  }

  return (
    <div className="page prediction-page">
      <PredictionHeading />

      <GeographyNotice />

      <section className="prediction-distinction" aria-labelledby="distinction-heading">
        <Info aria-hidden="true" size={20} strokeWidth={1.8} />
        <div>
          <h2 id="distinction-heading" className="visually-hidden">
            Qué muestra esta pantalla
          </h2>
          <p>
            <strong>Predicción, no observación.</strong>
          </p>
          <p>
            La observación histórica se consulta en Inteligencia territorial y
            tiene su propio selector de año. No es una observación histórica y el
            año histórico no cambia el horizonte 2027.
          </p>
        </div>
      </section>

      <ModelComparison
        models={models}
        selectedModel={selectedModel}
        selectDisabled={models.length <= 1}
        onSelectModel={(modelRunId) => setSelectedModelId(modelRunId)}
      />

      <section className="summary-card" aria-labelledby="coverage-heading">
        <div className="card-heading">
          <div>
            <h2 id="coverage-heading">Cobertura y exclusiones 2027</h2>
            <p>
              Elegibilidad calculada antes de estimar. Una fila insuficiente no
              se imputa como cero ni como riesgo bajo.
            </p>
          </div>
          <span className="status-pill status-pill--neutral">Predicción 2027</span>
        </div>

        <dl className="kpi-grid">
          <div className="kpi">
            <dt>Municipios elegibles</dt>
            <dd data-testid="coverage-eligible">
              {summary.eligible} de {summary.total}
            </dd>
            <dd className="kpi__note">
              Cobertura del universo municipal publicado para 2027.
            </dd>
          </div>
          <div className="kpi">
            <dt>Información insuficiente</dt>
            <dd data-testid="coverage-insufficient">{summary.insufficient}</dd>
            <dd className="kpi__note">
              No se imputan como cero ni se clasifican como riesgo bajo.
            </dd>
          </div>
          <div className="kpi">
            <dt>Categoría inestable</dt>
            <dd data-testid="unstable-kpi">{unstableValue}</dd>
            <dd className="kpi__note">
              La banda cruza un umbral de riesgo; la etiqueta se muestra como
              inestable. El conteo depende de las filas de predicción.
            </dd>
          </div>
          <div className="kpi">
            <dt>Rango de error histórico de referencia</dt>
            <dd data-testid="historical-band">
              {formatPp(metrics?.bandAmplitudePp, 2)}
            </dd>
            <dd className="kpi__note">
              Amplitud sobre {metrics?.bandErrors ?? 91} errores de la validación
              2021. No es un intervalo de confianza del 90 % ni un intervalo
              causal.
            </dd>
          </div>
        </dl>

        {metrics?.empiricalCoverage2024 ? (
          <p className="source-note" data-testid="empirical-coverage">
            Cobertura empírica 2024: {metrics.empiricalCoverage2024.within} de{" "}
            {metrics.empiricalCoverage2024.n} errores absolutos dentro del rango
            congelado ({Math.round(metrics.empiricalCoverage2024.share * 100)} %).
            Es una comprobación descriptiva; 2024 no ajusta la banda.
          </p>
        ) : null}
        {metrics?.cohort2027.lnCoverageBaseYear ? (
          <p className="source-note" data-testid="ln-coverage">
            Cobertura de lista nominal:{" "}
            {metrics.cohort2027.eligibleLn?.toLocaleString("es-MX") ?? "—"} de{" "}
            {metrics.cohort2027.totalLn?.toLocaleString("es-MX") ?? "—"} personas.
            La base es la LN {metrics.cohort2027.lnCoverageBaseYear}, último
            antecedente observado; no es una proyección de la LN 2027.
          </p>
        ) : null}
        <p className="source-note" data-testid="exclusion-note">
          {predictionsQuery.isPending ? (
            <>
              Exclusiones: cargando el detalle de las filas de predicción. La
              banda es un rango de error histórico de referencia, no una certeza
              de 2027.
            </>
          ) : predictionsQuery.isError ? (
            <>
              Exclusiones: no disponibles porque falló la consulta de
              predicciones. El conteo de cobertura proviene de las métricas del
              modelo y no se sustituye por cero. La banda es un rango de error
              histórico de referencia, no una certeza de 2027.
            </>
          ) : (
            <>
              Exclusiones: {summary.insufficient} municipios no elegibles por{" "}
              {exclusionText}. La banda es un rango de error histórico de
              referencia, no una certeza de 2027.
            </>
          )}
        </p>
      </section>

      <PredictionExplanation
        model={selectedModel}
        territoryId={territoryId}
        predictions={predictions}
      />

      <section className="summary-card" aria-labelledby="prediction-table-heading">
        <div className="card-heading">
          <div>
            <h2 id="prediction-table-heading">Predicciones municipales</h2>
            <p>
              Una fila por municipio. Los valores son estimaciones para 2027 y no
              reemplazan la observación histórica.
            </p>
          </div>
          <span className="status-pill status-pill--neutral">
            Predicción 2027
          </span>
        </div>

        {predictionsQuery.isPending ? (
          <PageState
            variant="loading"
            title="Cargando predicciones 2027"
            message="Consultando las 125 filas publicadas y su calidad."
          />
        ) : predictionsQuery.isError ? (
          <PageState
            variant="error"
            title="No se pudieron cargar las predicciones"
            message={
              predictionsQuery.error instanceof Error
                ? predictionsQuery.error.message
                : "La consulta de predicciones no está disponible."
            }
            action={
              <button
                type="button"
                className="button button--primary"
                onClick={() => void predictionsQuery.refetch()}
              >
                <RefreshCw aria-hidden="true" size={16} strokeWidth={1.8} />
                Reintentar consulta
              </button>
            }
          />
        ) : predictions.length === 0 ? (
          <PageState
            variant="empty"
            title="Sin predicciones publicadas"
            message="La ejecución seleccionada no contiene filas para 2027."
          />
        ) : (
          <>
            {selectedPrediction ? (
              <p className="selection-note">
                Municipio seleccionado en los filtros globales:{" "}
                <strong>
                  {selectedPrediction.municipality_name} ·{" "}
                  {selectedPrediction.municipality_code}
                </strong>
                .
              </p>
            ) : null}

            <div className="prediction-toolbar">
              <div className="filter-field">
                <label htmlFor="risk-filter">Filtrar por riesgo</label>
                <select
                  id="risk-filter"
                  value={riskFilter}
                  onChange={(event) =>
                    setRiskFilter(event.target.value as RiskFilter)
                  }
                >
                  <option value="all">Todos los estados</option>
                  <option value="eligible">Sólo elegibles</option>
                  <option value="insufficient">Información insuficiente</option>
                  <option value="low">Riesgo bajo</option>
                  <option value="medium">Riesgo medio</option>
                  <option value="high">Riesgo alto</option>
                  <option value="unstable">Categoría inestable</option>
                </select>
              </div>
              <p className="table-note" role="status">
                {filtered.length} de {predictions.length} filas visibles.
              </p>
            </div>

            <DataTable
              caption="Predicciones municipales 2027"
              rows={filtered}
              rowKey={(row) => row.territory_id}
              emptyMessage="No hay predicciones que coincidan con el filtro."
              rowProps={(row) =>
                row.territory_id === territoryId
                  ? { className: "is-selected", "aria-current": "true" }
                  : {}
              }
              columns={[
                {
                  key: "name",
                  header: "Municipio",
                  render: (row) => row.municipality_name,
                },
                {
                  key: "code",
                  header: "Código INE",
                  render: (row) => row.municipality_code,
                },
                {
                  key: "prediction",
                  header: "Predicción 2027",
                  align: "right",
                  render: (row) => formatPct(row.estimated_abstention_pct),
                },
                {
                  key: "band",
                  header: "Rango de error histórico",
                  align: "right",
                  render: (row) =>
                    formatRange(
                      row.historical_error_lower_pct,
                      row.historical_error_upper_pct,
                    ),
                },
                {
                  key: "risk",
                  header: "Riesgo",
                  render: (row) => (
                    <RiskBadge
                      risk={asRiskLevel(row.risk)}
                      unstable={row.risk_unstable}
                    />
                  ),
                },
                {
                  key: "stability",
                  header: "Estabilidad",
                  render: (row) => (
                    <span className="stability-note">
                      {!row.eligible
                        ? "No evaluable"
                        : row.risk_unstable
                          ? "Inestable: la banda cruza un umbral"
                          : "Estable en la banda"}
                    </span>
                  ),
                },
              ]}
            />
            <p className="table-note">
              {`Predicción 2027 del modelo ${selectedModel.family}. No es una observación histórica y "Información insuficiente" nunca equivale a cero. La columna de rango es el error histórico de referencia, no una confianza del 90 %.`}
            </p>
          </>
        )}
      </section>
    </div>
  );
}

function PredictionHeading() {
  return (
    <div className="page-heading">
      <p className="eyebrow">Predicción municipal · Jalisco</p>
      <h1>Predicción 2027</h1>
      <p className="page-heading__lead">
        Abstención estimada para 2027, con evidencia de selección del modelo,
        cobertura y exclusiones. Es una predicción condicional, no una
        observación histórica ni una garantía electoral.
      </p>
    </div>
  );
}
