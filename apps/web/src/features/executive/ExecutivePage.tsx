import { useQuery } from "@tanstack/react-query";
import { ArrowRight, Gauge, RefreshCw } from "lucide-react";
import type { MouseEvent } from "react";

import { navigate, pathWithCurrentFilters } from "../../app/navigation";
import { DataTable } from "../../components/DataTable";
import { GeographyNotice } from "../../components/GeographyNotice";
import { PageState } from "../../components/PageState";
import { RiskBadge } from "../../components/RiskBadge";
import {
  fetchModels,
  fetchPredictions,
  fetchRecommendations,
  queryKeys,
} from "../../lib/api";
import {
  asRiskLevel,
  formatPct,
  formatPp,
  parseModelMetrics,
  summarizePredictions,
} from "../prediction/modelEvidence";

function moduleLink(
  event: MouseEvent<HTMLAnchorElement>,
  path: string,
): void {
  if (
    event.metaKey ||
    event.ctrlKey ||
    event.shiftKey ||
    event.altKey ||
    event.button !== 0
  ) {
    return;
  }
  event.preventDefault();
  navigate(pathWithCurrentFilters(path));
}

type RiskRow = {
  key: "low" | "medium" | "high" | "insufficient";
  label: string;
  count: number;
  share: string;
};

