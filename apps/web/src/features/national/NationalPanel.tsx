import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { useGlobalFilters, type StateCode } from "../../app/filters";
import { navigate, pathWithCurrentFilters } from "../../app/navigation";
import { DataTable } from "../../components/DataTable";
import { PageState } from "../../components/PageState";
import {
  fetchParticipationSummary,
  fetchTerritories,
  queryKeys,
  wmsTerritoryUrl,
  type StateParticipationSummary,
  type TerritoryDTO,
} from "../../lib/api";
import { formatCount, formatRateOrInsufficient, formatShare } from "../territory/format";

export function NationalPanel() {
  const { level, stateCode, historicalYear, setFilters } = useGlobalFilters();
  const [mapFailed, setMapFailed] = useState(false);
  const summaryQuery = useQuery({
    queryKey: queryKeys.summary(level, historicalYear),
    queryFn: ({ signal }) =>
      fetchParticipationSummary({ level, year: historicalYear, signal }),
    staleTime: 5 * 60_000,
  });
  const territoriesQuery = useQuery({
    queryKey: queryKeys.territories(stateCode, level),
    queryFn: ({ signal }) =>
      fetchTerritories({ stateCode, level, pageSize: 500, signal }),
    enabled: stateCode !== "all" && level === "municipality",
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
              Observación histórica {historicalYear}; abstención calculada desde conteos observados, cobertura del catálogo y elegibilidad del nivel seleccionado.
            </p>
          </div>
          <span className="status-pill status-pill--neutral">{level === "municipality" ? "Municipio" : "Distrito federal · Observado 2024"}</span>
        </div>
        {level === "federal_district" ? (
          <p className="district-pending" role="status">
            Observado 2024 / perfil distrital pendiente. La historia distrital anterior y cualquier predicción 2027 no están disponibles para este nivel.
          </p>
        ) : null}
        {stateCode === "all" ? (
          <>
            <NationalMap failed={mapFailed} onError={() => setMapFailed(true)} />
            <DataTable
              caption="Resumen por entidad"
              rows={summaries}
              rowKey={(row) => row.state_code}
              emptyMessage="La API no devolvió entidades para este nivel y año."
              columns={summaryColumns((row) => setFilters({ stateCode: row.state_code as StateCode, territoryId: null }))}
            />
          </>
        ) : (
          <>
            {selectedSummary ? <SummaryFacts summary={selectedSummary} /> : <p role="status">Sin resumen publicado para esta entidad.</p>}
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
            ) : null}
          </>
        )}
      </section>
      <p className="source-note">La tasa estatal se obtiene al sumar conteos observados, no al promediar tasas territoriales. La cartografía nacional es WMS; WFS se solicita sólo con entidad seleccionada.</p>
    </div>
  );
}

function NationalHeading({ level }: { level: "municipality" | "federal_district" }) {
  return (
    <header className="page-heading">
      <p className="eyebrow">Observatorio · Nacional</p>
      <h1>Panel ejecutivo</h1>
      <p className="page-heading__lead">
        {level === "municipality" ? "Comparación de abstención observada, cobertura e indicadores municipales en las 32 entidades." : "Consulta de observación distrital 2024 con su plan y cobertura; no se publican predicciones distritales."}
      </p>
    </header>
  );
}

function SummaryFacts({ summary }: { summary: StateParticipationSummary }) {
  return (
    <dl className="kpi-grid">
      <div className="kpi"><dt>Abstención observada</dt><dd>{formatRateOrInsufficient(summary.observed_abstention_pct)}</dd><dd className="kpi__note">{summary.year} · calculada desde conteos agregados</dd></div>
      <div className="kpi"><dt>Cobertura</dt><dd>{formatShare(summary.coverage_share)}</dd><dd className="kpi__note">del catálogo municipal publicado</dd></div>
      <div className="kpi"><dt>Riesgo alto</dt><dd>{formatCount(summary.high_risk_count)}</dd><dd className="kpi__note">unidades elegibles para predicción</dd></div>
      <div className="kpi"><dt>Información insuficiente</dt><dd>{formatCount(summary.insufficient_count)}</dd><dd className="kpi__note">no se representa como cero ni riesgo bajo</dd></div>
    </dl>
  );
}

function summaryColumns(onSelect: (row: StateParticipationSummary) => void) {
  return [
    { key: "state", header: "Entidad", render: (row: StateParticipationSummary) => `${row.state_name} · ${row.state_code}` },
    { key: "observed", header: "Abstención observada", align: "right" as const, render: (row: StateParticipationSummary) => formatRateOrInsufficient(row.observed_abstention_pct) },
    { key: "coverage", header: "Cobertura", align: "right" as const, render: (row: StateParticipationSummary) => formatShare(row.coverage_share) },
    { key: "high", header: "Riesgo alto", align: "right" as const, render: (row: StateParticipationSummary) => formatCount(row.high_risk_count) },
    { key: "insufficient", header: "Insuficientes", align: "right" as const, render: (row: StateParticipationSummary) => formatCount(row.insufficient_count) },
    { key: "action", header: "Acción", render: (row: StateParticipationSummary) => <button type="button" className="button button--link" onClick={() => onSelect(row)}>Ver municipios de {row.state_name}</button> },
  ];
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

function NationalMap({ failed, onError }: { failed: boolean; onError(): void }) {
  return (
    <section className="national-map" aria-labelledby="national-map-heading">
      <div className="card-heading"><div><h3 id="national-map-heading">Mapa nacional de entidades</h3><p>Contornos estatales desde WMS. Los valores observados y la navegación territorial están disponibles en la tabla.</p></div></div>
      {failed ? <p className="inline-alert" role="alert">No se pudo cargar el mapa WMS. Los resúmenes por entidad siguen disponibles en la tabla.</p> : <img src={wmsTerritoryUrl()} alt="Mapa WMS nacional con límites de las 32 entidades federativas" onError={onError} />}
    </section>
  );
}
