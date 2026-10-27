import { useSyncExternalStore } from "react";

export type ModuleId =
  | "executive"
  | "territory"
  | "prediction"
  | "scenarios"
  | "reports"
  | "not-found";

export type NavigationItem = {
  id: Exclude<ModuleId, "not-found">;
  path: string;
  label: string;
  description: string;
  status: "available" | "pending";
};

export const NAVIGATION: readonly NavigationItem[] = [
  {
    id: "executive",
    path: "/",
    label: "Panel ejecutivo",
    description: "Resumen de cobertura y señales territoriales",
    status: "pending",
  },
  {
    id: "territory",
    path: "/territory",
    label: "Inteligencia territorial",
    description: "Historia municipal y referencia cartográfica",
    status: "available",
  },
  {
    id: "prediction",
    path: "/prediction",
    label: "Predicción",
    description: "Abstención estimada para 2027",
    status: "pending",
  },
  {
    id: "scenarios",
    path: "/scenarios",
    label: "Escenarios",
    description: "Comparación hipotética A/B",
    status: "pending",
  },
  {
    id: "reports",
    path: "/reports",
    label: "Reportes",
    description: "Exportaciones verificables",
    status: "pending",
  },
] as const;

const NAVIGATE_EVENT = "participa-geo:navigate";

function subscribe(callback: () => void): () => void {
  window.addEventListener("popstate", callback);
  window.addEventListener(NAVIGATE_EVENT, callback);
  return () => {
    window.removeEventListener("popstate", callback);
    window.removeEventListener(NAVIGATE_EVENT, callback);
  };
}

function getSnapshot(): string {
  return window.location.pathname;
}

function getServerSnapshot(): string {
  return "/";
}

export function usePathname(): string {
  return useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot);
}

export function navigate(href: string): void {
  const current = `${window.location.pathname}${window.location.search}`;
  if (current === href) return;
  window.history.pushState(null, "", href);
  window.dispatchEvent(new Event(NAVIGATE_EVENT));
}

/** Keep the global filters when moving between modules. */
export function pathWithCurrentFilters(path: string): string {
  return `${path}${window.location.search}`;
}

export function resolveModule(pathname: string): ModuleId {
  const match = NAVIGATION.find((item) => item.path === pathname);
  return match?.id ?? "not-found";
}

export function isActivePath(pathname: string, path: string): boolean {
  return pathname === path;
}
