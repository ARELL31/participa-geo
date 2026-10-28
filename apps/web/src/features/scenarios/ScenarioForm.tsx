import { FileWarning } from "lucide-react";
import { useMemo, useState, type FormEvent } from "react";

import type { StateCode } from "../../app/filters";
import { MEXICAN_STATES } from "../../components/LevelSwitcher";
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
  stateCode: StateCode;
  eligible: PredictionDTO[];
  insufficientCount: number;
  values: ScenarioFormValues;
  error: string | null;
  submitting: boolean;
  onStateChange(stateCode: StateCode): void;
  onChange(next: Partial<ScenarioFormValues>): void;
  onReview(): void;
};

export function ScenarioForm({
  stateCode,
  eligible,
  insufficientCount,
  values,
  error,
  submitting,
  onStateChange,
  onChange,
  onReview,
}: ScenarioFormProps) {
  const [search, setSearch] = useState("");
  const visibleEligible = useMemo(() => {
    const normalizedSearch = search
      .trim()
      .toLocaleLowerCase("es-MX")
      .normalize("NFD")
      .replace(/[\u0300-\u036f]/g, "");
    return eligible
      .filter((item) => {
        if (!normalizedSearch) return true;
        const text = `${item.municipality_code ?? ""} ${item.municipality_name ?? ""}`
          .toLocaleLowerCase("es-MX")
          .normalize("NFD")
          .replace(/[\u0300-\u036f]/g, "");
        return text.includes(normalizedSearch);
      })
      .slice(0, 50);
  }, [eligible, search]);

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
          <label htmlFor="scenario-state">Entidad de municipios</label>
          <select
            id="scenario-state"
            value={stateCode}
            onChange={(event) => onStateChange(event.target.value as StateCode)}
          >
            {MEXICAN_STATES.map(([code, name]) => (
              <option key={code} value={code}>
                {name} · {code}
              </option>
            ))}
          </select>
        </div>

        <div className="form-field form-field--wide">
          <label htmlFor="scenario-municipalities">Municipios</label>
          <label className="visually-hidden" htmlFor="scenario-municipality-search">
            Buscar municipio
          </label>
          <input
            id="scenario-municipality-search"
            type="search"
            placeholder="Buscar por nombre o código"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
          />
          <select
            id="scenario-municipalities"
            multiple
            required
            size={10}
            aria-describedby="scenario-municipalities-hint"
            value={values.selectedTerritoryIds}
            onChange={(event) =>
              onChange({
                selectedTerritoryIds: [
                  ...values.selectedTerritoryIds.filter(
                    (id) => !visibleEligible.some((item) => item.territory_id === id),
                  ),
                  ...Array.from(event.target.selectedOptions, (option) => option.value),
                ],
              })
            }
          >
            {visibleEligible.map((item) => (
              <option key={item.territory_id} value={item.territory_id}>
                {item.municipality_code} · {item.municipality_name}
              </option>
            ))}
          </select>
          <p id="scenario-municipalities-hint" className="filter-hint">
            Mostrando hasta 50 de {eligible.length} municipios elegibles de la entidad seleccionada. {insufficientCount}{" "}
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
