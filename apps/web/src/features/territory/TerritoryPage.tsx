import { useQuery } from "@tanstack/react-query";
import { RefreshCw } from "lucide-react";

import {
  HISTORICAL_YEARS,
  isElectionYear,
  useGlobalFilters,
} from "../../app/filters";
import { GeographyNotice } from "../../components/GeographyNotice";
import { PageState } from "../../components/PageState";
import {
  fetchHistory,
  fetchMunicipalityFeatures,
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
  const { territoryId, historicalYear, setFilters } = useGlobalFilters();

  const territoriesQuery = useQuery({
    queryKey: queryKeys.territories("14"),
    queryFn: ({ signal }) => fetchTerritories({ stateCode: "14", signal }),
    staleTime: 5 * 60_000,
  });

  const seriesQuery = useQuery({
    queryKey: queryKeys.historySeries({ territoryId, historicalYear }),
    queryFn: ({ signal }) =>
      fetchHistory({ territoryId, pageSize: 125, signal }),
    staleTime: 60_000,
  });

  const featuresQuery = useQuery({
    queryKey: queryKeys.municipalFeatures(historicalYear),
    queryFn: ({ signal }) =>
      fetchMunicipalityFeatures(historicalYear, signal),
    staleTime: 60_000,
  });

  const territories = territoriesQuery.data?.items ?? [];
  const selectedTerritory = territoryId
    ? territories.find((item) => item.id === territoryId)
    : undefined;
  const selectedMunicipalityCode = selectedTerritory?.municipality_code ?? null;

  // Guard against any stale envelope whose territory does not match the URL.
  const records =
    seriesQuery.data?.items.filter(
      (record) => record.territory_id === territoryId,
    ) ?? [];
  const rows = historyRows(records);
  const selectedRecord = rows.find((row) => row.year === historicalYear)?.record;

  const territoryLabel = selectedTerritory
    ? `${selectedTerritory.name} · ${selectedTerritory.municipality_code}`
    : "Agregado estatal de Jalisco";

  return (
    <div className="page territory-page">
      <header className="page-heading">
        <p className="eyebrow">Observatorio · Jalisco</p>
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
                {item.municipality_code} · {item.name}
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
              : "125 municipios de referencia INE."}
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

        <div className="filter-static">
          <span className="filter-static__label">Estado</span>
          <span className="filter-static__value">Jalisco · 14</span>
          <span className="filter-static__hint">Cobertura del MVP</span>
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
              onClick={() => void seriesQuery.refetch()}
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
                  Observación histórica {historicalYear}. {selectedRecord?.eligible === false
                    ? "El registro no es elegible para comparación."
                    : "Tasas calculadas sobre la fuente CCPC."}
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
                  {formatRateOrInsufficient(selectedRecord?.participation_pct)}
                </dd>
                <p className="kpi__note">Porcentaje de la lista nominal.</p>
              </div>
              <div className="kpi">
                <dt>Abstención</dt>
                <dd data-testid="kpi-abstention">
                  {formatRateOrInsufficient(selectedRecord?.abstention_pct)}
                </dd>
                <p className="kpi__note">
                  Nunca se sustituye un dato ausente por cero.
                </p>
              </div>
              <div className="kpi">
                <dt>NS (no especificados)</dt>
                <dd data-testid="kpi-ns">
                  {formatCount(selectedRecord?.ns)}
                </dd>
                <p className="kpi__note">
                  {selectedRecord
                    ? `${formatShare(selectedRecord.unknown_share)} de la lista nominal.`
                    : "Sin dato de participación de NS."}
                </p>
              </div>
              <div className="kpi">
                <dt>Universo conocido</dt>
                <dd data-testid="kpi-known">
                  {selectedRecord
                    ? formatCount(
                        knownUniverse(selectedRecord.ln, selectedRecord.ns),
                      )
                    : "No disponible"}
                </dd>
                <p className="kpi__note">LN − NS. Conteo absoluto, no una tasa.</p>
              </div>
            </dl>

            <p className="source-note">
              Fuente: CCPC Jalisco, cortes {HISTORICAL_YEARS[0]}–{HISTORICAL_YEARS.at(-1)}.
              Referencia cartográfica: 15 de diciembre de 2025. Los agregados
              estatales suman conteos antes de recalcular tasas.
            </p>
          </section>

          <HistoryChart
            rows={rows}
            selectedYear={historicalYear}
            territoryLabel={territoryLabel}
          />
        </>
      )}

      <MunicipalMap
        year={historicalYear}
        features={featuresQuery.data}
        featuresLoading={featuresQuery.isPending}
        featuresError={featuresQuery.isError}
        selectedMunicipalityCode={selectedMunicipalityCode}
        onSelectMunicipality={(code) => {
          const match = territories.find(
            (item) => item.municipality_code === code,
          );
          if (match) setFilters({ territoryId: match.id });
        }}
      />
    </div>
  );
}
