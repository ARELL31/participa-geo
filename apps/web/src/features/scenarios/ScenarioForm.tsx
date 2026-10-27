import { FileWarning } from "lucide-react";
import type { FormEvent } from "react";

import type { PredictionDTO } from "../../lib/api";

export type AssumptionCode =
  | "preventive_exploration"
  | "model_sensitivity";

export type ScenarioFormValues = {
  selectedTerritoryIds: string[];
  reduction: string;
  assumption: AssumptionCode | "";
};

export const ASSUMPTIONS: ReadonlyArray<{
  code: AssumptionCode;
  label: string;
  description: string;
}> = [
  {
    code: "preventive_exploration",
    label: "Exploración preventiva",
    description:
      "Ejercicio aritmético de sensibilidad sobre municipios seleccionados; no representa eficacia causal.",
  },
  {
    code: "model_sensitivity",
    label: "Sensibilidad del modelo",
    description:
      "Compara un cambio hipotético acotado para observar si cambia la clasificación de riesgo.",
  },
];

export function assumptionLabel(code: AssumptionCode | ""): string {
  return ASSUMPTIONS.find((item) => item.code === code)?.label ?? "";
}

type ScenarioFormProps = {
  eligible: PredictionDTO[];
  insufficientCount: number;
  values: ScenarioFormValues;
  error: string | null;
  submitting: boolean;
  onChange(next: Partial<ScenarioFormValues>): void;
  onReview(): void;
};

export function ScenarioForm({
  eligible,
  insufficientCount,
  values,
  error,
  submitting,
  onChange,
  onReview,
}: ScenarioFormProps) {
  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    onReview();
  }

  return (
    <section className="summary-card scenario-form-card" aria-labelledby="scenario-form-heading">
      <div className="card-heading">
        <div>
          <h2 id="scenario-form-heading">Configurar escenario</h2>
          <p>
            La reducción se aplica sólo a los municipios seleccionados. B es
            aritmética hipotética: B = max(0, A − reducción).
          </p>
        </div>
        <span className="status-pill status-pill--neutral">Año objetivo 2027</span>
      </div>

      <form className="scenario-form" onSubmit={handleSubmit} noValidate>
        {error ? (
          <div className="inline-alert inline-alert--warning" role="alert">
            <FileWarning aria-hidden="true" size={20} strokeWidth={1.8} />
            <p>{error}</p>
          </div>
        ) : null}

        <div className="form-field form-field--wide">
          <label htmlFor="scenario-municipalities">Municipios</label>
          <select
            id="scenario-municipalities"
            multiple
            required
            size={10}
            aria-describedby="scenario-municipalities-hint"
            value={values.selectedTerritoryIds}
            onChange={(event) =>
              onChange({
                selectedTerritoryIds: Array.from(
                  event.target.selectedOptions,
                  (option) => option.value,
                ),
              })
            }
          >
            {eligible.map((item) => (
              <option key={item.territory_id} value={item.territory_id}>
                {item.municipality_code} · {item.municipality_name}
              </option>
            ))}
          </select>
          <p id="scenario-municipalities-hint" className="filter-hint">
            Sólo se listan {eligible.length} municipios elegibles. {insufficientCount}{" "}
            municipios con información insuficiente no se pueden seleccionar.
          </p>
        </div>

        <div className="form-field">
          <label htmlFor="scenario-reduction">
            Reducción hipotética (puntos porcentuales)
          </label>
          <input
            id="scenario-reduction"
            type="number"
            inputMode="decimal"
            min={0}
            max={10}
            step={0.1}
            required
            aria-describedby="scenario-reduction-hint"
            value={values.reduction}
            onChange={(event) => onChange({ reduction: event.target.value })}
          />
          <p id="scenario-reduction-hint" className="filter-hint">
            Entre 0 y 10 pp. No se estiman personas ni efectos causales.
          </p>
        </div>

        <div className="form-field">
          <label htmlFor="scenario-assumption">Supuesto</label>
          <select
            id="scenario-assumption"
            required
            aria-describedby="scenario-assumption-hint"
            value={values.assumption}
            onChange={(event) =>
              onChange({
                assumption: event.target.value as AssumptionCode | "",
              })
            }
          >
            <option value="">Seleccione un supuesto</option>
            {ASSUMPTIONS.map((assumption) => (
              <option key={assumption.code} value={assumption.code}>
                {assumption.label}
              </option>
            ))}
          </select>
          <p id="scenario-assumption-hint" className="filter-hint">
            El texto explicativo proviene de un catálogo cerrado y revisado.
          </p>
        </div>

        <div className="scenario-form__actions">
          <button
            type="submit"
            className="button button--primary"
            disabled={submitting}
          >
            {submitting ? "Creando escenario…" : "Crear escenario"}
          </button>
        </div>
        <p className="export-note">
          Las exportaciones del escenario aparecen cuando el resultado queda
          persistido; no se ofrecen botones sin archivo real.
        </p>
      </form>
    </section>
  );
}
