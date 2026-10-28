import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { useGlobalFilters, type StateCode } from "../../app/filters";
import { navigate, pathWithCurrentFilters } from "../../app/navigation";
import { DataTable } from "../../components/DataTable";
import { PageState } from "../../components/PageState";
import {
  fetchAllPredictions,
  fetchNationalStateFeatures,
  fetchHistory,
  fetchModels,
  fetchParticipationSummary,
  fetchTerritories,
  queryKeys,
  wmsTerritoryUrl,
  type NationalStateFeatureCollection,
  type StateParticipationSummary,
  type TerritoryDTO,
} from "../../lib/api";
import { formatCount, formatRateOrInsufficient, formatShare } from "../territory/format";
import { parseModelMetrics, summarizePredictions } from "../prediction/modelEvidence";

export function NationalPanel() {
  const { level, stateCode, setFilters } = useGlobalFilters();
  const [mapFailed, setMapFailed] = useState(false);
  const summaryYear = 2024 as const;
  const modelsQuery = useQuery({
    queryKey: queryKeys.models(),
    queryFn: ({ signal }) => fetchModels({ signal }),
    enabled: stateCode === "all" && level === "municipality",
    staleTime: 5 * 60_000,
  });
  const model = modelsQuery.data?.items[0];
  const predictionsQuery = useQuery({
    queryKey: queryKeys.predictions(model?.model_run_id ?? null),
    queryFn: ({ signal }) => fetchAllPredictions({
      modelRunId: model?.model_run_id ?? null,
      stateCode: "all",
      pageSize: 500,
      signal,
    }),
    enabled: stateCode === "all" && level === "municipality" && Boolean(model),
    staleTime: 60_000,
  });
  const summaryQuery = useQuery({
    queryKey: queryKeys.summary(level, summaryYear),
    queryFn: ({ signal }) =>
      fetchParticipationSummary({ level, year: summaryYear, signal }),
    staleTime: 5 * 60_000,
  });
  const stateFeaturesQuery = useQuery({
    queryKey: queryKeys.nationalStateFeatures(),
    queryFn: ({ signal }) => fetchNationalStateFeatures(signal),
    enabled: stateCode === "all" && level === "municipality",
    staleTime: 60 * 60_000,
  });
  const territoriesQuery = useQuery({
    queryKey: queryKeys.territories(stateCode, level),
    queryFn: ({ signal }) =>
      fetchTerritories({ stateCode, level, pageSize: 500, signal }),
    enabled: stateCode !== "all",
    staleTime: 5 * 60_000,
  });
  const districtHistoryQuery = useQuery({
    queryKey: ["district-list-history", stateCode, 2024],
    queryFn: ({ signal }) => fetchHistory({ level: "federal_district", stateCode, year: 2024, pageSize: 500, signal }),
    enabled: stateCode !== "all" && level === "federal_district",
    staleTime: 5 * 60_000,
  });

  if (summaryQuery.isPending) {
    return (
      <div className="page national-page">
        <NationalHeading level={level} />
        <PageState variant="loading" title="Cargando resumen nacional" message="Consultando los agregados observados y la cobertura publicados para 32 entidades." />
      </div>
    );
  }
  if (summaryQuery.isError) {
    return (
      <div className="page national-page">
        <NationalHeading level={level} />
        <PageState variant="error" headingLevel={1} title="No se pudo cargar el resumen nacional" message={summaryQuery.error instanceof Error ? summaryQuery.error.message : "El resumen no está disponible."} action={<button type="button" className="button button--primary" onClick={() => void summaryQuery.refetch()}>Reintentar consulta</button>} />
      </div>
    );
  }

  const summaries = summaryQuery.data ?? [];
  const selectedSummary = summaries.find((item) => item.state_code === stateCode);
  const territories = territoriesQuery.data?.items ?? [];

  return (
    <div className="page national-page">
      <NationalHeading level={level} />

      <section className="summary-card" aria-labelledby="national-summary-heading">
        <div className="card-heading">
          <div>
            <h2 id="national-summary-heading">
              {stateCode === "all" ? "Resumen nacional" : `${selectedSummary?.state_name ?? "Entidad seleccionada"} · ${stateCode}`}
            </h2>
            <p>
              {level === "municipality"
                ? `Observación municipal ${summaryYear}; tasas estatales calculadas desde conteos agregados y cobertura del catálogo.`
                : "Observación distrital 2024 y cobertura publicadas. Sin modelo 2027."}
            </p>
          </div>
          <span className="status-pill status-pill--neutral">{level === "municipality" ? "Municipio" : "Distrito federal · Observado 2024 · Sin modelo 2027"}</span>
        </div>
        {stateCode === "all" ? (
          <>
            {level === "municipality" ? (
              <>
                <NationalPredictionFacts
                  pending={modelsQuery.isPending || predictionsQuery.isPending}
                  error={modelsQuery.isError || predictionsQuery.isError}
                  summary={model && predictionsQuery.data
                    ? summarizePredictions(predictionsQuery.data.items, parseModelMetrics(model.metrics))
                    : null}
                  highRisk={predictionsQuery.data?.items.filter(
                    (prediction) => prediction.eligible && prediction.risk === "high",
                  ).length ?? 0}
                />
                <NationalMap
                  failed={mapFailed}
                  onError={() => setMapFailed(true)}
                  year={2024}
                  summaries={summaries}
                  features={stateFeaturesQuery.data}
                  featuresLoading={stateFeaturesQuery.isPending}
                  featuresError={stateFeaturesQuery.isError}
                />
              </>
            ) : null}
            <DataTable
              caption="Resumen por entidad"
              rows={summaries}
              rowKey={(row) => row.state_code}
              emptyMessage="La API no devolvió entidades para este nivel y año."
              columns={summaryColumns(level, (row) => setFilters({ stateCode: row.state_code as StateCode, territoryId: null }))}
            />
          </>
        ) : (
          <>
            {selectedSummary ? <SummaryFacts summary={selectedSummary} level={level} /> : <p role="status">Sin resumen publicado para esta entidad.</p>}
            {level === "municipality" ? (
              <>
                <h3 className="national-subheading">Municipios de la entidad</h3>
                {territoriesQuery.isPending ? <p role="status">Cargando municipios…</p> : null}
                {territoriesQuery.isError ? <p role="alert">No se pudo cargar la lista municipal.</p> : null}
                {territories.length > 0 ? <TerritoryList territories={territories} onSelect={(territory) => {
                  setFilters({ territoryId: territory.id });
                  navigate(pathWithCurrentFilters("/territory"));
                }} /> : null}
                {!territoriesQuery.isPending && !territoriesQuery.isError && territories.length === 0 ? <p>No hay municipios disponibles para esta entidad.</p> : null}
              </>
            ) : (
              <>
                <h3 className="national-subheading">Distritos federales · marco 2023</h3>
                {territoriesQuery.isPending || districtHistoryQuery.isPending ? <p role="status">Cargando distritos y observación 2024…</p> : null}
                {territoriesQuery.isError || districtHistoryQuery.isError ? <p role="alert">No se pudo cargar la lista distrital observada.</p> : null}
                {!territoriesQuery.isPending && !territoriesQuery.isError && !districtHistoryQuery.isPending && !districtHistoryQuery.isError && territories.length > 0 ? (
                  <DataTable
                    caption="Observación distrital por territorio"
                    rows={territories.map((territory) => ({ territory, record: districtHistoryQuery.data?.items.find((item) => item.territory_id === territory.id) }))}
                    rowKey={(row) => row.territory.id}
                    columns={[
                      { key: "district", header: "Distrito · marco 2023", render: (row) => `${row.territory.name} · marco 2023` },
                      { key: "observed", header: "Observado 2024 · abstención", align: "right", render: (row) => formatRateOrInsufficient(row.record?.abstention_pct) },
                      { key: "coverage", header: "Cobertura", align: "right", render: (row) => formatShare(row.record?.coverage_share) },
                      { key: "ln", header: "LN 2024", align: "right", render: (row) => formatCount(row.record?.ln) },
                      { key: "coverage-status", header: "Estado de cobertura", render: (row) => row.record?.eligible ? "Suficiente" : "Información insuficiente" },
                      { key: "action", header: "Ficha", render: (row) => <button type="button" className="button button--link" onClick={() => { setFilters({ territoryId: row.territory.id }); navigate(pathWithCurrentFilters("/territory")); }}>Abrir ficha de {row.territory.name}</button> },
                    ]}
                  />
                ) : null}
                {!territoriesQuery.isPending && !territoriesQuery.isError && territories.length === 0 ? <p role="status">No hay distritos publicados para esta entidad.</p> : null}
              </>
            )}
          </>
        )}
      </section>
      <p className="source-note">{level === "municipality" ? "La tasa estatal se obtiene al sumar conteos observados, no al promediar tasas territoriales. El mapa temático usa la observación municipal de 2024 y 32 geometrías estatales WFS; el WMS conserva los contornos de referencia." : "Las cifras distritales son observaciones agregadas de 2024. No hay un modelo 2027 publicado para este nivel."}</p>
    </div>
  );
}

