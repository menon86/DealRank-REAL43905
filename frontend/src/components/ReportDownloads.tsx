import { useState } from "react";
import { describeError, downloadReport } from "../lib/client";

type ReportKind = "pdf" | "pptx";

interface ReportDownloadsProps {
  dealIds: string[];
  hurdleRate: number;
}

/**
 * The PDF/PPTX download buttons shared by the comparison and ranking
 * views (docs/build-plan.md 6.4). Each button shows its own "Preparing…"
 * state while the backend renders the file, and a failed download
 * surfaces the server's error inline instead of doing nothing.
 */
export function ReportDownloads({ dealIds, hurdleRate }: ReportDownloadsProps) {
  const [pending, setPending] = useState<ReportKind | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleDownload(kind: ReportKind) {
    setPending(kind);
    setError(null);
    try {
      await downloadReport(kind, dealIds, hurdleRate);
    } catch (err) {
      setError(`${kind.toUpperCase()} export failed. ${describeError(err)}`);
    } finally {
      setPending(null);
    }
  }

  const disabled = pending !== null || dealIds.length === 0;

  return (
    <div className="report-downloads">
      <div className="report-downloads-buttons">
        {(["pdf", "pptx"] as const).map((kind) => (
          <button
            key={kind}
            type="button"
            className="secondary"
            disabled={disabled}
            aria-busy={pending === kind}
            onClick={() => handleDownload(kind)}
          >
            {pending === kind ? (
              <>
                <span className="spinner" aria-hidden="true" /> Preparing {kind.toUpperCase()}…
              </>
            ) : (
              `Download ${kind.toUpperCase()}`
            )}
          </button>
        ))}
      </div>
      {error && (
        <div className="status-banner error" role="alert">
          {error}
          <button type="button" className="link" onClick={() => setError(null)}>
            Dismiss
          </button>
        </div>
      )}
    </div>
  );
}
