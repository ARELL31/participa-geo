import { useCallback, useEffect, useMemo, useState } from "react";

import { TerritoryPage } from "../features/territory/TerritoryPage";
import { ApplicationShell } from "../components/ApplicationShell";
import { PageState } from "../components/PageState";
import { RiskBadge } from "../components/RiskBadge";
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

function PendingModule({
  title,
  message,
  showRiskLegend = false,
}: {
  title: string;
  message: string;
  showRiskLegend?: boolean;
}) {
  return (
    <div className="page">
      <PageState
        variant="pending"
        headingLevel={1}
        title={title}
        message={message}
      >
        {showRiskLegend ? (
          <div className="risk-legend">
            <h2>Escala de riesgo prevista</h2>
            <p>
              Las categorías se muestran siempre con etiqueta textual e icono;
              el gris representa información insuficiente y nunca un cero.
            </p>
            <ul>
              <li>
                <RiskBadge risk="low" /> Abstención estimada por debajo del 40 %.
              </li>
              <li>
                <RiskBadge risk="medium" /> Abstención estimada entre 40 % y 50 %.
              </li>
              <li>
                <RiskBadge risk="high" /> Abstención estimada de 50 % o más.
              </li>
              <li>
                <RiskBadge risk="insufficient" /> Datos insuficientes para estimar.
              </li>
            </ul>
          </div>
        ) : null}
      </PageState>
    </div>
  );
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
  } else if (moduleId === "territory") {
    content = <TerritoryPage />;
  } else if (moduleId === "prediction") {
    content = (
      <PendingModule
        title="Predicción 2027"
        message="El módulo de predicción explicable se implementará en una entrega posterior. Esta pantalla no contiene controles operativos ni datos simulados."
        showRiskLegend
      />
    );
  } else if (moduleId === "scenarios") {
    content = (
      <PendingModule
        title="Escenarios hipotéticos"
        message="La comparación A/B con supuestos trazables se implementará en una entrega posterior. No hay acciones disponibles todavía."
      />
    );
  } else if (moduleId === "reports") {
    content = (
      <PendingModule
        title="Reportes y exportaciones"
        message="La generación y descarga de reportes se implementará en una entrega posterior. No se ofrecen exportaciones ni cifras de ejemplo."
      />
    );
  } else if (moduleId === "not-found") {
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
  } else {
    content = (
      <PendingModule
        title="Panel ejecutivo"
        message="El resumen ejecutivo se implementará en una entrega posterior. No se muestran indicadores de ejemplo."
      />
    );
  }

  return (
    <GlobalFiltersContext.Provider value={contextValue}>
      <ApplicationShell pathname={pathname}>{content}</ApplicationShell>
    </GlobalFiltersContext.Provider>
  );
}