function NationalPredictionFacts({
  pending,
  error,
  summary,
  highRisk,
}: {
  pending: boolean;
  error: boolean;
  summary: ReturnType<typeof summarizePredictions> | null;
  highRisk: number;
}) {
  if (pending) return <p role="status">Cargando cobertura predictiva nacional…</p>;
  if (error) return <p role="alert">No se pudo cargar la cobertura predictiva nacional.</p>;
  if (!summary) return <p role="status">No hay predicciones municipales publicadas.</p>;
  return (
    <dl className="kpi-grid" aria-label="Cobertura predictiva nacional">
      <div className="kpi">
        <dt>Cobertura de predicción</dt>
        <dd data-testid="national-coverage">{summary.eligible} de {summary.total}</dd>
        <dd className="kpi__note">{(summary.eligible / summary.total * 100).toFixed(1)} % de municipios elegibles.</dd>
      </div>
      <div className="kpi">
        <dt>Riesgo alto</dt>
        <dd data-testid="national-high-risk">{highRisk}</dd>
        <dd className="kpi__note">Abstención estimada de 50 % o más entre elegibles.</dd>
      </div>
      <div className="kpi">
        <dt>Información insuficiente</dt>
        <dd>{summary.insufficient}</dd>
        <dd className="kpi__note">No se imputa como cero ni riesgo bajo.</dd>
      </div>
    </dl>
  );
}

