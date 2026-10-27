import { MapPin } from "lucide-react";

/**
 * The approved cartographic disclaimer is always visible next to territorial
 * results. It is informational (`role="note"`), not a dismissible alert.
 */
export function GeographyNotice() {
  return (
    <aside className="geography-notice" role="note" aria-label="Referencia cartográfica">
      <MapPin aria-hidden="true" size={20} strokeWidth={1.8} />
      <p>
        Referencia cartográfica INE: 15 de diciembre de 2025. No implica igualdad
        de límites históricos.
      </p>
    </aside>
  );
}
