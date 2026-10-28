import * as Dialog from "@radix-ui/react-dialog";
import {
  FileText,
  GitCompareArrows,
  LayoutDashboard,
  Map,
  Menu,
  TrendingUp,
  X,
  type LucideIcon,
} from "lucide-react";
import { useRef, useState, type ReactNode } from "react";

import type { ModuleId } from "../app/navigation";
import { useGlobalFilters } from "../app/filters";
import { LevelSwitcher } from "./LevelSwitcher";
import {
  isActivePath,
  NAVIGATION,
  navigate,
  pathWithCurrentFilters,
} from "../app/navigation";

const ICONS: Record<Exclude<ModuleId, "not-found">, LucideIcon> = {
  executive: LayoutDashboard,
  territory: Map,
  prediction: TrendingUp,
  scenarios: GitCompareArrows,
  reports: FileText,
};

type NavigationListProps = {
  pathname: string;
  onNavigate?: () => void;
};

function NavigationList({ pathname, onNavigate }: NavigationListProps) {
  return (
    <nav className="navigation" aria-label="Navegación principal">
      <p className="navigation__label">Módulos</p>
      <ul className="navigation__list">
        {NAVIGATION.map((item) => {
          const Icon = ICONS[item.id];
          const active = isActivePath(pathname, item.path);
          return (
            <li key={item.path}>
              <a
                className="navigation__link"
                href={pathWithCurrentFilters(item.path)}
                aria-current={active ? "page" : undefined}
                onClick={(event) => {
                  if (
                    event.metaKey ||
                    event.ctrlKey ||
                    event.shiftKey ||
                    event.altKey ||
                    event.button !== 0
                  ) {
                    return;
                  }
                  event.preventDefault();
                  navigate(pathWithCurrentFilters(item.path));
                  onNavigate?.();
                }}
              >
                <Icon aria-hidden="true" size={20} strokeWidth={1.8} />
                <span className="navigation__text">
                  <span className="navigation__name">{item.label}</span>
                  <span className="navigation__description">{item.description}</span>
                </span>
                {item.status === "pending" ? (
                  <span className="navigation__status">Pendiente</span>
                ) : null}
              </a>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}

function Brand() {
  return (
    <div className="brand">
      <span className="brand__mark" aria-hidden="true">
        PG
      </span>
      <span className="brand__text">
        <span className="brand__name">PARTICIPA-GEO</span>
        <span className="brand__tagline">Observatorio de participación</span>
      </span>
    </div>
  );
}

type ApplicationShellProps = {
  pathname: string;
  children: ReactNode;
};

export function ApplicationShell({ pathname, children }: ApplicationShellProps) {
  const { stateCode, level } = useGlobalFilters();
  const [mobileOpen, setMobileOpen] = useState(false);
  const menuButtonRef = useRef<HTMLButtonElement | null>(null);

  return (
    <div className="app-shell">
      <a className="skip-link" href="#contenido">
        Saltar al contenido
      </a>

      <aside className="sidebar" aria-label="Barra lateral">
        <Brand />
        <NavigationList pathname={pathname} />
        <div className="sidebar__footer">
          <p>Cobertura: 32 entidades</p>
          <p>Fuente: INE · CCPC</p>
        </div>
      </aside>

      <div className="app-body">
        <header className="app-header">
          <button
            ref={menuButtonRef}
            type="button"
            className="mobile-menu-button"
            aria-label="Abrir menú de navegación"
            aria-haspopup="dialog"
            aria-expanded={mobileOpen}
            onClick={() => setMobileOpen(true)}
          >
            <Menu aria-hidden="true" size={24} strokeWidth={1.8} />
          </button>
          <div className="app-header__identity">
            <span className="app-header__product">PARTICIPA-GEO</span>
            <span className="app-header__context">
              Inteligencia territorial · {stateCode === "all" ? "Nacional" : "México"}
            </span>
          </div>
          <LevelSwitcher />
          <div className="app-header__meta" aria-label="Corte de datos y objetivo">
            <span>Corte de referencia: 15 dic 2025</span>
            {level === "municipality" ? <span className="app-header__target">Predicción 2027 · año fijo</span> : <span className="app-header__target">Observado 2024 · marco 2023</span>}
          </div>
        </header>

        <main id="contenido" tabIndex={-1} className="app-main">
          {children}
        </main>

        <footer className="app-footer">
          <p>
            PARTICIPA-GEO · MVP de analítica territorial. Datos agregados por
            municipio; sin información personal.
          </p>
        </footer>
      </div>

      <Dialog.Root open={mobileOpen} onOpenChange={setMobileOpen}>
        <Dialog.Portal>
          <Dialog.Overlay className="dialog-overlay" />
          <Dialog.Content
            className="dialog-content"
            aria-describedby="mobile-nav-description"
            onCloseAutoFocus={(event) => {
              event.preventDefault();
              menuButtonRef.current?.focus();
            }}
          >
            <div className="dialog-content__header">
              <Dialog.Title className="dialog-content__title">
                Navegación
              </Dialog.Title>
              <Dialog.Close asChild>
                <button
                  type="button"
                  className="icon-button"
                  aria-label="Cerrar menú de navegación"
                >
                  <X aria-hidden="true" size={24} strokeWidth={1.8} />
                </button>
              </Dialog.Close>
            </div>
            <Dialog.Description id="mobile-nav-description" className="visually-hidden">
              Módulos disponibles y pendientes de PARTICIPA-GEO.
            </Dialog.Description>
            <NavigationList
              pathname={pathname}
              onNavigate={() => setMobileOpen(false)}
            />
            <p className="dialog-content__footer">Cobertura: Jalisco · Fuente: INE</p>
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>
    </div>
  );
}
