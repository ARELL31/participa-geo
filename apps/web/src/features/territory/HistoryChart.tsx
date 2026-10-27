import { DataTable } from "../../components/DataTable";
import {
  HISTORICAL_YEARS,
  type ElectionYear,
} from "../../app/filters";
import type { HistoryDTO } from "../../lib/api";
import {
  formatCount,
  formatRate,
  formatShare,
  knownUniverse,
} from "./format";

type ChartRow = {
  year: ElectionYear;
  record: HistoryDTO | undefined;
};

const WIDTH = 720;
const HEIGHT = 300;
const MARGIN = { top: 24, right: 40, bottom: 42, left: 64 };
const PLOT_WIDTH = WIDTH - MARGIN.left - MARGIN.right;
const PLOT_HEIGHT = HEIGHT - MARGIN.top - MARGIN.bottom;

function xPosition(index: number): number {
  return MARGIN.left + (index * PLOT_WIDTH) / (HISTORICAL_YEARS.length - 1);
}

function yPosition(value: number): number {
  return MARGIN.top + ((100 - value) * PLOT_HEIGHT) / 100;
}

type HistoryChartProps = {
  rows: ChartRow[];
  selectedYear: ElectionYear;
  territoryLabel: string;
};

/**
 * A deliberately small SVG line chart with a six-year table alternative.
 * Missing observations break the line; the table always says “No disponible”
 * rather than plotting or printing a synthetic zero.
 */
export function HistoryChart({
  rows,
  selectedYear,
  territoryLabel,
}: HistoryChartProps) {
  const points = rows.map((row, index) => {
    const value = row.record?.abstention_pct;
    return {
      year: row.year,
      x: xPosition(index),
      y:
        typeof value === "number" && Number.isFinite(value)
          ? yPosition(value)
          : null,
      value: typeof value === "number" && Number.isFinite(value) ? value : null,
    };
  });

  const segments: Array<Array<{ x: number; y: number }>> = [];
  let current: Array<{ x: number; y: number }> = [];
  for (const point of points) {
    if (point.y === null) {
      if (current.length > 0) segments.push(current);
      current = [];
    } else {
      current.push({ x: point.x, y: point.y });
    }
  }
  if (current.length > 0) segments.push(current);

  const hasAnyValue = points.some((point) => point.value !== null);
  const selectedIndex = HISTORICAL_YEARS.indexOf(selectedYear);

  return (
    <section className="chart-card" aria-labelledby="history-heading">
      <div className="card-heading">
        <div>
          <h2 id="history-heading">Historia de abstención</h2>
          <p>
            Observación histórica de {territoryLabel}. Seis cortes CCPC; la
            línea no se interpola cuando falta un dato.
          </p>
        </div>
        <span className="status-pill status-pill--neutral">Observación histórica</span>
      </div>

      {hasAnyValue ? (
        <figure className="history-figure">
          <svg
            className="history-chart"
            viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
            role="img"
            aria-labelledby="history-chart-title history-chart-desc"
          >
            <title id="history-chart-title">
              Abstención histórica de {territoryLabel}, 2009 a 2024
            </title>
            <desc id="history-chart-desc">
              Línea de abstención en porcentaje para los seis años electorales.
              La tabla siguiente contiene los mismos valores, incluidos los años
              sin información.
            </desc>
            {[0, 25, 50, 75, 100].map((tick) => (
              <g key={tick}>
                <line
                  x1={MARGIN.left}
                  y1={yPosition(tick)}
                  x2={WIDTH - MARGIN.right}
                  y2={yPosition(tick)}
                  className="chart-grid"
                />
                <text
                  x={MARGIN.left - 10}
                  y={yPosition(tick) + 4}
                  textAnchor="end"
                  className="chart-axis-label chart-axis-label--y"
                >
                  {tick}
                </text>
              </g>
            ))}
            {selectedIndex >= 0 ? (
              <line
                x1={xPosition(selectedIndex)}
                y1={MARGIN.top}
                x2={xPosition(selectedIndex)}
                y2={HEIGHT - MARGIN.bottom}
                className="chart-selected-guide"
              />
            ) : null}
            {segments.map((segment, index) => (
              <path
                key={`segment-${index}`}
                d={segment
                  .map(
                    (point, pointIndex) =>
                      `${pointIndex === 0 ? "M" : "L"} ${point.x} ${point.y}`,
                  )
                  .join(" ")}
                className="chart-line"
              />
            ))}
            {points.map((point, index) => (
              <g key={point.year}>
                <text
                  x={point.x}
                  y={HEIGHT - MARGIN.bottom + 24}
                  textAnchor="middle"
                  className={
                    index === selectedIndex
                      ? "chart-axis-label is-selected"
                      : "chart-axis-label"
                  }
                >
                  {point.year}
                </text>
                {point.y !== null ? (
                  <circle
                    cx={point.x}
                    cy={point.y}
                    r={index === selectedIndex ? 6 : 4}
                    className={
                      index === selectedIndex
                        ? "chart-point is-selected"
                        : "chart-point"
                    }
                  />
                ) : (
                  <g>
                    <circle
                      cx={point.x}
                      cy={HEIGHT - MARGIN.bottom}
                      r={3}
                      className="chart-point chart-point--missing"
                    />
                    <text
                      x={point.x}
                      y={HEIGHT - MARGIN.bottom - 8}
                      textAnchor="middle"
                      className="chart-missing-label"
                    >
                      Sin dato
                    </text>
                  </g>
                )}
              </g>
            ))}
          </svg>
          <figcaption>
            Abstención (%) por año electoral. Año resaltado: {selectedYear}.
          </figcaption>
        </figure>
      ) : (
        <p className="chart-insufficient" role="status">
          Información insuficiente para trazar la serie histórica. La tabla
          conserva el detalle de cada año.
        </p>
      )}

      <DataTable
        caption="Historia de participación por año"
        rows={rows}
        rowKey={(row) => String(row.year)}
        rowProps={(row) => ({
          "aria-current": row.year === selectedYear ? "true" : undefined,
          className: row.year === selectedYear ? "is-selected" : undefined,
        })}
        columns={[
          {
            key: "year",
            header: "Año",
            render: (row) => row.year,
          },
          {
            key: "participation",
            header: "Participación",
            align: "right",
            render: (row) => formatRate(row.record?.participation_pct),
          },
          {
            key: "abstention",
            header: "Abstención",
            align: "right",
            render: (row) => formatRate(row.record?.abstention_pct),
          },
          {
            key: "ns",
            header: "NS",
            align: "right",
            render: (row) =>
              row.record ? formatShare(row.record.unknown_share) : "No disponible",
          },
          {
            key: "known",
            header: "Universo conocido (LN − NS)",
            align: "right",
            render: (row) =>
              row.record
                ? formatCount(knownUniverse(row.record.ln, row.record.ns))
                : "No disponible",
          },
          {
            key: "eligible",
            header: "Elegible",
            render: (row) => {
              if (!row.record) return "No disponible";
              return row.record.eligible ? "Sí" : "No";
            },
          },
        ]}
      />
    </section>
  );
}
