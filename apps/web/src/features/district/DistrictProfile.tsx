import { useQuery } from "@tanstack/react-query";

import { useGlobalFilters } from "../../app/filters";
import { navigate, pathWithCurrentFilters } from "../../app/navigation";
import { DataTable } from "../../components/DataTable";
import { PageState } from "../../components/PageState";
import {
  fetchDistrictFeatures,
  fetchHistory,
  fetchTerritories,
  queryKeys,
  type HistoryDTO,
  type TerritoryDTO,
} from "../../lib/api";
import { formatCount, formatRateOrInsufficient, formatShare } from "../territory/format";
import { MunicipalityDistrictPanel } from "../territory/MunicipalityDistrictPanel";
import { DistrictMap } from "./DistrictMap";

export function DistrictProfile() {
  const { stateCode, territoryId, setFilters } = useGlobalFilters();
  const territoriesQuery = useQuery({
    queryKey: queryKeys.territories(stateCode, "federal_district"),
    queryFn: ({ signal }) => fetchTerritories({ stateCode, level: "federal_district", pageSize: 500, signal }),
    enabled: stateCode !== "all",
    staleTime: 5 * 60_000,
  });
  const historyQuery = useQuery({
    queryKey: ["district-observed-2024", stateCode, territoryId],
    queryFn: ({ signal }) => fetchHistory({ level: "federal_district", stateCode, territoryId, year: 2024, pageSize: 500, signal }),
    enabled: stateCode !== "all",
    staleTime: 5 * 60_000,
  });
  const mapQuery = useQuery({
    queryKey: queryKeys.districtFeatures(stateCode),
    queryFn: ({ signal }) => fetchDistrictFeatures(stateCode, signal),
    enabled: stateCode !== "all" && Boolean(territoryId),
    staleTime: 60 * 60_000,
  });

  if (stateCode === "all") {
    return <PageState variant="empty" title="Seleccione una entidad" message="El mapa y las fichas distritales se consultan por entidad para mantener acotadas las geometrías." />;
  }
  if (territoriesQuery.isPending || historyQuery.isPending) {
    return <PageState variant="loading" title="Cargando observación distrital 2024" message="Consultando marco 2023, conteos observados y cobertura." />;
  }
  if (territoriesQuery.isError || historyQuery.isError) {
    return <PageState variant="error" title="No se pudo cargar el perfil distrital" message="No se presentan valores estimados ni se sustituyen datos faltantes por cero." action={<button type="button" className="button button--secondary" onClick={() => { void territoriesQuery.refetch(); void historyQuery.refetch(); }}>Reintentar</button>} />;
  }
  const territories = territoriesQuery.data?.items ?? [];
  const records = historyQuery.data?.items ?? [];
  if (!territoryId) {
    const rows = territories.map((territory) => ({
      territory,
      record: records.find((item) => item.territory_id === territory.id),
    }));
    return <section className="district-list" aria-labelledby="district-list-heading">
      <h2 id="district-list-heading">Distritos federales · marco 2023</h2>
      <p>Abstención observada 2024 y cobertura explícita. Sin predicción, bandas ni escenarios.</p>
      {rows.length ? <DataTable caption="Observación distrital por territorio" rows={rows} rowKey={(row) => row.territory.id} columns={[
        { key: "district", header: "Distrito", render: (row) => `${row.territory.name} · marco 2023` },
        { key: "observed", header: "Observado 2024 · abstención", align: "right", render: (row) => formatRateOrInsufficient(row.record?.abstention_pct) },
        { key: "coverage", header: "Cobertura", align: "right", render: (row) => formatShare(row.record?.coverage_share) },
        { key: "ln", header: "LN 2024", align: "right", render: (row) => formatCount(row.record?.ln) },
        { key: "coverage-status", header: "Cobertura", render: (row) => row.record?.eligible ? "Suficiente" : "Información insuficiente" },
        { key: "open", header: "Ficha", render: (row) => <button type="button" className="button button--link" onClick={() => { setFilters({ territoryId: row.territory.id }); navigate(pathWithCurrentFilters("/territory")); }}>Abrir ficha de {row.territory.name}</button> },
      ]} /> : <p role="status">No hay distritos publicados para esta entidad.</p>}
    </section>;
  }

  const territory = territories.find((item) => item.id === territoryId);
  const observation = records.find((item) => item.territory_id === territoryId);
  return <DistrictObserved territory={territory} observation={observation} mapLoading={mapQuery.isPending} mapError={mapQuery.isError} features={mapQuery.data} stateCode={stateCode} />;
}

function DistrictObserved({
  territory,
  observation,
  mapLoading,
  mapError,
  features,
  stateCode,
}: {
  territory: TerritoryDTO | undefined;
  observation: HistoryDTO | undefined;
  mapLoading: boolean;
  mapError: boolean;
  features: Awaited<ReturnType<typeof fetchDistrictFeatures>> | undefined;
  stateCode: string;
}) {
  const { territoryId, setFilters } = useGlobalFilters();
  const label = territory?.name ?? observation?.name ?? "Distrito seleccionado";
  const code = territory?.territory_code ?? "";
  return <>
    <header className="page-heading"><p className="eyebrow">Observatorio · {stateCode} · marco 2023</p><h2>{label} · marco 2023</h2><p className="page-heading__lead">Ficha territorial con conteos y cobertura observados de 2024. El plan distrital es referencia cartográfica, no una jerarquía municipal.</p></header>
    <section className="summary-card" aria-label={`Observación 2024 de ${label}`}>
      <div className="card-heading"><h3>Observado 2024</h3><span className="status-pill status-pill--neutral">Marco 2023</span></div>
      <dl className="kpi-grid">
        <div className="kpi"><dt>Abstención observada</dt><dd>{formatRateOrInsufficient(observation?.abstention_pct)}</dd><dd className="kpi__note">Conteos agregados de secciones</dd></div>
        <div className="kpi"><dt>Cobertura</dt><dd>{formatShare(observation?.coverage_share)}</dd><dd className="kpi__note">Sobre LN2024 de referencia</dd></div>
        <div className="kpi"><dt>Lista nominal (LN)</dt><dd>{formatCount(observation?.ln)}</dd><dd className="kpi__note">Todas las secciones CCPC asignadas al DEF2023 oficial</dd></div>
        <div className="kpi"><dt>Estado de cobertura</dt><dd>{observation?.eligible ? "Suficiente" : "Información insuficiente"}</dd><dd className="kpi__note">No implica elegibilidad predictiva</dd></div>
      </dl>
    </section>
    <section className="summary-card" aria-labelledby="district-map-heading">
      <h3 id="district-map-heading">Mapa del marco 2023</h3>
      {mapLoading ? <p role="status">Cargando geometría distrital…</p> : null}
      {mapError ? <p role="alert">No se pudo cargar el mapa. La ficha y la tabla de agregados siguen disponibles.</p> : null}
      {!mapLoading && !mapError && features ? <DistrictMap features={features} selectedCode={code} /> : null}
    </section>
    {territoryId ? <MunicipalityDistrictPanel territoryId={territoryId} kind="district" onSelectMunicipality={(row) => {
      // A municipality may intersect several districts; resolve by its code through the state-scoped catalogue.
      void fetchTerritories({ stateCode, level: "municipality", pageSize: 500 }).then((page) => {
        const municipality = page.items.find((item) => item.territory_code === row.municipality_code);
        if (municipality) {
          setFilters({ level: "municipality", territoryId: municipality.id });
          navigate(pathWithCurrentFilters("/territory"));
        }
      });
    }} /> : null}
  </>;
}
