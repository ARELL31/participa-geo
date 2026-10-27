import { AlertTriangle, LoaderCircle, RefreshCw } from "lucide-react";
import type {
  GeoJSONSource,
  Map as MapLibreMap,
  RasterTileSource,
  StyleSpecification,
} from "maplibre-gl";
import { useEffect, useRef, useState } from "react";
// Vite must bundle MapLibre's module worker; without this explicit URL the
// worker request 404s under nginx and the map silently falls back to the table.
import maplibreWorkerUrl from "maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url";
import "maplibre-gl/dist/maplibre-gl.css";

import { DataTable } from "../../components/DataTable";
import type { ElectionYear } from "../../app/filters";
import {
  wmsAbstentionTileUrl,
  type MunicipalityFeatureCollection,
} from "../../lib/api";
import { formatRate, formatShare } from "./format";

const JALISCO_BOUNDS: [[number, number], [number, number]] = [
  [-105.8, 18.2],
  [-101.4, 22.2],
];

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
): MunicipalityRow[] {
  if (!features) return [];
  const rows: MunicipalityRow[] = [];
  for (const feature of features.features) {
    const properties = feature.properties;
    if (!properties) continue;
    const code = properties.municipality_code;
    if (typeof code !== "string" || code === "") continue;
    rows.push({
      code,
      name: typeof properties.name === "string" ? properties.name : code,
      participationPct:
        typeof properties.participation_pct === "number"
          ? properties.participation_pct
          : null,
      abstentionPct:
        typeof properties.abstention_pct === "number"
          ? properties.abstention_pct
          : null,
      unknownShare:
        typeof properties.unknown_share === "number"
          ? properties.unknown_share
          : null,
    });
  }
  return rows.sort((a, b) => a.code.localeCompare(b.code));
}

type MunicipalMapProps = {
  year: ElectionYear;
  features: MunicipalityFeatureCollection | undefined;
  featuresLoading: boolean;
  featuresError: boolean;
  selectedMunicipalityCode: string | null;
  onSelectMunicipality(code: string): void;
};

export function MunicipalMap({
  year,
  features,
  featuresLoading,
  featuresError,
  selectedMunicipalityCode,
  onSelectMunicipality,
}: MunicipalMapProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<MapLibreMap | null>(null);
  const selectRef = useRef(onSelectMunicipality);
  const [mapReady, setMapReady] = useState(false);
  const [mapError, setMapError] = useState(false);
  const [tableOpen, setTableOpen] = useState(false);

  useEffect(() => {
    selectRef.current = onSelectMunicipality;
  }, [onSelectMunicipality]);

  useEffect(() => {
    if (featuresError) setTableOpen(true);
  }, [featuresError]);

  useEffect(() => {
    if (mapError) return;
    if (!supportsWebGl()) {
      setMapError(true);
      setTableOpen(true);
      return;
    }
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
            center: [-103.45, 20.5],
            zoom: 6.1,
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
            instance.fitBounds(JALISCO_BOUNDS, { padding: 24, duration: 0 });
            instance.addSource("wms-abstention", {
              type: "raster",
              tiles: [wmsAbstentionTileUrl(year)],
              tileSize: 256,
            });
            instance.addLayer({
              id: "wms-abstention",
              type: "raster",
              source: "wms-abstention",
              paint: { "raster-opacity": 0.9 },
            });
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
  }, [year, mapError]);

  // Add or refresh the interactive WFS layer once the style is ready.
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !mapReady) return;

    const data = features ?? { type: "FeatureCollection", features: [] };
    const existing = map.getSource("municipalities") as GeoJSONSource | undefined;
    if (existing) {
      existing.setData(data);
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
      paint: { "fill-color": "#6F1739", "fill-opacity": 0.02 },
    });
    map.addLayer({
      id: "municipalities-outline",
      type: "line",
      source: "municipalities",
      paint: { "line-color": "#FFFFFF", "line-width": 0.8, "line-opacity": 0.85 },
    });
    map.addLayer({
      id: "municipalities-selected",
      type: "line",
      source: "municipalities",
      filter: ["==", ["get", "municipality_code"], selectedMunicipalityCode ?? ""],
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
  }, [features, mapReady, selectedMunicipalityCode]);

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
    const raster = map.getSource("wms-abstention") as RasterTileSource | undefined;
    if (raster) {
      raster.setTiles([wmsAbstentionTileUrl(year)]);
    }
  }, [selectedMunicipalityCode, year, mapReady]);

  const rows = rowsFromFeatures(features);
  const showTable = tableOpen || mapError || featuresError;

  return (
    <section className="map-card" aria-labelledby="map-heading">
      <div className="card-heading">
        <div>
          <h2 id="map-heading">Mapa de abstención municipal</h2>
          <p>
            Capa WMS de referencia y selección municipal mediante WFS. No se
            usan mosaicos externos.
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
            aria-label={`Mapa de abstención municipal, año ${year}`}
            aria-describedby="map-description"
          />
          {!mapReady ? (
            <div className="map-loading" role="status">
              <LoaderCircle aria-hidden="true" size={20} strokeWidth={1.8} />
              Cargando mapa…
            </div>
          ) : null}
          <p id="map-description" className="map-description">
            El mapa es una referencia visual. La tabla equivalente permite
            seleccionar municipios con teclado y ofrece los mismos valores.
          </p>
        </div>
      )}

      {featuresError ? (
        <div className="inline-alert inline-alert--warning" role="status">
          <AlertTriangle aria-hidden="true" size={20} strokeWidth={1.8} />
          <p>
            No se pudo cargar la capa interactiva de municipios. Se mantiene el
            acceso tabular con la información disponible.
          </p>
        </div>
      ) : null}

      {showTable ? (
        <div id="municipality-table" className="map-table">
          {featuresLoading ? (
            <p className="table-note" role="status">
              Cargando información municipal…
            </p>
          ) : null}
          <DataTable
            caption="Municipios de Jalisco"
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
