import { useQuery } from "@tanstack/react-query";
import { RefreshCw } from "lucide-react";

import {
  HISTORICAL_YEARS,
  isElectionYear,
  useGlobalFilters,
} from "../../app/filters";
import { navigate, pathWithCurrentFilters } from "../../app/navigation";
import { GeographyNotice } from "../../components/GeographyNotice";
import { PageState } from "../../components/PageState";
import {
  fetchHistory,
  fetchModels,
  fetchMunicipalityFeatures,
  fetchPredictions,
  fetchTerritories,
  queryKeys,
  type HistoryDTO,
} from "../../lib/api";
import { HistoryChart } from "./HistoryChart";
import { MunicipalMap } from "./MunicipalMap";
import {
  formatCount,
  formatRateOrInsufficient,
  formatShare,
  knownUniverse,
} from "./format";

function historyRows(records: HistoryDTO[]) {
  return HISTORICAL_YEARS.map((year) => ({
    year,
    record: records.find((record) => record.year === year),
  }));
}

export function TerritoryPage() {
  const { level, stateCode, territoryId, historicalYear, setFilters } = useGlobalFilters();

  const modelsQuery = useQuery({
    queryKey: queryKeys.models("municipality"),
    queryFn: ({ signal }) => fetchModels({ level: "municipality", signal }),
    enabled: level === "municipality" && Boolean(territoryId),
    staleTime: 5 * 60_000,
  });
  const selectedModel = modelsQuery.data?.items[0];
  const predictionQuery = useQuery({
    queryKey: queryKeys.predictions(selectedModel?.model_run_id ?? null, level, stateCode, territoryId),
    queryFn: ({ signal }) => fetchPredictions({
      modelRunId: selectedModel?.model_run_id,
      level: "municipality",
      stateCode,
      territoryId,
      pageSize: 1,
      signal,
    }),
    enabled: level === "municipality" && Boolean(territoryId && selectedModel),
    staleTime: 60_000,
  });

  const territoriesQuery = useQuery({
    queryKey: queryKeys.territories(stateCode, level),
    queryFn: ({ signal }) => fetchTerritories({ stateCode, level, pageSize: 500, signal }),
    enabled: stateCode !== "all" && level === "municipality",
    staleTime: 5 * 60_000,
  });

  // The chart needs all six observations, so its request is intentionally
  // unfiltered by year and its key depends only on the territory.
  const seriesQuery = useQuery({
    queryKey: queryKeys.historySeries(territoryId, level, stateCode),
    queryFn: ({ signal }) =>
      fetchHistory({ level, stateCode, territoryId, pageSize: 500, signal }),
    enabled: level === "municipality" && (territoryId !== null || stateCode !== "all"),
    staleTime: 60_000,
  });

  // The selected-year query uses the now-valid `year` contract and feeds the
  // KPI/selected row; it is the only history query keyed by historical year.
  const selectedQuery = useQuery({
    queryKey: queryKeys.history({ level, stateCode, territoryId, historicalYear }),
    queryFn: ({ signal }) =>
      fetchHistory({
        level,
        stateCode,
        territoryId,
        year: historicalYear,
        pageSize: 1,
        signal,
      }),
    enabled: level === "municipality" && (territoryId !== null || stateCode !== "all"),
    staleTime: 60_000,
  });

  const featuresQuery = useQuery({
    queryKey: queryKeys.municipalFeatures(stateCode),
    queryFn: ({ signal }) =>
      fetchMunicipalityFeatures(stateCode, signal),
    enabled: stateCode !== "all" && level === "municipality",
    staleTime: 60_000,
  });

  const territories = territoriesQuery.data?.items ?? [];
  const selectedTerritory = territoryId
    ? territories.find((item) => item.id === territoryId)
    : undefined;

  // Guard against any stale envelope whose territory does not match the URL.
  const records =
    seriesQuery.data?.items.filter(
      (record) => record.territory_id === territoryId,
    ) ?? [];

  // The unfiltered series is authoritative for the chart and its table. The
  // selected-year query supplies the current KPI/selected row and is merged in
  // only for that year, so a transient year request cannot relabel the series.
  const selectedRecord = selectedQuery.data?.items.find(
    (record) =>
      record.territory_id === territoryId && record.year === historicalYear,
  );
  const rows = historyRows(records).map((row) =>
    row.year === historicalYear && selectedRecord
      ? { ...row, record: selectedRecord }
      : row,
  );

  const firstRecord = records[0];
  const selectedMunicipalityCode =
    selectedTerritory?.territory_code ?? selectedTerritory?.municipality_code ??
    firstRecord?.municipality_code ??
    null;

  // A non-null UUID is always a municipality, even if the catalogue request is
  // delayed or failed; never fall back to the state-aggregate label.
  const territoryLabel =
    territoryId === null
      ? stateCode === "14" ? "Agregado estatal de Jalisco" : `Agregado estatal · ${stateCode}`
      : selectedTerritory
        ? `${selectedTerritory.name} · ${selectedTerritory.territory_code ?? selectedTerritory.municipality_code}`
        : firstRecord?.name
          ? `${firstRecord.name} · ${firstRecord.municipality_code ?? "sin código"}`
          : "Municipio seleccionado";

  const isStateAggregate = territoryId === null;
  const eligibilityText = isStateAggregate
    ? "Agregado estatal calculado sumando conteos municipales antes de recalcular tasas."
    : selectedRecord?.eligible === false
      ? "El registro no es elegible para comparación."
      : "Tasas calculadas sobre la fuente CCPC.";
  const selectedState = selectedQuery.isPending
    ? "loading"
    : selectedQuery.isError
      ? "error"
      : "ready";

  if (level === "federal_district") {
    return (
      <div className="page territory-page">
        <header className="page-heading"><p className="eyebrow">Observatorio · {stateCode === "all" ? "Nacional" : stateCode}</p><h1>Inteligencia territorial</h1></header>
        <PageState variant="empty" title="Observado 2024 / perfil distrital pendiente" message="El nivel distrital sólo dispone de observación 2024 y cobertura. La ficha distrital y la relación municipio–distrito se incorporarán en la siguiente tarea; no hay predicción 2027 para distritos." />
      </div>
    );
  }

  if (stateCode === "all") {
    return (
      <div className="page territory-page">
        <header className="page-heading"><p className="eyebrow">Observatorio · Nacional</p><h1>Inteligencia territorial</h1><p className="page-heading__lead">Seleccione una entidad en los filtros globales para consultar municipios y geometrías acotadas.</p></header>
        <PageState variant="empty" title="Seleccione una entidad" message="La consulta municipal y el WFS se limitan a una entidad. No se descargan las 2,477 geometrías en el navegador." />
      </div>
    );
  }

  return (
    <div className="page territory-page">
      <header className="page-heading">
        <p className="eyebrow">Observatorio · {stateCode}</p>
        <h1>Inteligencia territorial</h1>
        <p className="page-heading__lead">
          Consulta la serie histórica municipal y contrasta la referencia
          cartográfica vigente. Los datos son agregados y no identifican
          personas.
        </p>
      </header>

      <GeographyNotice />

      <section className="filters-panel" aria-labelledby="filters-heading">
        <h2 id="filters-heading" className="visually-hidden">
          Filtros globales
        </h2>
        <div className="filter-field">
          <label htmlFor="municipality-filter">Municipio</label>
          <select
            id="municipality-filter"
            value={territoryId ?? ""}
            aria-describedby="municipality-filter-hint"
            disabled={territoriesQuery.isPending || territoriesQuery.isError}
            onChange={(event) =>
              setFilters({ territoryId: event.target.value || null })
            }
          >
            <option value="">Todos los municipios (agregado estatal)</option>
            {territories.map((item) => (
              <option key={item.id} value={item.id}>
                {item.territory_code ?? item.municipality_code} · {item.name}
              </option>
            ))}
            {territoriesQuery.isPending ? (
              <option value="" disabled>
                Cargando municipios…
              </option>
            ) : null}
            {territoriesQuery.isError ? (
              <option value="" disabled>
                Municipios no disponibles
              </option>
            ) : null}
          </select>
          <p id="municipality-filter-hint" className="filter-hint">
            {territoriesQuery.isError
              ? "No fue posible cargar la lista de municipios."
              : "Catálogo municipal de la entidad seleccionada."}
          </p>
        </div>

        <div className="filter-field">
          <label htmlFor="year-filter">Año histórico</label>
          <select
            id="year-filter"
            value={historicalYear}
            aria-describedby="year-filter-hint"
            onChange={(event) => {
              const value = Number(event.target.value);
              if (isElectionYear(value)) {
                setFilters({ historicalYear: value });
              }
            }}
          >
            {HISTORICAL_YEARS.map((year) => (
              <option key={year} value={year}>
                {year}
              </option>
            ))}
          </select>
          <p id="year-filter-hint" className="filter-hint">
            Cortes CCPC 2009–2024.
          </p>
        </div>

        <div className="filter-static filter-static--target">
          <span className="filter-static__label">Predicción</span>
          <span className="filter-static__value">2027</span>
          <span className="filter-static__hint">Año objetivo fijo, separado de la historia</span>
        </div>
      </section>

      {seriesQuery.isPending ? (
        <PageState
          variant="loading"
          title="Cargando historia territorial"
          message="Consultando la serie municipal y los conteos de la fuente."
        />
      ) : seriesQuery.isError ? (
        <PageState
          variant="error"
          title="No se pudo cargar la historia territorial"
          message={
            seriesQuery.error instanceof Error
              ? seriesQuery.error.message
              : "La consulta no está disponible en este momento."
          }
          action={
            <button
              type="button"
              className="button button--primary"
              onClick={() => {
                void seriesQuery.refetch();
                void selectedQuery.refetch();
              }}
            >
              <RefreshCw aria-hidden="true" size={16} strokeWidth={1.8} />
              Reintentar consulta
            </button>
          }
        />
      ) : records.length === 0 ? (
        <PageState
          variant="empty"
          title="Sin historia para los filtros seleccionados"
          message="La fuente no contiene observaciones para este municipio y año. Pruebe otro año o vuelva al agregado estatal."
        />
      ) : (
        <>
          <section className="summary-card" aria-labelledby="summary-heading">
            <div className="card-heading">
              <div>
                <h2 id="summary-heading">{territoryLabel}</h2>
                <p>
                  Observación histórica {historicalYear}.{" "}
                  {selectedState === "error"
                    ? "No se pudo cargar el año seleccionado; la serie histórica permanece visible."
                    : eligibilityText}
                </p>
              </div>
              <span className="status-pill status-pill--neutral">
                Observación histórica
              </span>
            </div>

            <dl className="kpi-grid">
              <div className="kpi">
                <dt>Participación</dt>
                <dd data-testid="kpi-participation">
                  {selectedState === "loading"
                    ? "Cargando…"
                    : selectedState === "error"
                      ? "No disponible"
                      : formatRateOrInsufficient(
                          selectedRecord?.participation_pct,
                        )}
                </dd>
                <dd className="kpi__note">Porcentaje de la lista nominal.</dd>
              </div>
              <div className="kpi">
                <dt>Abstención</dt>
                <dd data-testid="kpi-abstention">
                  {selectedState === "loading"
                    ? "Cargando…"
                    : selectedState === "error"
                      ? "No disponible"
                      : formatRateOrInsufficient(selectedRecord?.abstention_pct)}
                </dd>
                <dd className="kpi__note">
                  Nunca se sustituye un dato ausente por cero.
                </dd>
              </div>
              <div className="kpi">
                <dt>NS (no especificados)</dt>
                <dd data-testid="kpi-ns">
                  {selectedState === "loading"
                    ? "Cargando…"
                    : selectedState === "error"
                      ? "No disponible"
                      : formatCount(selectedRecord?.ns)}
                </dd>
                <dd className="kpi__note">
                  {selectedState === "loading"
                    ? "Cargando año seleccionado…"
                    : selectedRecord
                      ? `${formatShare(selectedRecord.unknown_share)} de la lista nominal.`
                      : "Sin dato de participación de NS."}
                </dd>
              </div>
              <div className="kpi">
                <dt>Universo conocido</dt>
                <dd data-testid="kpi-known">
                  {selectedState === "loading"
                    ? "Cargando…"
                    : selectedState === "error" || !selectedRecord
                      ? "No disponible"
                      : formatCount(
                          knownUniverse(selectedRecord.ln, selectedRecord.ns),
                        )}
                </dd>
                <dd className="kpi__note">LN − NS. Conteo absoluto, no una tasa.</dd>
              </div>
            </dl>

            <p className="source-note">
              Fuente: CCPC, cortes {HISTORICAL_YEARS[0]}–{HISTORICAL_YEARS.at(-1)}.
              Referencia cartográfica: 15 de diciembre de 2025.{" "}
              {isStateAggregate
                ? "El agregado estatal suma conteos territoriales antes de recalcular tasas; la elegibilidad de modelo no aplica."
                : "Los agregados estatales suman conteos antes de recalcular tasas."}
            </p>
          </section>

          <HistoryChart
            rows={rows}
            selectedYear={historicalYear}
            territoryLabel={territoryLabel}
          />
        </>
      )}

      {territoryId ? (
        <section className="summary-card" aria-labelledby="municipal-prediction-heading">
          <div className="card-heading"><div><h2 id="municipal-prediction-heading">Predicción municipal 2027</h2><p>Estimación publicada para este municipio; no representa un efecto causal.</p></div><span className="status-pill status-pill--neutral">Predicción 2027</span></div>
          {modelsQuery.isPending || (selectedModel && predictionQuery.isPending) ? <p role="status">Cargando predicción publicada…</p> : null}
          {modelsQuery.isError || (selectedModel && predictionQuery.isError) ? <p role="alert">No se pudo consultar la predicción publicada para este municipio.</p> : null}
          {!modelsQuery.isPending && !modelsQuery.isError && !selectedModel ? <p role="status">No hay una ejecución municipal publicada.</p> : null}
          {!modelsQuery.isPending && !modelsQuery.isError && selectedModel && !predictionQuery.isPending && !predictionQuery.isError ? (
            predictionQuery.data?.items[0]?.eligible
              ? <p className="kpi__text">Abstención estimada: {formatRateOrInsufficient(predictionQuery.data.items[0].estimated_abstention_pct)}</p>
              : <p className="district-pending">Información insuficiente para publicar una predicción 2027. No se sustituye por cero ni por riesgo bajo.</p>
          ) : null}
          <a className="button button--secondary" href={pathWithCurrentFilters("/scenarios")} onClick={(event) => { event.preventDefault(); navigate(pathWithCurrentFilters("/scenarios")); }}>Explorar escenario hipotético</a>
        </section>
      ) : null}

      <MunicipalMap
        year={historicalYear}
        features={featuresQuery.data}
        featuresLoading={featuresQuery.isPending}
        featuresError={featuresQuery.isError}
        selectedMunicipalityCode={selectedMunicipalityCode}
        onSelectMunicipality={(code) => {
          const match = territories.find(
            (item) => (item.territory_code ?? item.municipality_code) === code,
          );
          if (match) setFilters({ territoryId: match.id });
        }}
      />
    </div>
  );
}
