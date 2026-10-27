import { DataTable } from "../../components/DataTable";
import { RiskBadge } from "../../components/RiskBadge";
import type { ScenarioDTO, ScenarioResultDTO } from "../../lib/api";

function value(value: number | null | undefined): string {
  return typeof value === "number" && Number.isFinite(value)
    ? `${value.toFixed(1)} %`
    : "Información insuficiente";
}

function difference(row: ScenarioResultDTO): string {
  if (
    row.baseline_abstention_pct === null ||
    row.baseline_abstention_pct === undefined ||
    row.hypothetical_abstention_pct === null ||
    row.hypothetical_abstention_pct === undefined
  ) {
    return "—";
  }
  if (!row.selected) return "Sin cambio";
  if (row.effective_reduction_pp === 0) return "Sin cambio";
  return `-${row.effective_reduction_pp.toFixed(1)} pp`;
}

type ScenarioTableProps = {
  scenario: ScenarioDTO;
};

export function ScenarioTable({ scenario }: ScenarioTableProps) {
  return (
    <section className="summary-card" aria-labelledby="scenario-table-heading">
      <div className="card-heading">
        <div>
          <h2 id="scenario-table-heading">Comparación A/B por municipio</h2>
          <p>
            A es la predicción publicada 2027. B es el ejercicio hipotético del
            municipio seleccionado; los no seleccionados conservan A.
          </p>
        </div>
        <span className="status-pill status-pill--neutral">
          {scenario.results.filter((row) => row.selected).length} seleccionados
        </span>
      </div>

      <DataTable
        caption="Comparación A/B por municipio"
        rows={scenario.results}
        rowKey={(row) => row.territory_id}
        emptyMessage="El escenario no contiene resultados municipales."
        rowProps={(row) =>
          row.selected ? { className: "is-selected" } : {}
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
            key: "baseline",
            header: "A · Abstención 2027",
            align: "right",
            render: (row) => value(row.baseline_abstention_pct),
          },
          {
            key: "hypothetical",
            header: "B · Escenario",
            align: "right",
            render: (row) => value(row.hypothetical_abstention_pct),
          },
          {
            key: "difference",
            header: "Diferencia",
            align: "right",
            render: (row) => difference(row),
          },
          {
            key: "riskA",
            header: "Riesgo A",
            render: (row) => (
              <RiskBadge
                risk={row.risk_a}
                unstable={row.risk_a_unstable}
              />
            ),
          },
          {
            key: "riskB",
            header: "Riesgo B",
            render: (row) => (
              <RiskBadge
                risk={row.risk_b}
                unstable={row.risk_b_unstable}
              />
            ),
          },
          {
            key: "selected",
            header: "Selección",
            render: (row) => (row.selected ? "Seleccionado" : "No seleccionado"),
          },
        ]}
      />

      <p className="table-note">
        B = max(0, A − reducción solicitada) sólo en municipios seleccionados.
        Los valores insuficientes permanecen como “Información insuficiente” y
        nunca se convierten en cero. El rango A/B es un rango de error histórico
        de referencia; no es un intervalo causal.
      </p>
    </section>
  );
}
