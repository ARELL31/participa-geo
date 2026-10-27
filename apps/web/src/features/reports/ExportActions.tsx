import { useMutation } from "@tanstack/react-query";
import { AlertTriangle, Download, LoaderCircle } from "lucide-react";
import { useState } from "react";

import {
  createReport,
  downloadReport,
  type ReportArtifactDTO,
  type ReportKind,
  type ReportRequest,
} from "../../lib/api";

export type ExportAction = {
  kind: ReportKind;
  label: string;
  description?: string;
};

type ExportActionsProps = {
  actions: readonly ExportAction[];
  request: Omit<ReportRequest, "kind">;
  onGenerated?: (artifact: ReportArtifactDTO) => void;
  /** Optional heading; the buttons remain usable without it. */
  caption?: string;
};

/**
 * Generates real report artifacts synchronously and downloads them. There is no
 * fake button: an action only renders a control for a kind the API supports, a
 * duplicate click is blocked while one export is in flight, and errors are shown
 * with the server's problem detail.
 */
export function ExportActions({
  actions,
  request,
  onGenerated,
  caption,
}: ExportActionsProps) {
  const [pendingKind, setPendingKind] = useState<ReportKind | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: async (kind: ReportKind) => {
      const artifact = await createReport({ ...request, kind });
      await downloadReport(artifact);
      return artifact;
    },
    onMutate: (kind) => {
      setPendingKind(kind);
      setError(null);
      setMessage(null);
    },
    onSuccess: (artifact) => {
      setPendingKind(null);
      setMessage(
        `Archivo generado: ${artifact.filename || artifact.kind} (${artifact.size_bytes.toLocaleString("es-MX")} bytes, sha256 ${artifact.sha256.slice(0, 12)}…).`,
      );
      onGenerated?.(artifact);
    },
    onError: (mutationError) => {
      setPendingKind(null);
      setError(
        mutationError instanceof Error
          ? mutationError.message
          : "No se pudo generar la exportación.",
      );
    },
  });

  const pending = mutation.isPending;

  return (
    <div className="export-actions">
      {caption ? <p className="export-actions__caption">{caption}</p> : null}
      <div className="export-actions__buttons" role="group" aria-label={caption ?? "Exportaciones"}>
        {actions.map((action) => {
          const active = pendingKind === action.kind;
          return (
            <button
              key={action.kind}
              type="button"
              className="button button--secondary"
              aria-busy={active}
              disabled={pending}
              title={action.description}
              onClick={() => mutation.mutate(action.kind)}
            >
              {active ? (
                <LoaderCircle
                  aria-hidden="true"
                  className="spin"
                  size={16}
                  strokeWidth={1.8}
                />
              ) : (
                <Download aria-hidden="true" size={16} strokeWidth={1.8} />
              )}
              {active ? "Generando…" : action.label}
            </button>
          );
        })}
      </div>
      {error ? (
        <div className="inline-alert inline-alert--warning" role="alert">
          <AlertTriangle aria-hidden="true" size={20} strokeWidth={1.8} />
          <p>{error}</p>
        </div>
      ) : null}
      <p className="export-actions__status" role="status" aria-live="polite">
        {message ?? ""}
      </p>
    </div>
  );
}