function NationalHeading({ level }: { level: "municipality" | "federal_district" }) {
  return (
    <header className="page-heading">
      <p className="eyebrow">Observatorio · Nacional</p>
      <h1>Panel ejecutivo</h1>
      <p className="page-heading__lead">
        {level === "municipality" ? "Comparación de abstención observada, cobertura e indicadores municipales en las 32 entidades." : "Observación distrital 2024 y cobertura por entidad. Sin modelo 2027."}
      </p>
    </header>
  );
}

function SummaryFacts({ summary, level }: { summary: StateParticipationSummary; level: "municipality" | "federal_district" }) {
  return (
    <dl className="kpi-grid">
      <div className="kpi"><dt>Abstención observada</dt><dd>{formatRateOrInsufficient(summary.observed_abstention_pct)}</dd><dd className="kpi__note">{summary.year} · calculada desde conteos agregados</dd></div>
      <div className="kpi"><dt>Cobertura</dt><dd>{formatShare(summary.coverage_share)}</dd><dd className="kpi__note">{level === "municipality" ? "del catálogo municipal publicado" : "de unidades distritales publicadas"}</dd></div>
      {level === "municipality" ? (
        <>
          <div className="kpi"><dt>Riesgo alto</dt><dd>{formatCount(summary.high_risk_count)}</dd><dd className="kpi__note">unidades elegibles para predicción</dd></div>
          <div className="kpi"><dt>Información insuficiente</dt><dd>{formatCount(summary.insufficient_count)}</dd><dd className="kpi__note">no se representa como cero ni riesgo bajo</dd></div>
        </>
      ) : null}
    </dl>
  );
}

function summaryColumns(level: "municipality" | "federal_district", onSelect: (row: StateParticipationSummary) => void) {
  const columns = [
    { key: "state", header: "Entidad", render: (row: StateParticipationSummary) => `${row.state_name} · ${row.state_code}` },
    { key: "observed", header: "Abstención observada", align: "right" as const, render: (row: StateParticipationSummary) => formatRateOrInsufficient(row.observed_abstention_pct) },
    { key: "coverage", header: "Cobertura", align: "right" as const, render: (row: StateParticipationSummary) => formatShare(row.coverage_share) },
    ...(level === "municipality" ? [
      { key: "high", header: "Riesgo alto", align: "right" as const, render: (row: StateParticipationSummary) => formatCount(row.high_risk_count) },
      { key: "insufficient", header: "Insuficientes", align: "right" as const, render: (row: StateParticipationSummary) => formatCount(row.insufficient_count) },
    ] : []),
    { key: "action", header: "Acción", render: (row: StateParticipationSummary) => <button type="button" className="button button--link" onClick={() => onSelect(row)}>{level === "municipality" ? `Ver municipios de ${row.state_name}` : `Ver observación distrital de ${row.state_name}`}</button> },
  ];
  return columns;
}

function TerritoryList({ territories, onSelect }: { territories: TerritoryDTO[]; onSelect(territory: TerritoryDTO): void }) {
  return (
    <DataTable
      caption="Municipios de la entidad"
      rows={territories}
      rowKey={(territory) => territory.id}
      columns={[
        { key: "code", header: "Código INE", render: (territory) => territory.territory_code ?? territory.municipality_code ?? "No disponible" },
        { key: "name", header: "Municipio", render: (territory) => territory.name },
        { key: "action", header: "Acción", render: (territory) => <button type="button" className="button button--link" onClick={() => onSelect(territory)}>Abrir {territory.name}</button> },
      ]}
    />
  );
}

const NATIONAL_BOUNDS = { minLon: -118.5, maxLon: -86.8, minLat: 14.5, maxLat: 32.8 };
const CHOROPLETH_COLORS = {
  unavailable: "#d1d5db",
  under30: "#d7eee5",
  under40: "#93cfb6",
  under50: "#f4d58d",
  "50plus": "#c96969",
} as const;

