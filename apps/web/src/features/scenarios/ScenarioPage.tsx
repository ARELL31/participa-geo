import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, RefreshCw } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";

import { GeographyNotice } from "../../components/GeographyNotice";
import { PageState } from "../../components/PageState";
import {
  createScenario,
  fetchModels,
  fetchMunicipalityFeatures,
  fetchPredictions,
  fetchScenario,
  queryKeys,
  type PredictionDTO,
  type ScenarioDTO,
  type ScenarioRequest,
} from "../../lib/api";
import {
  ScenarioForm,
  assumptionLabel,
  type ScenarioFormValues,
} from "./ScenarioForm";
import { ScenarioMaps } from "./ScenarioMaps";
import { ScenarioTable } from "./ScenarioTable";
import { ExportActions } from "../reports/ExportActions";

const EMPTY_FORM: ScenarioFormValues = {
  selectedTerritoryIds: [],
  reduction: "3",
  assumption: "",
};

/** Scenario geometry is the latest reference layer; the 2027 target is fixed. */
const MAP_REFERENCE_YEAR = 2024 as const;

function readScenarioId(): string | null {
  return new URLSearchParams(window.location.search).get("scenario_id");
}

function eligiblePredictions(predictions: PredictionDTO[]): PredictionDTO[] {
  return predictions.filter(
    (item) =>
      item.eligible &&
      typeof item.estimated_abstention_pct === "number" &&
      Number.isFinite(item.estimated_abstention_pct),
  );
}

function validateForm(values: ScenarioFormValues): string | null {
  if (values.selectedTerritoryIds.length === 0) {
    return "Seleccione al menos un municipio elegible antes de continuar.";
  }
  if (values.selectedTerritoryIds.length > 125) {
    return "La selección no puede superar 125 municipios.";
  }
  const reduction = Number(values.reduction);
  if (
    values.reduction.trim() === "" ||
    !Number.isFinite(reduction) ||
    reduction < 0 ||
    reduction > 10
  ) {
    return "La reducción debe ser un número entre 0 y 10 puntos porcentuales.";
  }
  if (!values.assumption) {
    return "Seleccione un supuesto del catálogo antes de continuar.";
  }
  return null;
}

function replaceScenarioIdInUrl(scenarioId: string): void {
  const url = new URL(window.location.href);
  url.searchParams.set("scenario_id", scenarioId);
  window.history.replaceState(null, "", `${url.pathname}${url.search}${url.hash}`);
}

