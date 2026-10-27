import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  Download,
  FileSpreadsheet,
  FileText,
  LoaderCircle,
  Map,
  Package,
  RefreshCw,
  type LucideIcon,
} from "lucide-react";
import { useContext, useState } from "react";

import { DEFAULT_FILTERS, GlobalFiltersContext } from "../../app/filters";
import { GeographyNotice } from "../../components/GeographyNotice";
import { PageState } from "../../components/PageState";
import {
  downloadReport,
  fetchReports,
  queryKeys,
  type ReportArtifactDTO,
  type ReportKind,
} from "../../lib/api";
import { ExportActions } from "./ExportActions";

const KIND_LABELS: Record<ReportKind, string> = {
  history_csv: "Historial municipal · CSV",
  history_xlsx: "Historial municipal · XLSX",
  scenario_csv: "Escenario A/B · CSV",
  scenario_geojson: "Escenario A/B · GeoJSON",
  scenario_pdf: "Escenario A/B · PDF",
  scenario_map_png: "Mapa A/B · PNG",
  scenario_map_pdf: "Mapa A/B · PDF",
  methodology_pdf: "Reporte metodológico · PDF",
  executive_pdf: "Presentación ejecutiva · PDF",
  technical_zip: "Paquete técnico · ZIP",
};

const INSTITUTIONAL: readonly ReportKind[] = [
  "methodology_pdf",
  "executive_pdf",
  "technical_zip",
];

function kindIcon(kind: ReportKind): LucideIcon {
  if (kind === "technical_zip") return Package;
  if (kind.includes("map")) return Map;
  if (kind.includes("xlsx") || kind.includes("csv")) return FileSpreadsheet;
  return FileText;
}

const KIND_ICONS: Record<ReportKind, LucideIcon> = {
  history_csv: kindIcon("history_csv"),
  history_xlsx: kindIcon("history_xlsx"),
  scenario_csv: kindIcon("scenario_csv"),
  scenario_geojson: kindIcon("scenario_geojson"),
  scenario_pdf: kindIcon("scenario_pdf"),
  scenario_map_png: kindIcon("scenario_map_png"),
  scenario_map_pdf: kindIcon("scenario_map_pdf"),
  methodology_pdf: kindIcon("methodology_pdf"),
  executive_pdf: kindIcon("executive_pdf"),
  technical_zip: kindIcon("technical_zip"),
};

