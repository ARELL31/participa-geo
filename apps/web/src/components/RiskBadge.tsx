import { CircleCheck, CircleHelp, CircleMinus, TriangleAlert } from "lucide-react";

export type RiskLevel = "low" | "medium" | "high" | "insufficient";

const CONFIG = {
  low: { label: "Riesgo bajo", Icon: CircleCheck },
  medium: { label: "Riesgo medio", Icon: CircleMinus },
  high: { label: "Riesgo alto", Icon: TriangleAlert },
  insufficient: { label: "Información insuficiente", Icon: CircleHelp },
} as const satisfies Record<RiskLevel, { label: string; Icon: typeof CircleCheck }>;

type RiskBadgeProps = {
  risk: RiskLevel;
  unstable?: boolean;
};

/**
 * Risk is always conveyed with text and an icon, never by colour alone.
 * ``insufficient`` is deliberately neutral grey, never a green/zero value.
 */
export function RiskBadge({ risk, unstable = false }: RiskBadgeProps) {
  const { label, Icon } = CONFIG[risk];
  return (
    <span className="risk-badge" data-risk={risk}>
      <Icon aria-hidden="true" size={16} strokeWidth={1.8} />
      <span>{label}</span>
      {unstable ? <span className="risk-badge__unstable">Inestable</span> : null}
    </span>
  );
}
