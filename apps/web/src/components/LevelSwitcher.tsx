import { useGlobalFilters } from "../app/filters";

const STATES = [
  ["01", "Aguascalientes"], ["02", "Baja California"], ["03", "Baja California Sur"], ["04", "Campeche"],
  ["05", "Coahuila"], ["06", "Colima"], ["07", "Chiapas"], ["08", "Chihuahua"], ["09", "Ciudad de México"],
  ["10", "Durango"], ["11", "Guanajuato"], ["12", "Guerrero"], ["13", "Hidalgo"], ["14", "Jalisco"],
  ["15", "México"], ["16", "Michoacán"], ["17", "Morelos"], ["18", "Nayarit"], ["19", "Nuevo León"],
  ["20", "Oaxaca"], ["21", "Puebla"], ["22", "Querétaro"], ["23", "Quintana Roo"], ["24", "San Luis Potosí"],
  ["25", "Sinaloa"], ["26", "Sonora"], ["27", "Tabasco"], ["28", "Tamaulipas"], ["29", "Tlaxcala"],
  ["30", "Veracruz"], ["31", "Yucatán"], ["32", "Zacatecas"],
] as const;

export function LevelSwitcher() {
  const { level, stateCode, setFilters } = useGlobalFilters();
  return (
    <div className="global-filters" aria-label="Filtros territoriales">
      <div className="filter-field global-filters__level">
        <label htmlFor="level-filter">Nivel territorial</label>
        <select
          id="level-filter"
          value={level}
          onChange={(event) => {
            const nextLevel = event.target.value;
            if (nextLevel === "municipality" || nextLevel === "federal_district") {
              setFilters({ level: nextLevel, territoryId: null });
            }
          }}
        >
          <option value="municipality">Municipio</option>
          <option value="federal_district">Distrito federal</option>
        </select>
      </div>
      <div className="filter-field global-filters__state">
        <label htmlFor="state-filter">Entidad</label>
        <select
          id="state-filter"
          value={stateCode}
          onChange={(event) => setFilters({ stateCode: event.target.value as typeof stateCode, territoryId: null })}
          aria-describedby="state-filter-hint"
        >
          <option value="all">Todas las entidades</option>
          {STATES.map(([code, name]) => (
            <option key={code} value={code}>
              {name} · {code}
            </option>
          ))}
        </select>
        <span id="state-filter-hint" className="visually-hidden">
          Seleccione una entidad para consultar sus territorios.
        </span>
      </div>
    </div>
  );
}