function formatBytes(value: number): string {
  if (value < 1024) return `${value} B`;
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KiB`;
  return `${(value / (1024 * 1024)).toFixed(1)} MiB`;
}

function ArtifactRow({ artifact }: { artifact: ReportArtifactDTO }) {
  const [error, setError] = useState<string | null>(null);
  const mutation = useMutation({
    mutationFn: () => downloadReport(artifact),
    onError: (mutationError) => {
      setError(
        mutationError instanceof Error
          ? mutationError.message
          : "No se pudo descargar el archivo.",
      );
    },
  });
  const Icon = KIND_ICONS[artifact.kind];
  return (
    <li className="artifact-row">
      <div className="artifact-row__identity">
        <Icon aria-hidden="true" size={20} strokeWidth={1.8} />
        <div>
          <p className="artifact-row__title">{KIND_LABELS[artifact.kind]}</p>
          <p className="artifact-row__meta">
            {formatBytes(artifact.size_bytes)} · sha256{" "}
            <code>{artifact.sha256.slice(0, 12)}…</code> ·{" "}
            {new Date(artifact.created_at).toLocaleString("es-MX")}
          </p>
          {error ? (
            <p className="artifact-row__error" role="alert">
              {error}
            </p>
          ) : null}
        </div>
      </div>
      <button
        type="button"
        className="button button--secondary"
        aria-busy={mutation.isPending}
        disabled={mutation.isPending}
        onClick={() => mutation.mutate()}
      >
        {mutation.isPending ? (
          <LoaderCircle aria-hidden="true" className="spin" size={16} strokeWidth={1.8} />
        ) : (
          <Download aria-hidden="true" size={16} strokeWidth={1.8} />
        )}
        {mutation.isPending ? "Descargando…" : "Descargar"}
      </button>
    </li>
  );
}

export function ReportsPage() {
  const filters = useContext(GlobalFiltersContext) ?? DEFAULT_FILTERS;
  const queryClient = useQueryClient();
  const reportsQuery = useQuery({
    queryKey: queryKeys.reports(),
    queryFn: ({ signal }) => fetchReports({ signal }),
    staleTime: 15_000,
  });

  if (reportsQuery.isPending) {
    return (
      <div className="page reports-page">
        <ReportsHeading />
        <PageState
          variant="loading"
          title="Cargando reportes"
          message="Consultando los artefactos generados y las exportaciones disponibles."
        />
      </div>
    );
  }

  if (reportsQuery.isError) {
    return (
      <div className="page reports-page">
        <ReportsHeading />
        <PageState
          variant="error"
          headingLevel={1}
          title="No se pudieron cargar los reportes"
          message={
            reportsQuery.error instanceof Error
              ? reportsQuery.error.message
              : "La consulta de reportes no está disponible."
          }
          action={
            <button
              type="button"
              className="button button--primary"
              onClick={() => void reportsQuery.refetch()}
            >
              <RefreshCw aria-hidden="true" size={16} strokeWidth={1.8} />
              Reintentar consulta
            </button>
          }
        />
      </div>
    );
  }

  const artifacts = reportsQuery.data?.items ?? [];
  const institutional = artifacts.filter((artifact) =>
    INSTITUTIONAL.includes(artifact.kind),
  );
  const small = artifacts.filter(
    (artifact) => !INSTITUTIONAL.includes(artifact.kind),
  );

  return (
    <div className="page reports-page">
      <ReportsHeading />
      <GeographyNotice />

      <section className="summary-card" aria-labelledby="history-exports-heading">
        <div className="card-heading">
          <div>
            <h2 id="history-exports-heading">Exportaciones de historia municipal</h2>
            <p>
              Se generan en el servidor con los filtros actuales. Los valores nulos
              permanecen vacíos; el archivo incluye fuentes, versión del modelo,
              corte y diccionario. No se sustituyen ceros ni se estiman personas.
            </p>
          </div>
        </div>
        <ExportActions
          caption="Historia agregada con filtros actuales"
          request={{
            territory_id: filters.territoryId,
            year: filters.historicalYear,
          }}
          actions={[
            {
              kind: "history_csv",
              label: "Descargar historial CSV",
              description:
                "CSV con metadatos, fuentes y valores nulos preservados.",
            },
            {
              kind: "history_xlsx",
              label: "Descargar historial XLSX",
              description:
                "Libro con hojas de datos, metadatos y diccionario.",
            },
          ]}
          onGenerated={() =>
            void queryClient.invalidateQueries({ queryKey: queryKeys.reports() })
          }
        />
      </section>

      <section className="summary-card" aria-labelledby="institutional-heading">
        <div className="card-heading">
          <div>
            <h2 id="institutional-heading">Documentos institucionales</h2>
            <p>
              El reporte metodológico, la presentación ejecutiva y el paquete técnico
              sólo se sirven después de generarlos con la CLI. No hay cola ni estado
              pendiente: si no existen, la interfaz lo indica sin ofrecer un botón falso.
            </p>
          </div>
          <span className="status-pill status-pill--neutral">CLI</span>
        </div>
        {institutional.length === 0 ? (
          <div className="inline-alert inline-alert--warning" role="status">
            <AlertTriangle aria-hidden="true" size={20} strokeWidth={1.8} />
            <p>
              Aún no hay documentos institucionales generados. Ejecute
              <code> participa_geo.cli deliver --scenario-id &lt;UUID&gt; --output-dir dist/hackathon --team-slug participa-geo</code>
              en un entorno con acceso a GeoServer y a la base de datos.
            </p>
          </div>
        ) : (
          <ul className="artifact-list" aria-label="Documentos institucionales generados">
            {institutional.map((artifact) => (
              <ArtifactRow key={artifact.report_id} artifact={artifact} />
            ))}
          </ul>
        )}
      </section>

      <section className="summary-card" aria-labelledby="generated-heading">
        <div className="card-heading">
          <div>
            <h2 id="generated-heading">Exportaciones pequeñas generadas</h2>
            <p>
              Artefactos de historia y escenario generados desde la API. Cada uno
              conserva su hash SHA-256 y su archivo se descarga sin exponer rutas
              locales del servidor.
            </p>
          </div>
          <button
            type="button"
            className="button button--secondary"
            onClick={() => void reportsQuery.refetch()}
          >
            <RefreshCw aria-hidden="true" size={16} strokeWidth={1.8} />
            Actualizar
          </button>
        </div>
        {small.length === 0 ? (
          <PageState
            variant="empty"
            title="Sin exportaciones pequeñas"
            message="Genere una exportación de historia o de escenario y aparecerá aquí con su hash y acción de descarga."
          />
        ) : (
          <ul className="artifact-list" aria-label="Exportaciones pequeñas generadas">
            {small.map((artifact) => (
              <ArtifactRow key={artifact.report_id} artifact={artifact} />
            ))}
          </ul>
        )}
      </section>

      <section className="summary-card reports-note" aria-labelledby="reports-note-heading">
        <h2 id="reports-note-heading">Límites de la entrega</h2>
        <p>
          Los reportes son agregados municipales. No contienen datos personales ni
          permiten inferencia individual. Las cartas firmadas, la cesión de derechos
          y el envío final son pasos humanos fuera de la API, los contenedores y el
          repositorio público.
        </p>
      </section>
    </div>
  );
}

function ReportsHeading() {
  return (
    <div className="page-heading">
      <p className="eyebrow">Entrega institucional · Jalisco</p>
      <h1>Reportes y exportaciones</h1>
      <p className="page-heading__lead">
        Descargue historia agregada y escenarios con metadatos, fuentes y hashes.
        Los documentos institucionales se generan por CLI para que la entrega sea
        reproducible y revisable.
      </p>
    </div>
  );
}
