import { AlertTriangle, LoaderCircle, RefreshCw } from "lucide-react";
import type {
  GeoJSONSource,
  Map as MapLibreMap,
  StyleSpecification,
} from "maplibre-gl";
import { useEffect, useRef, useState } from "react";
// Vite must bundle MapLibre's module worker; without this explicit URL the
// worker request 404s under nginx and the map silently falls back to the table.
import maplibreWorkerUrl from "maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url";
import "maplibre-gl/dist/maplibre-gl.css";

import { DataTable } from "../../components/DataTable";
import type { ElectionYear } from "../../app/filters";
import { featureCollectionBounds } from "../scenarios/mapBounds";
import {
  type HistoryDTO,
  type MunicipalityFeatureCollection,
  type NationalStateFeatureCollection,
} from "../../lib/api";
import { formatRate, formatShare } from "./format";

function supportsWebGl(): boolean {
  if (typeof window === "undefined" || typeof WebGLRenderingContext === "undefined") {
    return false;
  }
  try {
    const canvas = document.createElement("canvas");
    return Boolean(canvas.getContext("webgl2") ?? canvas.getContext("webgl"));
  } catch {
    return false;
  }
}

type MunicipalityRow = {
  code: string;
  name: string;
  participationPct: number | null;
  abstentionPct: number | null;
  unknownShare: number | null;
};

function rowsFromFeatures(
  features: MunicipalityFeatureCollection | undefined,
  observations: HistoryDTO[] | undefined,
  stateCode: string,
  year: ElectionYear,
): MunicipalityRow[] {
  if (!features) return [];
  const observed = new Map((observations ?? []).filter((row) => row.state_code === stateCode && row.year === year).map((row) => [row.municipality_code, row]));
  const rows: MunicipalityRow[] = [];
  for (const feature of features.features.filter((item) => item.properties?.state_code === stateCode)) {
    const properties = feature.properties;
    if (!properties) continue;
    const code = properties.municipality_code;
    if (typeof code !== "string" || code === "") continue;
    const observation = properties.state_code === stateCode ? observed.get(code) : undefined;
    rows.push({
      code,
      name: typeof properties.name === "string" ? properties.name : code,
      participationPct:
        typeof observation?.participation_pct === "number"
          ? observation.participation_pct
          : null,
      abstentionPct:
        typeof observation?.abstention_pct === "number"
          ? observation.abstention_pct
          : null,
      unknownShare:
        typeof observation?.unknown_share === "number"
          ? observation.unknown_share
          : null,
    });
  }
  return rows.sort((a, b) => a.code.localeCompare(b.code));
}

type MunicipalMapProps = {
  year: ElectionYear;
  stateName: string;
  features: MunicipalityFeatureCollection | undefined;
  observations: HistoryDTO[] | undefined;
  stateOutline: NationalStateFeatureCollection | undefined;
  observationsLoading: boolean;
  observationsError: boolean;
  stateOutlineLoading: boolean;
  stateCode: string;
  featuresLoading: boolean;
  featuresError: boolean;
  stateOutlineError: boolean;
  selectedMunicipalityCode: string | null;
  onSelectMunicipality(code: string): void;
};

