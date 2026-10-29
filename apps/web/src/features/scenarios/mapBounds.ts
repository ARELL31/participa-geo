import type { FeatureCollection, Geometry, Position } from "geojson";

export type MapBounds = [[number, number], [number, number]];

type BoundsAccumulator = {
  minLon: number;
  minLat: number;
  maxLon: number;
  maxLat: number;
};

function visitPosition(position: Position, acc: BoundsAccumulator): void {
  const [lon, lat] = position;
  if (
    typeof lon !== "number" ||
    typeof lat !== "number" ||
    !Number.isFinite(lon) ||
    !Number.isFinite(lat)
  ) {
    return;
  }
  acc.minLon = Math.min(acc.minLon, lon);
  acc.maxLon = Math.max(acc.maxLon, lon);
  acc.minLat = Math.min(acc.minLat, lat);
  acc.maxLat = Math.max(acc.maxLat, lat);
}

function visitCoordinates(value: unknown, acc: BoundsAccumulator): void {
  if (!Array.isArray(value)) return;
  if (value.length === 2 && typeof value[0] === "number" && typeof value[1] === "number") {
    visitPosition(value as Position, acc);
    return;
  }
  for (const child of value) visitCoordinates(child, acc);
}

function visitGeometry(geometry: Geometry | null, acc: BoundsAccumulator): void {
  if (!geometry) return;
  if (geometry.type === "GeometryCollection") {
    for (const child of geometry.geometries) visitGeometry(child, acc);
    return;
  }
  visitCoordinates(geometry.coordinates, acc);
}

/**
 * Bounds of the actual GeoJSON received by the A/B map.
 *
 * The map must not assume Jalisco: a national scenario can be in any state.
 * Returns null when there are no finite coordinates, so the caller can show
 * the explicit table/error state instead of reframing to a false location.
 */
export function featureCollectionBounds(
  collection: FeatureCollection,
): MapBounds | null {
  const acc: BoundsAccumulator = {
    minLon: Number.POSITIVE_INFINITY,
    minLat: Number.POSITIVE_INFINITY,
    maxLon: Number.NEGATIVE_INFINITY,
    maxLat: Number.NEGATIVE_INFINITY,
  };
  for (const feature of collection.features) {
    visitGeometry(feature.geometry as Geometry | null, acc);
  }
  if (
    !Number.isFinite(acc.minLon) ||
    !Number.isFinite(acc.minLat) ||
    !Number.isFinite(acc.maxLon) ||
    !Number.isFinite(acc.maxLat)
  ) {
    return null;
  }
  return [
    [acc.minLon, acc.minLat],
    [acc.maxLon, acc.maxLat],
  ];
}
