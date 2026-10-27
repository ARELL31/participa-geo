import { Database, ShieldCheck } from "lucide-react";

import { DataTable } from "../../components/DataTable";
import type { ModelDTO } from "../../lib/api";
import {
  featureLabel,
  formatPp,
  formatSignedPp,
  parseModelMetrics,
  type MetricSummary,
  type ModelMetrics,
} from "./modelEvidence";

type ModelRow = {
  family: string;
  selected: boolean;
  validation: MetricSummary;
  test: MetricSummary;
};

function familyLabel(family: string): string {
  if (family === "M0") {
    return "M0 · referencia temporal";
  }
  if (family === "M1") {
    return "M1 · candidato sociodemográfico";
  }
  return family;
}

/**
 * The served M0 family is one feature, not the shared six-field feature order.
 * Only the family that actually serves may claim its production inputs.
 */
function productionFeaturesCopy(
  selectedFamily: string,
  features: string[],
): string {
  if (selectedFamily === "M0") {
    return "1 variable de producción: abstención del mismo tipo (t-6)";
  }
  if (selectedFamily === "M1") {
    const labels = features.map(featureLabel);
    return `${features.length} variables de producción: ${labels.join(", ")}`;
  }
  return "La ejecución publicada no declara sus variables de producción.";
}

function selectionExplanation(
  model: ModelDTO,
  metrics: ModelMetrics | null,
): string {
  const selectedFamily = metrics?.selectedFamily ?? model.family;
  const m0Validation = metrics?.m0.validation.mae ?? null;
  const m1Validation = metrics?.m1.validation.mae ?? null;
  if (selectedFamily === "M0" && m0Validation !== null && m1Validation !== null) {
    return `M0 fue seleccionado porque obtuvo el menor MAE en la validación 2021 (${formatPp(m0Validation)} frente a ${formatPp(m1Validation)} de M1). M1 añade variables sociodemográficas, no fue seleccionado y no se utiliza en producción.`;
  }
  if (selectedFamily === "M1" && m0Validation !== null && m1Validation !== null) {
    return `M1 fue seleccionado en la validación 2021 (${formatPp(m1Validation)} frente a ${formatPp(m0Validation)} de M0).`;
  }
  return "No hay métricas de selección disponibles; esta pantalla no afirma qué familia ganó.";
}

type ModelComparisonProps = {
  models: ModelDTO[];
  selectedModel: ModelDTO;
  onSelectModel(modelRunId: string): void;
  selectDisabled?: boolean;
};

