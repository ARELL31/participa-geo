import { AlertTriangle, LoaderCircle } from "lucide-react";
import type {
  ExpressionSpecification,
  Map as MapLibreMap,
  StyleSpecification,
} from "maplibre-gl";
import { useEffect, useMemo, useRef, useState } from "react";
import maplibreWorkerUrl from "maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url";
import "maplibre-gl/dist/maplibre-gl.css";

import { RiskBadge } from "../../components/RiskBadge";
import type {
  MunicipalityFeatureCollection,
  ScenarioDTO,
} from "../../lib/api";

const JALISCO_BOUNDS: [[number, number], [number, number]] = [
  [-105.8, 18.2],
  [-101.4, 22.2],
];

const RISK_COLORS = {
  low: "#EADDE2",
  medium: "#AD536D",
  high: "#6F1739",
  insufficient: "#D4D0D1",
} as const;

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

type RiskField = "risk_a" | "risk_b";

function fillColorExpression(riskField: RiskField): ExpressionSpecification {
  return [
    "match",
    ["get", riskField],
    "low",
    RISK_COLORS.low,
    "medium",
    RISK_COLORS.medium,
    "high",
    RISK_COLORS.high,
    "insufficient",
    RISK_COLORS.insufficient,
    RISK_COLORS.insufficient,
  ] as ExpressionSpecification;
}

type ScenarioMapPanelProps = {
  label: string;
  description: string;
  data: MunicipalityFeatureCollection;
  riskField: RiskField;
};

function ScenarioMapPanel({
  label,
  description,
  data,
  riskField,
}: ScenarioMapPanelProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const [state, setState] = useState<"loading" | "ready" | "error">("loading");

  useEffect(() => {
    if (!supportsWebGl()) {
      setState("error");
      return;
    }
    const container = containerRef.current;
    if (!container) return;

    let disposed = false;
    let map: MapLibreMap | undefined;
    setState("loading");

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
                id: "scenario-background",
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
          instance.addControl(
            new maplibregl.NavigationControl({ showCompass: false }),
            "top-right",
          );
          instance.on("load", () => {
            if (disposed) return;
            instance.fitBounds(JALISCO_BOUNDS, { padding: 20, duration: 0 });
            instance.addSource("scenario-municipalities", {
              type: "geojson",
              data,
            });
            instance.addLayer({
              id: "scenario-municipalities-fill",
              type: "fill",
              source: "scenario-municipalities",
              paint: {
                "fill-color": fillColorExpression(riskField),
                "fill-opacity": 0.9,
              },
            });
            instance.addLayer({
              id: "scenario-municipalities-outline",
              type: "line",
              source: "scenario-municipalities",
              paint: {
                "line-color": "#FFFFFF",
                "line-width": 0.8,
                "line-opacity": 0.9,
              },
            });
            setState("ready");
          });
          instance.on("error", () => {
            if (!disposed) setState("error");
          });
        } catch {
          setState("error");
        }
      })
      .catch(() => {
        if (!disposed) setState("error");
      });

    return () => {
      disposed = true;
      map?.remove();
    };
  }, [data, riskField]);

  return (
    <section
      className="scenario-map"
      aria-labelledby={`${riskField}-map-heading`}
      aria-describedby="scenario-ab-legend"
    >
      <div className="scenario-map__heading">
        <h3 id={`${riskField}-map-heading`}>{label}</h3>
        <p>{description}</p>
      </div>
      {state === "error" ? (
        <div className="inline-alert inline-alert--warning" role="alert">
          <AlertTriangle aria-hidden="true" size={20} strokeWidth={1.8} />
          <p>No se pudo mostrar el mapa A/B. La tabla conserva los valores.</p>
        </div>
      ) : (
        <div className="scenario-map__frame">
          <div
            ref={containerRef}
            className="scenario-map__canvas"
            role="group"
            aria-label={`Mapa ${label} de abstención municipal`}
          />
          {state === "loading" ? (
            <div className="map-loading" role="status">
              <LoaderCircle aria-hidden="true" size={20} strokeWidth={1.8} />
              Cargando mapa…
            </div>
          ) : null}
        </div>
      )}
    </section>
  );
}