export function ExecutivePage() {
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

  const recommendationsQuery = useQuery({
    queryKey: queryKeys.recommendations(model?.model_run_id ?? null),
    queryFn: ({ signal }) =>
      fetchRecommendations({
        modelRunId: model?.model_run_id ?? null,
        signal,
      }),
    enabled: Boolean(model),
    staleTime: 60_000,
  });

  if (modelsQuery.isPending || predictionsQuery.isPending) {
    return (
      <div className="page executive-page">
        <ExecutiveHeading />
        <PageState
          variant="loading"
          title="Cargando resumen ejecutivo"
          message="Agregando cobertura, señales de riesgo y evidencia del modelo desde la API."
        />
      </div>
    );
  }

  if (modelsQuery.isError || predictionsQuery.isError) {
    return (
      <div className="page executive-page">
        <ExecutiveHeading />
        <PageState
          variant="error"
          headingLevel={1}
          title="No se pudo cargar el panel ejecutivo"
          message={
            modelsQuery.error instanceof Error
              ? modelsQuery.error.message
              : predictionsQuery.error instanceof Error
                ? predictionsQuery.error.message
                : "La consulta agregada no está disponible."
          }
          action={
            <button
              type="button"
              className="button button--primary"
              onClick={() => {
                void modelsQuery.refetch();
                void predictionsQuery.refetch();
              }}
            >
              <RefreshCw aria-hidden="true" size={16} strokeWidth={1.8} />
              Reintentar consulta
            </button>
          }
        />
      </div>
    );
  }

  const predictions = predictionsQuery.data?.items ?? [];
  if (!model || predictions.length === 0) {
    return (
      <div className="page executive-page">
        <ExecutiveHeading />
        <PageState
          variant="empty"
          headingLevel={1}
          title="Sin indicadores publicados"
          message="No hay una predicción 2027 persistida. El panel no muestra cifras de ejemplo."
        />
      </div>
    );
  }

  const metrics = parseModelMetrics(model.metrics);
  const summary = summarizePredictions(predictions, metrics);
  const coverage = summary.total > 0 ? summary.eligible / summary.total : 0;
  const highRisk = predictions.filter(
    (item) => item.eligible && item.risk === "high",
  );
  const topSignals = [...predictions]
    .filter((item) => item.eligible)
    .sort(
      (a, b) =>
        (b.estimated_abstention_pct ?? 0) - (a.estimated_abstention_pct ?? 0),
    )
    .slice(0, 5);
  const recommendations = recommendationsQuery.data?.items ?? [];
  const recommendationByTerritory = new Map(
    recommendations.map((item) => [item.territory_id, item]),
  );
  const riskRows: RiskRow[] = (
    ["high", "medium", "low", "insufficient"] as const
  ).map((key) => {
    const count = predictions.filter((item) =>
      key === "insufficient"
        ? !item.eligible
        : item.eligible && item.risk === key,
    ).length;
    return {
      key,
      label:
        key === "high"
          ? "Riesgo alto"
          : key === "medium"
            ? "Riesgo medio"
            : key === "low"
              ? "Riesgo bajo"
              : "Información insuficiente",
      count,
      share:
        predictions.length > 0
          ? `${((count / predictions.length) * 100).toFixed(1)} %`
          : "0.0 %",
    };
  });

  return (
    <div className="page executive-page">
      <ExecutiveHeading />
      <GeographyNotice />

      <section className="summary-card" aria-labelledby="executive-summary-heading">
        <div className="card-heading">
          <div>
            <h2 id="executive-summary-heading">Resumen 2027 · Jalisco</h2>
            <p>
              Indicadores agregados desde las predicciones publicadas. No
              identifican personas ni sustituyen la observación histórica.
            </p>
          </div>
          <span className="status-pill status-pill--neutral">
            <Gauge aria-hidden="true" size={16} strokeWidth={1.8} />
            Predicción 2027
          </span>
        </div>

        <dl className="kpi-grid">
          <div className="kpi">
            <dt>Cobertura de predicción</dt>
            <dd>
              {summary.eligible} de {summary.total}
            </dd>
            <p className="kpi__note">
              {(coverage * 100).toFixed(1)} % de municipios elegibles.
            </p>
          </div>
          <div className="kpi">
            <dt>Riesgo alto</dt>
            <dd data-testid="executive-high-risk">{highRisk.length}</dd>
            <p className="kpi__note">
              Abstención estimada de 50 % o más entre elegibles.
            </p>
          </div>
          <div className="kpi">
            <dt>Información insuficiente</dt>
            <dd>{summary.insufficient}</dd>
            <p className="kpi__note">
              No se imputan como cero ni como riesgo bajo.
            </p>
          </div>
          <div className="kpi">
            <dt>Categoría inestable</dt>
            <dd>
              {summary.unstable} de {summary.eligible}
            </dd>
            <p className="kpi__note">
              La banda histórica cruza un umbral de riesgo.
            </p>
          </div>
        </dl>
      </section>

      <div className="executive-grid">
        <section className="summary-card" aria-labelledby="model-summary-heading">
          <div className="card-heading">
            <div>
              <h2 id="model-summary-heading">Modelo publicado</h2>
              <p>
                Evidencia separada de validación 2021 y prueba 2024; no son una
                certeza sobre 2027.
              </p>
            </div>
            <span className="status-pill status-pill--neutral">
              {model.family} seleccionado
            </span>
          </div>
          <dl className="executive-facts">
            <div>
              <dt>Familia</dt>
              <dd>{model.family} · referencia temporal</dd>
            </div>
            <div>
              <dt>MAE validación 2021</dt>
              <dd>{formatPp(metrics?.m0.validation.mae)}</dd>
            </div>
            <div>
              <dt>MAE prueba 2024</dt>
              <dd>{formatPp(metrics?.m0.test.mae)}</dd>
            </div>
            <div>
              <dt>Rango de error histórico de referencia</dt>
              <dd>{formatPp(metrics?.bandAmplitudePp)}</dd>
            </div>
          </dl>
          <p className="executive-note">
            M0 no utiliza variables sociodemográficas en producción. El
            candidato M1 perdió la validación 2021 y no se sirve.
          </p>
          <a
            className="button button--secondary"
            href={pathWithCurrentFilters("/prediction")}
            onClick={(event) => moduleLink(event, "/prediction")}
          >
            Ver evidencia y predicciones
            <ArrowRight aria-hidden="true" size={16} strokeWidth={1.8} />
          </a>
        </section>

        <section className="summary-card" aria-labelledby="distribution-heading">
          <div className="card-heading">
            <div>
              <h2 id="distribution-heading">Distribución de riesgo 2027</h2>
              <p>Conteo por categoría publicada, con etiqueta e icono.</p>
            </div>
          </div>
          <DataTable
            caption="Distribución de riesgo predicho 2027"
            rows={riskRows}
            rowKey={(row) => row.key}
            emptyMessage="Sin categorías publicadas."
            columns={[
              {
                key: "category",
                header: "Categoría",
                render: (row) => <RiskBadge risk={row.key} />,
              },
              {
                key: "count",
                header: "Municipios",
                align: "right",
                render: (row) => row.count,
              },
              {
                key: "share",
                header: "Participación",
                align: "right",
                render: (row) => row.share,
              },
            ]}
          />
        </section>
      </div>

      <section className="summary-card" aria-labelledby="signals-heading">
        <div className="card-heading">
          <div>
            <h2 id="signals-heading">Señales prioritarias</h2>
            <p>
              Cinco municipios elegibles con mayor abstención estimada. Es una
              señal preventiva, no una asignación de recursos.
            </p>
          </div>
          <a
            className="button button--secondary"
            href={pathWithCurrentFilters("/scenarios")}
            onClick={(event) => moduleLink(event, "/scenarios")}
          >
            Comparar escenario
            <ArrowRight aria-hidden="true" size={16} strokeWidth={1.8} />
          </a>
        </div>
        <DataTable
          caption="Señales prioritarias de abstención estimada 2027"
          rows={topSignals}
          rowKey={(row) => row.territory_id}
          emptyMessage="No hay señales elegibles publicadas."
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
              key: "estimate",
              header: "Abstención estimada 2027",
              align: "right",
              render: (row) => formatPct(row.estimated_abstention_pct),
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
              key: "recommendation",
              header: "Recomendación preventiva",
              render: (row) => {
                if (recommendationsQuery.isPending) return "Cargando…";
                if (recommendationsQuery.isError) return "No disponible";
                return (
                  recommendationByTerritory.get(row.territory_id)
                    ?.recommendations[0]?.title ?? "Sin recomendación"
                );
              },
            },
          ]}
        />
        <p className="source-note">
          Fuente: ejecución {model.model_run_id} · corte {model.reference_date}.
          Recomendaciones preventivas: reglas{" "}
          {recommendations[0]?.rules_version ?? "no disponibles"}. Reportes y
          exportaciones: Disponible en T9.
        </p>
      </section>
    </div>
  );
}

function ExecutiveHeading() {
  return (
    <div className="page-heading">
      <p className="eyebrow">Observatorio · Jalisco</p>
      <h1>Panel ejecutivo</h1>
      <p className="page-heading__lead">
        Cobertura, señales de riesgo y evidencia del modelo para 2027. Los
        indicadores son agregados municipales y no identifican personas.
      </p>
    </div>
  );
}
