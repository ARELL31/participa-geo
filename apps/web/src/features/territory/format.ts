const rateFormatter = new Intl.NumberFormat("es-MX", {
  minimumFractionDigits: 1,
  maximumFractionDigits: 1,
});

const countFormatter = new Intl.NumberFormat("es-MX", {
  maximumFractionDigits: 0,
});

/** Rates are points (0–100). A missing value is never rendered as zero. */
export function formatRate(value: number | null | undefined): string {
  if (value === null || value === undefined || !Number.isFinite(value)) {
    return "No disponible";
  }
  return `${rateFormatter.format(value)} %`;
}

export function formatRateOrInsufficient(value: number | null | undefined): string {
  if (value === null || value === undefined || !Number.isFinite(value)) {
    return "Información insuficiente";
  }
  return `${rateFormatter.format(value)} %`;
}

/** Shares are fractions (0–1); the UI shows them as percentages. */
export function formatShare(value: number | null | undefined): string {
  if (value === null || value === undefined || !Number.isFinite(value)) {
    return "No disponible";
  }
  return `${rateFormatter.format(value * 100)} %`;
}

export function formatCount(value: number | null | undefined): string {
  if (value === null || value === undefined || !Number.isFinite(value)) {
    return "No disponible";
  }
  return countFormatter.format(value);
}

export function knownUniverse(ln: number, ns: number): number {
  return Math.max(0, ln - ns);
}
