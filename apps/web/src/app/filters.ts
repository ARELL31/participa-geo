import { createContext, useContext } from "react";

/** The six CCPC election years accepted by the historical API and UI. */
export const HISTORICAL_YEARS = [2009, 2012, 2015, 2018, 2021, 2024] as const;

export type ElectionYear = (typeof HISTORICAL_YEARS)[number];
export type TerritoryLevel = "municipality" | "federal_district";
export type StateCode = "all" | `${number}${number}`;

export type GlobalFilters = {
  level: TerritoryLevel;
  stateCode: StateCode;
  territoryId: string | null;
  historicalYear: ElectionYear;
};

export type GlobalFiltersContextValue = GlobalFilters & {
  setFilters(next: Partial<GlobalFilters>): void;
};

/** The 2027 forecast is a separate, fixed target — never a historical filter. */
export const TARGET_YEAR = 2027 as const;

export const DEFAULT_FILTERS: GlobalFilters = Object.freeze({
  level: "municipality",
  stateCode: "all",
  territoryId: null,
  historicalYear: 2024,
});

const UUID_PATTERN =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

export function isElectionYear(value: unknown): value is ElectionYear {
  return HISTORICAL_YEARS.includes(value as ElectionYear);
}

/**
 * Parse the global filters from a URL.
 *
 * An unknown historical year, a non-integer year or a malformed territory UUID
 * throws `RangeError` so the shell can offer a filter reset instead of silently
 * loading a different query or a blank screen.
 */
export function parseFilters(params: URLSearchParams): GlobalFilters {
  const rawLevel = params.get("level");
  const level: TerritoryLevel = rawLevel === null || rawLevel === ""
    ? "municipality"
    : rawLevel === "municipality" || rawLevel === "federal_district"
      ? rawLevel
      : (() => { throw new RangeError(`Nivel no permitido: ${rawLevel}.`); })();

  // `state` is canonical for the UI. Keep accepting the API's historical
  // `state_code` parameter so bookmarks and API-linked URLs continue to work.
  const rawState = params.get("state") ?? params.get("state_code");
  const stateValue = rawState?.trim() ?? "all";
  if (stateValue !== "all" && !/^(0[1-9]|[12][0-9]|3[0-2])$/.test(stateValue)) {
    throw new RangeError(`Entidad no permitida: ${stateValue}. Use all o 01–32.`);
  }
  const stateCode = stateValue as StateCode;

  const rawYear = params.get("year");
  let historicalYear: ElectionYear = DEFAULT_FILTERS.historicalYear;

  if (rawYear !== null && rawYear.trim() !== "") {
    const candidate = Number(rawYear);
    if (!Number.isInteger(candidate) || !isElectionYear(candidate)) {
      throw new RangeError(
        `Año histórico no permitido: ${rawYear}. Use 2009, 2012, 2015, 2018, 2021 o 2024.`,
      );
    }
    historicalYear = candidate;
  }

  const rawTerritory = params.get("territory_id");
  let territoryId: string | null = null;
  if (rawTerritory !== null && rawTerritory.trim() !== "") {
    if (!UUID_PATTERN.test(rawTerritory)) {
      throw new RangeError("El identificador de municipio no es un UUID válido.");
    }
    territoryId = rawTerritory;
  }

  return { level, stateCode, territoryId, historicalYear };
}

/** Serialize filters into the URL. `target_year` is intentionally absent. */
export function serializeFilters(filters: GlobalFilters): URLSearchParams {
  const params = new URLSearchParams();
  params.set("level", filters.level);
  params.set("state", filters.stateCode);
  if (filters.territoryId) {
    params.set("territory_id", filters.territoryId);
  }
  params.set("year", String(filters.historicalYear));
  return params;
}

export const GlobalFiltersContext =
  createContext<GlobalFiltersContextValue | null>(null);

/** Access the global filters. Must be used below `GlobalFiltersContext.Provider`. */
export function useGlobalFilters(): GlobalFiltersContextValue {
  const value = useContext(GlobalFiltersContext);
  if (!value) {
    throw new Error("useGlobalFilters must be used inside GlobalFiltersContext");
  }
  return value;
}
