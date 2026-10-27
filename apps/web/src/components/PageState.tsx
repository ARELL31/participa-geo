import {
  CircleAlert,
  CircleSlash2,
  Clock3,
  LoaderCircle,
  type LucideIcon,
} from "lucide-react";
import type { ReactNode } from "react";

export type PageStateVariant = "loading" | "error" | "empty" | "pending";

type PageStateProps = {
  variant: PageStateVariant;
  title: string;
  message?: string;
  action?: ReactNode;
  children?: ReactNode;
  headingLevel?: 1 | 2;
  className?: string;
};

const ICONS: Record<Exclude<PageStateVariant, "loading">, LucideIcon> = {
  error: CircleAlert,
  empty: CircleSlash2,
  pending: Clock3,
};

const EYEBROWS: Record<PageStateVariant, string> = {
  loading: "Cargando",
  error: "No se pudo completar la consulta",
  empty: "Sin resultados",
  pending: "Pendiente",
};

export function PageState({
  variant,
  title,
  message,
  action,
  children,
  headingLevel = 2,
  className,
}: PageStateProps) {
  const Heading = headingLevel === 1 ? "h1" : "h2";
  const Icon = variant === "loading" ? LoaderCircle : ICONS[variant];

  return (
    <section
      className={`page-state page-state--${variant}${className ? ` ${className}` : ""}`}
      role={variant === "error" ? "alert" : "status"}
      aria-live={variant === "error" ? "assertive" : "polite"}
      aria-busy={variant === "loading" || undefined}
    >
      <div className="page-state__icon" aria-hidden="true">
        <Icon size={24} strokeWidth={1.8} />
      </div>
      <div className="page-state__body">
        <span className="page-state__eyebrow">{EYEBROWS[variant]}</span>
        <Heading>{title}</Heading>
        {message ? <p className="page-state__message">{message}</p> : null}
        {action ? <div className="page-state__action">{action}</div> : null}
        {children}
      </div>
    </section>
  );
}