export function ScenarioPage() {
  const queryClient = useQueryClient();
  const [scenarioId, setScenarioId] = useState<string | null>(readScenarioId);
  const [values, setValues] = useState<ScenarioFormValues>(EMPTY_FORM);
  const [formError, setFormError] = useState<string | null>(null);
  const [reviewing, setReviewing] = useState(false);
  const confirmHeadingRef = useRef<HTMLHeadingElement | null>(null);
  const resultHeadingRef = useRef<HTMLHeadingElement | null>(null);

  const modelsQuery = useQuery({
    queryKey: queryKeys.models(),
    queryFn: ({ signal }) => fetchModels({ signal }),
    staleTime: 5 * 60_000,
  });
  const model = modelsQuery.data?.items[0];

  const predictionsQuery = useQuery({
    queryKey: queryKeys.predictions(model?.model_run_id ?? null),
    queryFn: ({ signal }) =>
      fetchPredictions({
        modelRunId: model?.model_run_id ?? null,
        signal,
      }),
    enabled: Boolean(model),
    staleTime: 60_000,
  });

  const scenarioQuery = useQuery({
    queryKey: queryKeys.scenario(scenarioId),
    queryFn: ({ signal }) => fetchScenario(scenarioId!, signal),
    enabled: Boolean(scenarioId),
    retry: false,
    staleTime: 5 * 60_000,
  });

  const mutation = useMutation({
    mutationFn: (request: ScenarioRequest) => createScenario(request),
    onSuccess: (created: ScenarioDTO) => {
      queryClient.setQueryData(queryKeys.scenario(created.scenario_id), created);
      setScenarioId(created.scenario_id);
      replaceScenarioIdInUrl(created.scenario_id);
      setReviewing(false);
      setFormError(null);
    },
    onError: () => {
      // Keep every form value intact so the user can correct the request.
      setReviewing(false);
    },
  });

  const scenario = mutation.data ?? scenarioQuery.data;
  const scenarioIdValue = scenario?.scenario_id ?? null;
  const predictions = useMemo(
    () => predictionsQuery.data?.items ?? [],
    [predictionsQuery.data],
  );
  const eligible = useMemo(
    () => eligiblePredictions(predictions),
    [predictions],
  );
  const insufficientCount = predictions.length - eligible.length;

  const featuresQuery = useQuery({
    queryKey: queryKeys.municipalFeatures(MAP_REFERENCE_YEAR),
    queryFn: ({ signal }) =>
      fetchMunicipalityFeatures(MAP_REFERENCE_YEAR, signal),
    enabled: Boolean(scenario),
    staleTime: 60_000,
  });

  useEffect(() => {
    if (reviewing) confirmHeadingRef.current?.focus();
  }, [reviewing]);

  useEffect(() => {
    if (scenarioIdValue) resultHeadingRef.current?.focus();
  }, [scenarioIdValue]);

  function handleChange(next: Partial<ScenarioFormValues>) {
    mutation.reset();
    setValues((previous) => ({ ...previous, ...next }));
    setFormError(null);
    setReviewing(false);
  }

  function buildRequest(): ScenarioRequest | null {
    if (!model) return null;
    return {
      model_run_id: model.model_run_id,
      target_year: 2027,
      territory_ids: values.selectedTerritoryIds,
      reduction_pp: Number(values.reduction),
      assumption_code: values.assumption || "preventive_exploration",
    };
  }

  function handleReview() {
    const error = validateForm(values);
    if (error) {
      setFormError(error);
      setReviewing(false);
      return;
    }
    mutation.reset();
    setFormError(null);
    setReviewing(true);
  }

  function handleConfirm() {
    const request = buildRequest();
    if (!request || !values.assumption) {
      setFormError(validateForm(values) ?? "Seleccione un supuesto válido.");
      setReviewing(false);
      return;
    }
    if (!validateForm(values)) {
      mutation.mutate(request);
    }
  }

  const selectedRows = values.selectedTerritoryIds
    .map((id) => predictions.find((item) => item.territory_id === id))
    .filter((item): item is PredictionDTO => Boolean(item));

  if (modelsQuery.isPending) {
    return (
      <div className="page scenario-page">
        <ScenarioHeading />
        <PageState
          variant="loading"
          title="Preparando el simulador municipal"
          message="Consultando la ejecución de modelo publicada."
        />
      </div>
    );
  }

  if (modelsQuery.isError) {
    return (
      <div className="page scenario-page">
        <ScenarioHeading />
        <PageState
          variant="error"
          headingLevel={1}
          title="No se pudo preparar el simulador"
          message={
            modelsQuery.error instanceof Error
              ? modelsQuery.error.message
              : "La consulta de modelos no está disponible."
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

  if (!model) {
    return (
      <div className="page scenario-page">
        <ScenarioHeading />
        <PageState
          variant="empty"
          headingLevel={1}
          title="Sin modelo publicado"
          message="No hay una ejecución de modelo publicada para 2027. No se inventan escenarios ni cifras de ejemplo."
        />
      </div>
    );
  }

  if (predictionsQuery.isPending) {
    return (
      <div className="page scenario-page">
        <ScenarioHeading />
        <PageState
          variant="loading"
          title="Preparando el simulador municipal"
          message="Cargando los municipios elegibles para 2027."
        />
      </div>
    );
  }

  if (predictionsQuery.isError) {
    return (
      <div className="page scenario-page">
        <ScenarioHeading />
        <PageState
          variant="error"
          headingLevel={1}
          title="No se pudo preparar el simulador"
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
      </div>
    );
  }

  if (eligible.length === 0) {
    return (
      <div className="page scenario-page">
        <ScenarioHeading />
        <PageState
          variant="empty"
          headingLevel={1}
          title="Sin municipios elegibles"
          message="No hay predicciones elegibles para 2027. No se inventan escenarios ni cifras de ejemplo."
        />
      </div>
    );
  }

  return (
    <div className="page scenario-page">
      <ScenarioHeading />
      <GeographyNotice />

      <section className="scenario-warning" aria-labelledby="scenario-warning-heading">
        <AlertTriangle aria-hidden="true" size={20} strokeWidth={1.8} />
        <div>
          <h2 id="scenario-warning-heading" className="visually-hidden">
            Advertencia del simulador
          </h2>
          <p>
            <strong>Escenario hipotético — no implica efecto causal</strong>. B se
            calcula con aritmética acotada sobre A; no estima personas,
            presupuesto ni eficacia de una intervención.
          </p>
        </div>
      </section>

      <ScenarioForm
        eligible={eligible}
        insufficientCount={insufficientCount}
        values={values}
        error={
          formError ??
          (mutation.isError && mutation.error instanceof Error
            ? mutation.error.message
            : null)
        }
        submitting={mutation.isPending}
        onChange={handleChange}
        onReview={handleReview}
      />

      {reviewing ? (
        <section
          className="summary-card scenario-confirm"
          aria-labelledby="scenario-confirm-heading"
        >
          <h2
            id="scenario-confirm-heading"
            ref={confirmHeadingRef}
            tabIndex={-1}
          >
            Confirme el escenario
          </h2>
          <p>
            Revise los supuestos antes de guardar. La creación es una sola
            transacción y no modifica la historia ni la predicción publicada.
          </p>
          <dl className="confirm-grid">
            <div>
              <dt>Municipios seleccionados</dt>
              <dd>Municipios seleccionados: {selectedRows.length}</dd>
            </div>
            <div>
              <dt>Reducción solicitada</dt>
              <dd>Reducción solicitada: {Number(values.reduction)} pp</dd>
            </div>
            <div>
              <dt>Supuesto</dt>
              <dd>Supuesto: {assumptionLabel(values.assumption)}</dd>
            </div>
            <div>
              <dt>Año objetivo</dt>
              <dd>Año objetivo: 2027 · fijo</dd>
            </div>
          </dl>
          <div className="scenario-confirm__rows">
            <h3>Municipios incluidos</h3>
            <ul>
              {selectedRows.map((row) => (
                <li key={row.territory_id}>
                  {row.municipality_code} · {row.municipality_name}
                </li>
              ))}
            </ul>
          </div>
          <div className="scenario-form__actions">
            <button
              type="button"
              className="button button--primary"
              disabled={mutation.isPending}
              onClick={handleConfirm}
            >
              Confirmar y crear escenario
            </button>
            <button
              type="button"
              className="button button--secondary"
              onClick={() => setReviewing(false)}
            >
              Volver a editar
            </button>
          </div>
        </section>
      ) : null}

      {scenarioId && !scenario && scenarioQuery.isPending ? (
        <PageState
          variant="loading"
          title="Cargando escenario persistido"
          message="Recuperando la comparación A/B desde el identificador compartido."
        />
      ) : null}

      {scenarioId && !scenario && scenarioQuery.isError ? (
        <PageState
          variant="error"
          title="No se pudo cargar el escenario"
          message={
            scenarioQuery.error instanceof Error
              ? scenarioQuery.error.message
              : "El identificador del escenario no está disponible."
          }
        />
      ) : null}

      {scenario ? (
        <div className="scenario-result">
          <section className="summary-card" aria-labelledby="scenario-result-heading">
            <div className="card-heading">
              <div>
                <h2
                  id="scenario-result-heading"
                  ref={resultHeadingRef}
                  tabIndex={-1}
                >
                  Resultado persistido
                </h2>
                <p>
                  Comparación A/B guardada con supuestos, versión de reglas y
                  hashes de entrada.
                </p>
              </div>
              <span className="status-pill status-pill--neutral">2027</span>
            </div>

            <p className="scenario-result__warning">
              <strong>Escenario hipotético — no implica efecto causal</strong>. La
              comparación no cambia la observación histórica de Inteligencia
              territorial ni la predicción publicada.
            </p>

            <dl className="kpi-grid">
              <div className="kpi">
                <dt>Reducción solicitada</dt>
                <dd>{scenario.requested_reduction_pp.toFixed(1)} pp</dd>
                <dd className="kpi__note">
                  Sólo en municipios seleccionados.
                </dd>
              </div>
              <div className="kpi">
                <dt>Municipios seleccionados</dt>
                <dd>{scenario.selected_territory_ids.length}</dd>
                <dd className="kpi__note">
                  De {scenario.results.length} resultados persistidos.
                </dd>
              </div>
              <div className="kpi">
                <dt>Supuesto</dt>
                <dd className="kpi__text">
                  {assumptionLabel(scenario.assumption_code)}
                </dd>
                <dd className="kpi__note">
                  Versión {scenario.assumption_version} · reglas{" "}
                  {scenario.rules_version}.
                </dd>
              </div>
              <div className="kpi">
                <dt>Banda A/B</dt>
                <dd className="kpi__text">Error histórico de referencia</dd>
                <dd className="kpi__note">
                  No es un intervalo de confianza ni causal.
                </dd>
              </div>
            </dl>

            <p className="scenario-result__rationale">
              {scenario.rationale_text}
            </p>
            <p className="scenario-result__band">
              {scenario.error_band_label}
            </p>
            <p className="scenario-result__share">
              El identificador del escenario está en la dirección de esta página;
              use esa URL para compartirlo o recuperarlo.
            </p>
            <p className="scenario-result__id">
              Escenario persistido · <code>{scenario.scenario_id}</code>
            </p>
          </section>

          <section className="summary-card" aria-labelledby="scenario-exports-heading">
            <div className="card-heading">
              <div>
                <h2 id="scenario-exports-heading">Exportar este escenario</h2>
                <p>
                  Descargue los 125 resultados persistidos, el GeoJSON con la
                  referencia 2025, un PDF del escenario o los mapas A/B generados
                  por GeoServer. Los mapas conservan la misma leyenda y el mismo
                  corte; si GIS falla, la exportación falla de forma explícita.
                </p>
              </div>
              <span className="status-pill status-pill--neutral">A/B</span>
            </div>
            <ExportActions
              caption="Exportaciones del escenario persistido"
              request={{ scenario_id: scenario.scenario_id }}
              actions={[
                {
                  kind: "scenario_csv",
                  label: "Exportar CSV",
                  description:
                    "CSV con A/B, bandas, riesgo, supuestos y hashes del escenario.",
                },
                {
                  kind: "scenario_geojson",
                  label: "Exportar GeoJSON",
                  description:
                    "125 geometrías EPSG:4326 de la referencia 2025-12-15.",
                },
                {
                  kind: "scenario_pdf",
                  label: "Exportar PDF",
                  description:
                    "Resumen y anexo de los 125 resultados municipales.",
                },
                {
                  kind: "scenario_map_png",
                  label: "Mapa PNG",
                  description:
                    "Mapa A/B compuesto desde GeoServer, 1200×900 por panel.",
                },
                {
                  kind: "scenario_map_pdf",
                  label: "Mapa PDF",
                  description:
                    "Mapa A/B en PDF con fuente, corte, modelo y supuestos.",
                },
              ]}
            />
          </section>

          <ScenarioMaps
            scenario={scenario}
            features={featuresQuery.data}
            featuresLoading={featuresQuery.isPending}
            featuresError={featuresQuery.isError}
          />

          <ScenarioTable scenario={scenario} />
        </div>
      ) : null}
    </div>
  );
}

function ScenarioHeading() {
  return (
    <div className="page-heading">
      <p className="eyebrow">Simulador municipal · Jalisco</p>
      <h1>Escenarios hipotéticos</h1>
      <p className="page-heading__lead">
        Compare la predicción publicada 2027 (A) con una reducción aritmética
        acotada (B) sobre municipios elegibles. Los escenarios son hipotéticos y
        no identifican efectos causales.
      </p>
    </div>
  );
}