export function ModelComparison({
  models,
  selectedModel,
  onSelectModel,
  selectDisabled = false,
}: ModelComparisonProps) {
  const metrics = parseModelMetrics(selectedModel.metrics);
  const selectedFamily = metrics?.selectedFamily ?? selectedModel.family;
  const rows: ModelRow[] = [
    {
      family: "M0",
      selected: selectedFamily === "M0",
      validation: metrics?.m0.validation ?? { mae: null, bias: null, n: null },
      test: metrics?.m0.test ?? { mae: null, bias: null, n: null },
    },
    {
      family: "M1",
      selected: selectedFamily === "M1",
      validation: metrics?.m1.validation ?? { mae: null, bias: null, n: null },
      test: metrics?.m1.test ?? { mae: null, bias: null, n: null },
    },
  ];
  const description =
    typeof selectedModel.parameters?.description === "string"
      ? selectedModel.parameters.description
      : "Ejecución de modelo publicada.";
  const limitations = selectedModel.limitations ?? [];

  return (
    <section className="summary-card model-evidence" aria-labelledby="model-evidence-heading">
      <div className="card-heading">
        <div>
          <h2 id="model-evidence-heading">Evidencia del modelo</h2>
          <p>
            La familia se eligió con la validación 2021 y se contrastó con la
            prueba 2024. Ninguno de los dos periodos es una certeza sobre 2027.
          </p>
        </div>
        <span className="status-pill status-pill--neutral">
          <ShieldCheck aria-hidden="true" size={16} strokeWidth={1.8} />
          {selectedFamily} seleccionado
        </span>
      </div>

      <div className="model-evidence__selector">
        <div className="filter-field">
          <label htmlFor="model-run-selector">Ejecución de modelo</label>
          <select
            id="model-run-selector"
            value={selectedModel.model_run_id}
            disabled={selectDisabled || models.length === 0}
            onChange={(event) => onSelectModel(event.target.value)}
          >
            {models.length === 0 ? (
              <option value="">Sin ejecuciones publicadas</option>
            ) : (
              models.map((model) => (
                <option key={model.model_run_id} value={model.model_run_id}>
                  {familyLabel(model.family)} · {model.reference_date}
                </option>
              ))
            )}
          </select>
          <p className="filter-hint">
            Se muestran sólo ejecuciones ya entrenadas y persistidas.
          </p>
        </div>

        <dl className="model-evidence__facts">
          <div>
            <dt>Año objetivo</dt>
            <dd>{selectedModel.target_year} · fijo</dd>
          </div>
          <div>
            <dt>Corte de referencia</dt>
            <dd>{selectedModel.reference_date}</dd>
          </div>
          <div>
            <dt>Variables en producción</dt>
            <dd>
              {productionFeaturesCopy(
                selectedFamily,
                selectedModel.features ?? [],
              )}
            </dd>
          </div>
        </dl>
      </div>

      <div className="model-evidence__description">
        <Database aria-hidden="true" size={20} strokeWidth={1.8} />
        <p>{description}</p>
      </div>

      <p className="model-evidence__selection" data-testid="selection-explanation">
        {selectionExplanation(selectedModel, metrics)}
      </p>
      <p className="model-evidence__note">
        {selectedFamily === "M0" ? (
          <>
            En producción, M0 no utiliza variables sociodemográficas; su
            estimación es la abstención observada del mismo municipio y tipo de
            elección en 2021. La validación 2021 se usó para elegir la familia.
            La prueba 2024 es evidencia posterior y no garantiza el desempeño
            futuro.
          </>
        ) : selectedFamily === "M1" ? (
          <>
            M1 usa las seis variables candidatas, incluidas las proporciones
            sociodemográficas. La validación 2021 se usó para elegir la familia;
            la prueba 2024 es evidencia posterior y no garantiza el desempeño
            futuro.
          </>
        ) : (
          <>
            La ejecución no declara qué variables usa en producción. No se
            infieren a partir del orden compartido de variables.
          </>
        )}
      </p>

      <DataTable
        caption="Métricas por familia y periodo"
        rows={rows}
        rowKey={(row) => row.family}
        emptyMessage="No hay métricas de modelo publicadas."
        columns={[
          {
            key: "family",
            header: "Familia",
            render: (row) => <strong>{row.family}</strong>,
          },
          {
            key: "state",
            header: "Estado",
            render: (row) =>
              row.selected ? "Seleccionado" : "Candidato · no seleccionado",
          },
          {
            key: "validationMae",
            header: `MAE validación ${metrics?.validationYear ?? 2021}`,
            align: "right",
            render: (row) => formatPp(row.validation.mae),
          },
          {
            key: "testMae",
            header: `MAE prueba ${metrics?.testYear ?? 2024}`,
            align: "right",
            render: (row) => formatPp(row.test.mae),
          },
          {
            key: "validationBias",
            header: `Sesgo validación ${metrics?.validationYear ?? 2021}`,
            align: "right",
            render: (row) => formatSignedPp(row.validation.bias),
          },
          {
            key: "testBias",
            header: `Sesgo prueba ${metrics?.testYear ?? 2024}`,
            align: "right",
            render: (row) => formatSignedPp(row.test.bias),
          },
        ]}
      />

      {limitations.length > 0 ? (
        <div className="model-evidence__limitations">
          <h3>Límites declarados</h3>
          <ul>
            {limitations.map((limitation) => (
              <li key={limitation}>{limitation}</li>
            ))}
          </ul>
        </div>
      ) : null}
    </section>
  );
}