export function MunicipalMap({
  year,
  stateName,
  features,
  observations,
  stateOutline,
  observationsLoading,
  observationsError,
  stateOutlineLoading,
  stateCode,
  featuresLoading,
  featuresError,
  stateOutlineError,
  selectedMunicipalityCode,
  onSelectMunicipality,
}: MunicipalMapProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<MapLibreMap | null>(null);
  const selectRef = useRef(onSelectMunicipality);
  const [mapReady, setMapReady] = useState(false);
  const [mapError, setMapError] = useState(() => !supportsWebGl());
  const [tableOpen, setTableOpen] = useState(false);
  const boundsRef = useRef<ReturnType<typeof featureCollectionBounds> | null>(null);
  const effectiveObservations = observationsError ? undefined : observations;

  useEffect(() => {
    selectRef.current = onSelectMunicipality;
  }, [onSelectMunicipality]);

  useEffect(() => {
    if (mapError) return;
    const container = containerRef.current;
    if (!container) return;

    let disposed = false;
    let map: MapLibreMap | undefined;
    setMapReady(false);

    void import("maplibre-gl")
      .then((maplibregl) => {
        if (disposed) return;
        try {
          maplibregl.setWorkerUrl(maplibreWorkerUrl);
          const style: StyleSpecification = {
            version: 8,
            sources: {},
            layers: [
              {
                id: "neutral-background",
                type: "background",
                paint: { "background-color": "#F7F6F5" },
              },
            ],
          };
          const instance = new maplibregl.Map({
            container,
            style,
            center: [-102, 23],
            zoom: 4,
            attributionControl: false,
            interactive: true,
          });
          map = instance;
          mapRef.current = instance;
          instance.addControl(
            new maplibregl.NavigationControl({ showCompass: false }),
            "top-right",
          );
          instance.on("load", () => {
            if (disposed) return;
            setMapReady(true);
          });
          instance.on("error", () => {
            if (disposed) return;
            setMapError(true);
            setTableOpen(true);
          });
        } catch {
          setMapError(true);
          setTableOpen(true);
        }
      })
      .catch(() => {
        if (!disposed) {
          setMapError(true);
          setTableOpen(true);
        }
      });

    return () => {
      disposed = true;
      map?.remove();
      mapRef.current = null;
    };
  }, [mapError]);

  // Add or refresh the interactive WFS layer once the style is ready.
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !mapReady) return;

    const observationByCode = new Map((effectiveObservations ?? []).filter((row) => row.state_code === stateCode && row.year === year).map((row) => [row.municipality_code, row]));
    const stateFeatures = (features?.features ?? []).filter((feature) => feature.properties?.state_code === stateCode);
    const data: MunicipalityFeatureCollection = {
      type: "FeatureCollection",
      features: stateFeatures.map((feature) => {
        const code = feature.properties?.municipality_code;
        const row = typeof code === "string" ? observationByCode.get(code) : undefined;
        return { ...feature, properties: { ...feature.properties, abstention_pct: row?.abstention_pct ?? null, participation_pct: row?.participation_pct ?? null, unknown_share: row?.unknown_share ?? null } };
      }),
    };
    const existing = map.getSource("municipalities") as GeoJSONSource | undefined;
    if (existing) {
      existing.setData(data);
      const outlineSource = map.getSource("state-outline") as GeoJSONSource | undefined;
      outlineSource?.setData(stateOutline ? { ...stateOutline, features: stateOutline.features.filter((feature) => feature.properties?.state_code === stateCode) } : { type: "FeatureCollection", features: [] });
      return;
    }

    map.addSource("municipalities", {
      type: "geojson",
      data,
    });
    map.addLayer({
      id: "municipalities-hit",
      type: "fill",
      source: "municipalities",
      paint: { "fill-color": ["case", ["==", ["get", "abstention_pct"], null], "#D8D6D3", ["interpolate", ["linear"], ["get", "abstention_pct"], 0, "#F7E8EE", 100, "#6F1739"]], "fill-opacity": 0.82 },
    });
    map.addLayer({
      id: "municipalities-outline",
      type: "line",
      source: "municipalities",
      paint: { "line-color": "#FFFFFF", "line-width": 0.8, "line-opacity": 0.85 },
    });
    if (!map.getSource("state-outline")) {
      map.addSource("state-outline", { type: "geojson", data: stateOutline ? { ...stateOutline, features: stateOutline.features.filter((feature) => feature.properties?.state_code === stateCode) } : { type: "FeatureCollection", features: [] } });
      map.addLayer({ id: "state-outline-halo", type: "line", source: "state-outline", paint: { "line-color": "#FFFFFF", "line-width": 5 } });
      map.addLayer({ id: "state-outline-line", type: "line", source: "state-outline", paint: { "line-color": "#6F1739", "line-width": 2.5 } });
    } else {
      (map.getSource("state-outline") as GeoJSONSource).setData(stateOutline ? { ...stateOutline, features: stateOutline.features.filter((feature) => feature.properties?.state_code === stateCode) } : { type: "FeatureCollection", features: [] });
    }
    map.addLayer({
      id: "municipalities-selected",
      type: "line",
      source: "municipalities",
      filter: ["==", ["get", "municipality_code"], ""],
      paint: { "line-color": "#6F1739", "line-width": 3 },
    });

    map.on("click", "municipalities-hit", (event) => {
      const feature = event.features?.[0];
      const code = feature?.properties?.municipality_code;
      if (typeof code === "string" && code !== "") {
        selectRef.current(code);
      }
    });
    map.on("mouseenter", "municipalities-hit", () => {
      map.getCanvas().style.cursor = "pointer";
    });
    map.on("mouseleave", "municipalities-hit", () => {
      map.getCanvas().style.cursor = "";
    });
  }, [features, effectiveObservations, stateOutline, stateCode, year, mapReady]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !mapReady) return;
    const outline = stateOutline ? { ...stateOutline, features: stateOutline.features.filter((feature) => feature.properties?.state_code === stateCode) } : undefined;
    const bounds = outline?.features.length ? featureCollectionBounds(outline) : features?.features.length ? featureCollectionBounds({ ...features, features: features.features.filter((feature) => feature.properties?.state_code === stateCode) }) : null;
    boundsRef.current = bounds;
    if (bounds) map.fitBounds(bounds, { padding: 28, duration: 0 });
  }, [stateOutline, stateCode, features, mapReady]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !mapReady) return;
    if (map.getLayer("municipalities-selected")) {
      map.setFilter("municipalities-selected", [
        "==",
        ["get", "municipality_code"],
        selectedMunicipalityCode ?? "",
      ]);
    }
  }, [selectedMunicipalityCode, mapReady]);

  useEffect(() => {
    const container = containerRef.current;
    const map = mapRef.current;
    if (!container || !map || !mapReady || typeof ResizeObserver === "undefined") return;
    const observer = new ResizeObserver(() => {
      map.resize();
      if (boundsRef.current) map.fitBounds(boundsRef.current, { padding: 28, duration: 0 });
    });
    observer.observe(container);
    return () => observer.disconnect();
  }, [mapReady]);

  const rows = rowsFromFeatures(features, effectiveObservations, stateCode, year);
  const showTable = tableOpen || mapError || featuresError || observationsError;

  return (
    <section className="map-card" aria-labelledby="map-heading">
      <div className="card-heading">
        <div>
          <h2 id="map-heading">Mapa de abstención municipal</h2>
          <p>
            {stateOutline?.features.find((feature) => feature.properties?.state_code === stateCode)?.properties?.name ?? stateName} · año {year}. Color por abstención observada; gris indica dato no disponible.
          </p>
        </div>
        {!mapError && !featuresError ? (
          <button
            type="button"
            className="button button--secondary"
            aria-expanded={showTable}
            aria-controls="municipality-table"
            onClick={() => setTableOpen((open) => !open)}
          >
            {showTable ? "Ocultar tabla alternativa" : "Ver tabla alternativa"}
          </button>
        ) : null}
      </div>

      {mapError ? (
        <div className="inline-alert" role="alert">
          <AlertTriangle aria-hidden="true" size={20} strokeWidth={1.8} />
          <div>
            <p>
              No se pudo mostrar el mapa. La tabla de municipios sigue
              disponible.
            </p>
            <button
              type="button"
              className="button button--quiet"
              onClick={() => {
                setMapError(false);
                setMapReady(false);
              }}
            >
              <RefreshCw aria-hidden="true" size={16} strokeWidth={1.8} />
              Reintentar mapa
            </button>
          </div>
        </div>
      ) : (
        <div className="map-frame">
          <div
            ref={containerRef}
            className="map-canvas"
            role="group"
            aria-label={`Mapa de abstención municipal, entidad ${stateCode}, año ${year}`}
            aria-describedby="map-description"
          />
          {!mapReady || featuresLoading || stateOutlineLoading || observationsLoading ? (
            <div className="map-loading" role="status">
              <LoaderCircle aria-hidden="true" size={20} strokeWidth={1.8} />
              Cargando mapa…
            </div>
          ) : null}
        </div>
      )}

      {!mapError ? <p id="map-description" className="map-description">
        El mapa es una referencia visual. La tabla equivalente permite
        seleccionar municipios con teclado y ofrece los mismos valores.
      </p> : null}

      <div className="map-legend" role="group" aria-label="Leyenda de abstención observada">
        <span>0 %</span><span className="map-legend__scale" aria-hidden="true" /><span>100 %</span><span className="map-legend__neutral" />No disponible
      </div>

      {featuresError ? (
        <div className="inline-alert inline-alert--warning" role="status">
          <AlertTriangle aria-hidden="true" size={20} strokeWidth={1.8} />
          <p>
            No se pudo cargar la capa interactiva de municipios. Se mantiene el
            acceso tabular con la información disponible.
          </p>
        </div>
      ) : null}

      {observationsError ? <div className="inline-alert inline-alert--warning" role="alert"><AlertTriangle aria-hidden="true" size={20} /><p>No se pudieron cargar las observaciones del año. El mapa no mostrará tasas residuales; la tabla municipal sigue disponible.</p></div> : null}
      {stateOutlineError ? <div className="inline-alert inline-alert--warning" role="status"><AlertTriangle aria-hidden="true" size={20} /><p>No se pudo cargar el contorno estatal; se encuadra la geometría municipal de respaldo.</p></div> : null}

      {showTable ? (
        <div id="municipality-table" className="map-table">
            {featuresLoading || observationsLoading ? (
            <p className="table-note" role="status">
              Cargando información municipal…
            </p>
          ) : null}
          <DataTable
            caption="Municipios de la entidad seleccionada"
            rows={rows}
            rowKey={(row) => row.code}
            emptyMessage={
              featuresLoading
                ? "Cargando información municipal…"
                : "No hay datos municipales para el año seleccionado."
            }
            rowProps={(row) => ({
              "aria-current":
                row.code === selectedMunicipalityCode ? "true" : undefined,
              className:
                row.code === selectedMunicipalityCode ? "is-selected" : undefined,
            })}
            columns={[
              {
                key: "name",
                header: "Municipio",
                render: (row) => row.name,
              },
              {
                key: "code",
                header: "Código INE",
                render: (row) => row.code,
              },
              {
                key: "participation",
                header: "Participación",
                align: "right",
                render: (row) => formatRate(row.participationPct),
              },
              {
                key: "abstention",
                header: "Abstención",
                align: "right",
                render: (row) => formatRate(row.abstentionPct),
              },
              {
                key: "ns",
                header: "NS",
                align: "right",
                render: (row) => formatShare(row.unknownShare),
              },
              {
                key: "action",
                header: "Acción",
                render: (row) => (
                  <button
                    type="button"
                    className="button button--link"
                    aria-current={
                      row.code === selectedMunicipalityCode ? "true" : undefined
                    }
                    onClick={() => onSelectMunicipality(row.code)}
                  >
                    Seleccionar {row.name}
                  </button>
                ),
              },
            ]}
          />
          <p className="table-note">
            Valores de observación histórica del año {year}; “No disponible”
            significa que la fuente no permite calcular la tasa.
          </p>
        </div>
      ) : null}
    </section>
  );
}
