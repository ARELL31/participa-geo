import { ArrowDown, ArrowRight, ArrowUp } from "lucide-react";

import { DataTable } from "../../components/DataTable";
import type { ModelDTO } from "../../lib/api";
import {
  coefficientDirection,
  coefficientUnit,
  featureLabel,
  formatSignedCoefficient,
  parseCandidateM1,
} from "./modelEvidence";

type CandidateRow = {
  feature: string;
  label: string;
  coefficient: number;
  direction: string;
  unit: string;
};

function DirectionIcon({ direction }: { direction: string }) {
  if (direction === "Aumenta la estimación") {
    return <ArrowUp aria-hidden="true" size={16} strokeWidth={1.8} />;
  }
  if (direction === "Reduce la estimación") {
    return <ArrowDown aria-hidden="true" size={16} strokeWidth={1.8} />;
  }
  return <ArrowRight aria-hidden="true" size={16} strokeWidth={1.8} />;
}

type PredictionExplanationProps = {
  model: ModelDTO;
};

/**
 * The selected M0 serving model is a temporal reference without coefficients.
 * This table explains the rejected M1 candidate honestly: additive
 * contributions in the transformed scale are associations, never causes.
 */
export function PredictionExplanation({ model }: PredictionExplanationProps) {
  const candidate = parseCandidateM1(model);
  const rows: CandidateRow[] = candidate
    ? candidate.coefficients.map((coefficient, index) => {
        const feature = candidate.features[index] ?? `feature_${index}`;
        return {
          feature,
          label: featureLabel(feature),
          coefficient,
          direction: coefficientDirection(coefficient),
          unit: coefficientUnit(feature),
        };
      })
    : [];

  return (
    <section className="summary-card" aria-labelledby="explanation-heading">
      <div className="card-heading">
        <div>
          <h2 id="explanation-heading">
            Contribuciones aditivas del candidato M1
          </h2>
          <p>
            Lectura explicable del candidato que no fue seleccionado. La familia
            M0 en producción no publica coeficientes sociodemográficos.
          </p>
        </div>
        <span className="status-pill status-pill--neutral">Candidato M1</span>
      </div>

      <p className="explanation-intro">
        M1 no está en producción ni se usa para las predicciones publicadas. Su
        forma es aditiva: abstención M1 ≈{" "}
        <strong>
          {candidate ? candidate.intercept.toFixed(2) : "sin dato"} pp
        </strong>{" "}
        + Σ β · z, donde z es cada variable estandarizada. La descomposición sólo
        ordena la asociación de cada variable.
      </p>

      {candidate ? (
        <>
          <p className="explanation-intercept">
            Intercepto {candidate.intercept.toFixed(2)} pp
          </p>
          <DataTable
            caption="Coeficientes aditivos del candidato M1"
            rows={rows}
            rowKey={(row) => row.feature}
            emptyMessage="El candidato no publica coeficientes."
            columns={[
              {
                key: "label",
                header: "Variable",
                render: (row) => row.label,
              },
              {
                key: "coefficient",
                header: "Coeficiente",
                align: "right",
                render: (row) => (
                  <span className="coefficient-value">
                    {formatSignedCoefficient(row.coefficient)}{" "}
                    <span className="coefficient-unit">{row.unit}</span>
                  </span>
                ),
              },
              {
                key: "direction",
                header: "Dirección de la asociación",
                render: (row) => (
                  <span className="coefficient-direction">
                    <DirectionIcon direction={row.direction} />
                    {row.direction}
                  </span>
                ),
              },
            ]}
          />
        </>
      ) : (
        <p className="inline-alert inline-alert--warning" role="status">
          El modelo seleccionado no publica coeficientes aditivos. No se
          reconstruyen contribuciones sin datos persistidos.
        </p>
      )}

      <p className="explanation-caveat">
        Los coeficientes describen asociaciones en la escala transformada; no
        identifican causas ni efectos. No se usan para estimar personas,
        presupuesto ni eficacia de una intervención.
      </p>
    </section>
  );
}
