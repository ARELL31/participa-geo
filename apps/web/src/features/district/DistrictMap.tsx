import type { Geometry } from "geojson";

import type { DistrictFeatureCollection } from "../../lib/api";

function coordinates(geometry: Geometry): number[][] {
  if (geometry.type === "Polygon") return geometry.coordinates.flat();
  if (geometry.type === "MultiPolygon") return geometry.coordinates.flat(2);
  return [];
}

function rings(geometry: Geometry): number[][][] {
  if (geometry.type === "Polygon") return geometry.coordinates as number[][][];
  if (geometry.type === "MultiPolygon") return geometry.coordinates.flat() as number[][][];
  return [];
}

export function DistrictMap({
  features,
  selectedCode,
}: {
  features: DistrictFeatureCollection;
  selectedCode: string;
}) {
  const points = features.features.flatMap((feature) => feature.geometry ? coordinates(feature.geometry) : []);
  if (points.length === 0) return <p role="status">No hay geometría distrital disponible para mostrar; la tabla de agregados sigue disponible.</p>;
  const minX = Math.min(...points.map(([x]) => x!));
  const maxX = Math.max(...points.map(([x]) => x!));
  const minY = Math.min(...points.map(([, y]) => y!));
  const maxY = Math.max(...points.map(([, y]) => y!));
  const width = Math.max(maxX - minX, 0.001);
  const height = Math.max(maxY - minY, 0.001);
  const project = ([longitude, latitude]: number[]): [number, number] => [
    16 + ((longitude! - minX) / width) * 608,
    16 + ((maxY - latitude!) / height) * 328,
  ];
  return (
    <figure className="district-map">
      <svg viewBox="0 0 640 360" role="img" aria-label={`Mapa del marco distrital 2023; seleccionado Distrito ${selectedCode}`}>
        {features.features.map((feature, featureIndex) => {
          const code = feature.properties?.district_code;
          return rings(feature.geometry).map((ring, ringIndex) => {
            const path = ring.map((point, index) => {
              const [x, y] = project(point);
              return `${index === 0 ? "M" : "L"}${x.toFixed(2)},${y.toFixed(2)}`;
            }).join(" ") + " Z";
            return <path key={`${feature.id ?? featureIndex}-${ringIndex}`} d={path} fill={code === selectedCode ? "#6f1739" : "#e8e4e2"} stroke="#fff" strokeWidth="1.2" />;
          });
        })}
      </svg>
      <figcaption>Geometría de referencia del marco 2023. Las tasas observadas y su cobertura se consultan en la tabla; no se infieren del color del mapa.</figcaption>
    </figure>
  );
}
