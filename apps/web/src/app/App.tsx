import { useCallback, useEffect, useMemo, useState } from "react";

import { TerritoryPage } from "../features/territory/TerritoryPage";
import { NationalPanel } from "../features/national/NationalPanel";
import { PredictionPage } from "../features/prediction/PredictionPage";
import { ScenarioPage } from "../features/scenarios/ScenarioPage";
import { ReportsPage } from "../features/reports/ReportsPage";
import { ApplicationShell } from "../components/ApplicationShell";
import { PageState } from "../components/PageState";
import {
  DEFAULT_FILTERS,
  GlobalFiltersContext,
  parseFilters,
  serializeFilters,
  type GlobalFilters,
  type GlobalFiltersContextValue,
} from "./filters";
import { navigate, resolveModule, usePathname } from "./navigation";

type FilterState =
  | { filters: GlobalFilters; error: null }
  | { filters: GlobalFilters; error: RangeError };

function readFilters(): FilterState {
  try {
    return {
      filters: parseFilters(new URLSearchParams(window.location.search)),
      error: null,
    };
  } catch (error) {
    return {
      filters: DEFAULT_FILTERS,
      error:
        error instanceof RangeError
          ? error
          : new RangeError("Los filtros de la URL no son válidos."),
    };
  }
}

export function App() {
  const pathname = usePathname();
  const [state, setState] = useState<FilterState>(readFilters);

  useEffect(() => {
    const onPopState = () => setState(readFilters());
    window.addEventListener("popstate", onPopState);
    return () => window.removeEventListener("popstate", onPopState);
  }, []);

  const setFilters = useCallback((next: Partial<GlobalFilters>) => {
    setState((previous) => {
      if (previous.error) return previous;
      const filters: GlobalFilters = { ...previous.filters, ...next };
      const query = serializeFilters(filters).toString();
      const nextUrl = `${window.location.pathname}${query ? `?${query}` : ""}${window.location.hash}`;
      window.history.replaceState(null, "", nextUrl);
      return { filters, error: null };
    });
  }, []);

  const resetFilters = useCallback(() => {
    const query = serializeFilters(DEFAULT_FILTERS).toString();
    window.history.replaceState(
      null,
      "",
      `${window.location.pathname}?${query}${window.location.hash}`,
    );
    setState({ filters: DEFAULT_FILTERS, error: null });
  }, []);

  const contextValue = useMemo<GlobalFiltersContextValue>(
    () => ({ ...state.filters, setFilters }),
    [state.filters, setFilters],
  );

  const moduleId = resolveModule(pathname);

  let content;
  if (state.error) {
    content = (
      <div className="page">
        <PageState
          variant="error"
          headingLevel={1}
          title="Filtros no válidos"
          message={`${state.error.message} Corrija la dirección o restablezca los filtros para continuar.`}
          action={
            <button type="button" className="button button--primary" onClick={resetFilters}>
              Restablecer filtros
            </button>
          }
        />
      </div>
    );
  } else if (moduleId === "executive") {
    content = <NationalPanel />;
  } else if (moduleId === "territory") {
    content = <TerritoryPage />;
  } else if (moduleId === "prediction") {
    content = <PredictionPage />;
  } else if (moduleId === "scenarios") {
    content = <ScenarioPage />;
  } else if (moduleId === "reports") {
    content = <ReportsPage />;
  } else {
    content = (
      <div className="page">
        <PageState
          variant="error"
          headingLevel={1}
          title="Página no encontrada"
          message="La dirección solicitada no corresponde a un módulo de PARTICIPA-GEO."
          action={
            <a
              className="button button--primary"
              href="/"
              onClick={(event) => {
                event.preventDefault();
                navigate("/");
              }}
            >
              Volver al panel
            </a>
          }
        />
      </div>
    );
  }

  return (
    <GlobalFiltersContext.Provider value={contextValue}>
      <ApplicationShell pathname={pathname}>{content}</ApplicationShell>
    </GlobalFiltersContext.Provider>
  );
}