type ScenarioMapsProps = {
  scenario: ScenarioDTO;
  features: MunicipalityFeatureCollection | undefined;
  featuresLoading: boolean;
  featuresError: boolean;
};

export function ScenarioMaps({
  scenario,
  features,
  featuresLoading,
  featuresError,
}: ScenarioMapsProps) {
  const data = useMemo<MunicipalityFeatureCollection>(() => {
    const byCode = new Map(
      scenario.results.map((result) => [result.municipality_code, result]),
    );
    if (!features) {
      return { type: "FeatureCollection", features: [] };
    }
    return {
      type: "FeatureCollection",
      features: features.features.map((feature) => {
        const code =
          typeof feature.properties?.municipality_code === "string"
            ? feature.properties.municipality_code
            : "";
        const result = byCode.get(code);
        return {
          ...feature,
          properties: {
            ...feature.properties,
            baseline_value: result?.baseline_abstention_pct ?? null,
            hypothetical_value: result?.hypothetical_abstention_pct ?? null,
            risk_a: result?.risk_a ?? "insufficient",
            risk_b: result?.risk_b ?? "insufficient",
            selected: result?.selected ?? false,
          },
        };
      }),
    };
  }, [features, scenario]);

  return (
    <section className="summary-card scenario-maps" aria-labelledby="scenario-maps-heading">
      <div className="card-heading">
        <div>
          <h2 id="scenario-maps-heading">Comparación cartográfica A/B</h2>
          <p>
            Ambas vistas usan la misma referencia cartográfica, los mismos cortes
            de riesgo y la misma leyenda. La cámara se abre en la misma extensión
            de Jalisco.
          </p>
        </div>
        <span className="status-pill status-pill--neutral">A/B</span>
      </div>

      {featuresError ? (
        <div className="inline-alert inline-alert--warning" role="alert">
          <AlertTriangle aria-hidden="true" size={20} strokeWidth={1.8} />
          <p>
            No se pudo cargar la capa cartográfica municipal. La tabla A/B sigue
            disponible.
          </p>
        </div>
      ) : featuresLoading ? (
        <p className="table-note" role="status">
          Cargando referencia cartográfica municipal…
        </p>
      ) : data.features.length === 0 ? (
        <div className="inline-alert inline-alert--warning" role="status">
          <AlertTriangle aria-hidden="true" size={20} strokeWidth={1.8} />
          <p>
            La capa cartográfica no contiene geometrías para este escenario. La
            tabla A/B sigue disponible.
          </p>
        </div>
      ) : (
        <>
          <div id="scenario-ab-legend" className="scenario-legend" role="group">
            <h3 id="scenario-ab-legend-title">
              Escala compartida A/B — mismos cortes y leyenda
            </h3>
            <p>
              Cortes de riesgo idénticos para A y B: &lt;40 %, 40–&lt;50 %, ≥50 %
              y sin estimación.
            </p>
            <ul>
              <li>
                <span
                  className="scenario-legend__swatch"
                  data-risk="low"
                  aria-hidden="true"
                />
                <RiskBadge risk="low" />
                <span>(&lt;40 %)</span>
              </li>
              <li>
                <span
                  className="scenario-legend__swatch"
                  data-risk="medium"
                  aria-hidden="true"
                />
                <RiskBadge risk="medium" />
                <span>(40–&lt;50 %)</span>
              </li>
              <li>
                <span
                  className="scenario-legend__swatch"
                  data-risk="high"
                  aria-hidden="true"
                />
                <RiskBadge risk="high" />
                <span>(≥50 %)</span>
              </li>
              <li>
                <span
                  className="scenario-legend__swatch"
                  data-risk="insufficient"
                  aria-hidden="true"
                />
                <RiskBadge risk="insufficient" />
                <span>(sin estimación)</span>
              </li>
            </ul>
          </div>

          <div className="scenario-maps__grid">
            <ScenarioMapPanel
              label="A · Línea base 2027"
              description="Predicción publicada antes del ejercicio hipotético."
              data={data}
              riskField="risk_a"
            />
            <ScenarioMapPanel
              label="B · Escenario hipotético 2027"
              description="Mismo municipio tras la reducción solicitada; no es un efecto causal."
              data={data}
              riskField="risk_b"
            />
          </div>
        </>
      )}
    </section>
  );
}