function observedColor(value: number | null | undefined): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return CHOROPLETH_COLORS.unavailable;
  if (value < 30) return CHOROPLETH_COLORS.under30;
  if (value < 40) return CHOROPLETH_COLORS.under40;
  if (value < 50) return CHOROPLETH_COLORS.under50;
  return CHOROPLETH_COLORS["50plus"];
}

function projectCoordinate(coordinate: number[]): [number, number] {
  const longitude = coordinate[0]!;
  const latitude = coordinate[1]!;
  const x = ((longitude - NATIONAL_BOUNDS.minLon) / (NATIONAL_BOUNDS.maxLon - NATIONAL_BOUNDS.minLon)) * 1200;
  const y = ((NATIONAL_BOUNDS.maxLat - latitude) / (NATIONAL_BOUNDS.maxLat - NATIONAL_BOUNDS.minLat)) * 700;
  return [x, y];
}

function ringPath(ring: number[][]): string {
  return ring.map((coordinate, index) => {
    const [x, y] = projectCoordinate(coordinate);
    return `${index === 0 ? "M" : "L"}${x.toFixed(2)},${y.toFixed(2)}`;
  }).join(" ") + " Z";
}

function stateGeometryPath(geometry: NationalStateFeatureCollection["features"][number]["geometry"]): string {
  if (geometry.type === "Polygon") return geometry.coordinates.map(ringPath).join(" ");
  if (geometry.type === "MultiPolygon") return geometry.coordinates.flatMap((polygon) => polygon.map(ringPath)).join(" ");
  return "";
}

function NationalMap({
  failed,
  onError,
  year,
  summaries,
  features,
  featuresLoading,
  featuresError,
}: {
  failed: boolean;
  onError(): void;
  year: number;
  summaries: StateParticipationSummary[];
  features: NationalStateFeatureCollection | undefined;
  featuresLoading: boolean;
  featuresError: boolean;
}) {
  const summariesByState = new Map(summaries.map((summary) => [summary.state_code, summary]));
  return (
    <section className="national-map" aria-labelledby="national-map-heading">
      <div className="card-heading"><div><h3 id="national-map-heading">Mapa nacional de entidades</h3><p>Abstención municipal observada {year}, calculada desde conteos agregados. Los contornos de referencia provienen del WMS nacional.</p></div></div>
      {failed ? <p className="inline-alert" role="alert">No se pudo cargar el mapa WMS. Los resúmenes por entidad siguen disponibles en la tabla.</p> : (
        <div className="national-map__viewport">
          <img src={wmsTerritoryUrl()} alt="Mapa WMS nacional con límites de las 32 entidades federativas" onError={onError} />
          {features ? (
            <svg className="national-map__choropleth" viewBox="0 0 1200 700" role="img" aria-labelledby="national-choropleth-title national-choropleth-desc">
              <title id="national-choropleth-title">Abstención municipal observada por entidad</title>
              <desc id="national-choropleth-desc">Las entidades se colorean según la tasa de abstención observada; los valores exactos y los datos insuficientes están en la tabla Resumen por entidad.</desc>
              {features.features.map((feature) => {
                const code = feature.properties?.state_code;
                if (!code || !feature.geometry) return null;
                const summary = summariesByState.get(code);
                return <path key={code} data-state-code={code} d={stateGeometryPath(feature.geometry)} fill={observedColor(summary?.observed_abstention_pct)} fillOpacity="0.58" stroke="#ffffff" strokeWidth="1.25" />;
              })}
            </svg>
          ) : null}
        </div>
      )}
      <div className="national-map__legend" role="group" aria-label={`Leyenda de abstención observada ${year}`}>
        <span className="national-map__legend-title">Abstención observada · {year}</span>
        <ul>
          <LegendItem color={CHOROPLETH_COLORS.under30} label="Menos de 30 %" />
          <LegendItem color={CHOROPLETH_COLORS.under40} label="30–39.9 %" />
          <LegendItem color={CHOROPLETH_COLORS.under50} label="40–49.9 %" />
          <LegendItem color={CHOROPLETH_COLORS["50plus"]} label="50 % o más" />
          <LegendItem color={CHOROPLETH_COLORS.unavailable} label="Información insuficiente" />
        </ul>
      </div>
      {featuresLoading ? <p role="status">Cargando geometrías de las 32 entidades…</p> : null}
      {featuresError ? <p role="status">No se pudo cargar el relleno temático. Los valores observados siguen disponibles en la tabla accesible.</p> : null}
    </section>
  );
}

function LegendItem({ color, label }: { color: string; label: string }) {
  return <li><span className="national-map__swatch" aria-hidden="true" style={{ backgroundColor: color }} />{label}</li>;
}
