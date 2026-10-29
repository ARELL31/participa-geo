import { describe, expect, it } from "vitest";

import type { MunicipalityFeatureCollection } from "../../lib/api";
import { featureCollectionBounds } from "./mapBounds";

function collection(
  coordinates: [number, number][][][],
): MunicipalityFeatureCollection {
  return {
    type: "FeatureCollection",
    features: coordinates.map((rings, index) => ({
      type: "Feature" as const,
      id: `municipality-${index}`,
      geometry: { type: "Polygon" as const, coordinates: rings },
      properties: {
        state_code: "19",
        municipality_code: String(index + 1).padStart(3, "0"),
        name: `Municipio ${index + 1}`,
      },
    })),
  } as MunicipalityFeatureCollection;
}

describe("featureCollectionBounds", () => {
  it("uses the geometry extent instead of a fixed Jalisco frame", () => {
    const bounds = featureCollectionBounds(
      collection([
        [
          [
            [-100.4, 25.2],
            [-99.8, 25.2],
            [-99.8, 25.9],
            [-100.4, 25.9],
            [-100.4, 25.2],
          ],
        ],
      ]),
    );

    expect(bounds).toEqual([
      [-100.4, 25.2],
      [-99.8, 25.9],
    ]);
  });

  it("covers every feature so both A/B panels share the same frame", () => {
    const bounds = featureCollectionBounds(
      collection([
        [
          [
            [-103.4, 20.6],
            [-103.2, 20.6],
            [-103.2, 20.8],
            [-103.4, 20.8],
            [-103.4, 20.6],
          ],
        ],
        [
          [
            [-102.0, 19.4],
            [-101.5, 19.4],
            [-101.5, 20.1],
            [-102.0, 20.1],
            [-102.0, 19.4],
          ],
        ],
      ]),
    );

    expect(bounds).toEqual([
      [-103.4, 19.4],
      [-101.5, 20.8],
    ]);
  });

  it("ignores non-finite coordinates and returns null for empty collections", () => {
    const withBroken = collection([
      [
        [
          [-100, 25],
          [Number.NaN, 25],
          [-99, 26],
          [-100, 26],
          [-100, 25],
        ],
      ],
    ]);

    expect(featureCollectionBounds(withBroken)).toEqual([
      [-100, 25],
      [-99, 26],
    ]);
    expect(
      featureCollectionBounds({ type: "FeatureCollection", features: [] }),
    ).toBeNull();
  });
});
