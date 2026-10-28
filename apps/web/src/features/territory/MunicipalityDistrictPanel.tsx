import { useQuery } from "@tanstack/react-query";

import { DataTable } from "../../components/DataTable";
import { PageState } from "../../components/PageState";
import {
  fetchMunicipalityDistrictIntersections,
  queryKeys,
  type MunicipalityDistrictDTO,
} from "../../lib/api";
import { formatCount, formatShare } from "./format";

type Props = {
  territoryId: string;
  kind: "municipality" | "district";
  onSelectDistrict?(row: MunicipalityDistrictDTO): void;
  onSelectMunicipality?(row: MunicipalityDistrictDTO): void;
};

export function MunicipalityDistrictPanel({
  territoryId,
  kind,
  onSelectDistrict,
  onSelectMunicipality,
}: Props) {
  const query = useQuery({
    queryKey: queryKeys.municipalityDistricts(territoryId),
    queryFn: ({ signal }) => fetchMunicipalityDistrictIntersections(territoryId, signal),
    staleTime: 5 * 60_000,
  });
  const rows = query.data?.items ?? [];
  const districtView = kind === "district";
  const caption = districtView ? "Municipios que intersectan el distrito" : "Distritos que intersectan el municipio";

  if (query.isPending) return <p role="status">Cargando intersecciones territoriales…</p>;
  if (query.isError) {
    return <PageState variant="error" title="No se pudieron cargar las intersecciones" message="Los agregados municipio×distrito no están disponibles." action={<button type="button" className="button button--secondary" onClick={() => void query.refetch()}>Reintentar</button>} />;
  }
  if (rows.length === 0) return <p role="status">No hay intersecciones publicadas para este territorio.</p>;

  return (
    <section className="intersection-panel" aria-labelledby="intersection-heading">
      <div className="card-heading">
        <div>
          <h2 id="intersection-heading">{caption}</h2>
          <p>Intersecciones cartográficas MGS del marco 2023. Los conteos de cada fila sólo incluyen secciones vinculadas a geometría; los totales distritales observados incluyen todas las secciones CCPC asignadas al DEF2023 oficial. La cobertura mide la conciliación MGS por separado.</p>
        </div>
      </div>
      <DataTable
        caption={caption}
        rows={rows}
        rowKey={(row) => `${row.municipality_code}-${row.district_code}`}
        columns={[
          ...(districtView ? [{ key: "municipality", header: "Municipio", render: (row: MunicipalityDistrictDTO) => onSelectMunicipality ? <button type="button" className="button button--link" onClick={() => onSelectMunicipality(row)}>{row.municipality_name ?? row.municipality_code} · {row.municipality_code}</button> : `${row.municipality_name ?? row.municipality_code} · ${row.municipality_code}` }] : []),
          ...(districtView ? [] : [{ key: "district", header: "Distrito · marco 2023", render: (row: MunicipalityDistrictDTO) => onSelectDistrict ? <button type="button" className="button button--link" onClick={() => onSelectDistrict(row)}>{row.district_name ?? `Distrito ${row.district_code}`} · marco 2023</button> : `${row.district_name ?? `Distrito ${row.district_code}`} · marco 2023` }]),
          { key: "sections", header: "Secciones", align: "right" as const, render: (row: MunicipalityDistrictDTO) => `${formatCount(row.section_count)} · ${formatShare(row.section_share)} de las secciones municipales` },
          { key: "ln", header: "LN 2024", align: "right" as const, render: (row: MunicipalityDistrictDTO) => row.ln === null ? "No disponible" : `${formatCount(row.ln)} · ${row.ln_share === null ? "No disponible" : formatShare(row.ln_share)}` },
          { key: "abstention", header: "Abstención 2024", align: "right" as const, render: (row: MunicipalityDistrictDTO) => row.abstention_pct === null ? "Información insuficiente" : `${row.abstention_pct.toFixed(1)} %` },
          { key: "coverage", header: "Cobertura distrital", align: "right" as const, render: (row: MunicipalityDistrictDTO) => row.coverage_share === null ? "Información insuficiente" : formatShare(row.coverage_share) },
        ]}
      />
    </section>
  );
}
