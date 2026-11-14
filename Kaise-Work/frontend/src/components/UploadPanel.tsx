import { useRef, useState, type FormEvent } from "react";
import {
  ApiError,
  uploadDataset,
  type ApiIssue,
  type DatasetSummary,
  type UploadResponse,
} from "../lib/api";
import { formatDate, formatInt } from "../lib/format";
import { Panel } from "./Panel";
import { ErrorState, LoadingState } from "./states";

/**
 * CSV upload → POST /api/datasets (multipart). Shows the dataset summary and
 * the full validation error/warning lists (§1 rules; §5.3: dataset with errors
 * is not replaced). Uploaded CSV data is observed data, not synthetic.
 */
export function UploadPanel({ onUploaded }: { onUploaded: (summary: DatasetSummary) => void }) {
  const inputRef = useRef<HTMLInputElement | null>(null);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<UploadResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    const file = inputRef.current?.files?.[0];
    if (!file) {
      setError("Choose a CSV file first.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const response = await uploadDataset(file);
      setResult(response);
      // The upload response IS a DatasetSummary (flat, plus errors/warnings).
      onUploaded(response);
    } catch (err) {
      setResult(null);
      setError(err instanceof ApiError ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  function issueLine(issue: ApiIssue, index: number): string {
    const parts: string[] = [];
    // Backend ValidationErrorItem: rule_id, row_number (1-based; 0 = header).
    parts.push(`rule ${issue.rule_id}`);
    parts.push(`row ${issue.row_number}`);
    if (issue.message !== "") parts.push(issue.message);
    else if (issue.value !== undefined && issue.value !== null) parts.push(issue.value);
    return parts.length > 0 ? parts.join(" — ") : JSON.stringify(issue) + ` (#${index})`;
  }

  return (
    <Panel
      title="1 · Upload fill-level data"
      subtitle="CSV per docs/contracts.md §1 (location_id, material_type, date, fill_level). Uploaded data is treated as observed."
      testid="upload-panel"
    >
      <form onSubmit={handleSubmit} className="flex flex-wrap items-center gap-2">
        <input
          ref={inputRef}
          type="file"
          accept=".csv,text/csv"
          className="block w-64 rounded border border-slate-300 bg-white p-1.5 text-sm file:mr-2 file:rounded file:border-0 file:bg-slate-100 file:px-2 file:py-0.5 file:text-sm"
          data-testid="upload-input"
        />
        <button
          type="submit"
          disabled={busy}
          className="rounded bg-sky-700 px-3 py-1.5 text-sm font-medium text-white hover:bg-sky-800 disabled:opacity-50"
          data-testid="upload-submit"
        >
          {busy ? "Uploading…" : "Upload & validate"}
        </button>
      </form>

      {busy ? <div className="mt-3"><LoadingState label="Uploading and validating CSV" /></div> : null}
      {error !== null && !busy ? (
        <div className="mt-3">
          <ErrorState label="Upload failed" hint={error} />
        </div>
      ) : null}

      {result !== null && !busy ? (
        result.errors.length > 0 ? (
          <div className="mt-3 space-y-2" data-testid="upload-errors">
            <div className="rounded-md border border-red-300 bg-red-50 px-3 py-2 text-sm text-red-800">
              <p className="font-semibold">
                Validation failed: {result.errors.length} error
                {result.errors.length === 1 ? "" : "s"}
                {result.warnings.length > 0
                  ? `, ${result.warnings.length} warning${result.warnings.length === 1 ? "" : "s"}`
                  : ""}
                . The dataset was <strong>not</strong> replaced (contract §5.3).
              </p>
            </div>
            <ul className="max-h-48 overflow-auto rounded border border-red-200 bg-white text-xs text-red-700">
              {result.errors.map((issue, i) => (
                <li key={i} className="border-b border-red-100 px-2 py-1 last:border-b-0">
                  {issueLine(issue, i)}
                </li>
              ))}
            </ul>
          </div>
        ) : (
          <div className="mt-3 space-y-2" data-testid="upload-summary">
            {/* UploadResponse extends DatasetSummary — pass it directly. */}
            <SummaryLines summary={result} />
            {result.warnings.length > 0 ? (
              <div className="rounded-md border border-amber-300 bg-amber-50 px-3 py-2 text-xs text-amber-800">
                <p className="font-semibold">{result.warnings.length} warning(s):</p>
                <ul className="list-disc pl-4">
                  {result.warnings.map((issue, i) => (
                    <li key={i}>{issueLine(issue, i)}</li>
                  ))}
                </ul>
              </div>
            ) : null}
          </div>
        )
      ) : null}
    </Panel>
  );
}

function SummaryLines({ summary }: { summary: DatasetSummary }) {
  const materials = Object.entries(summary.rows_per_material ?? {});
  return (
    <div className="rounded-md border border-emerald-300 bg-emerald-50 px-3 py-2 text-sm text-emerald-900">
      <p className="font-semibold">
        Uploaded “{summary.source_name}” — dataset active (errors {summary.n_errors},
        warnings {summary.n_warnings}).
      </p>
      <p className="mt-1">
        {formatInt(summary.n_rows, "rows")} · {formatInt(summary.n_locations, "locations")} ·{" "}
        {formatInt(summary.n_series, "series")} · {formatDate(summary.date_min)} →{" "}
        {formatDate(summary.date_max)}
      </p>
      {materials.length > 0 ? (
        <p className="mt-1 text-xs">
          {materials.map(([material, rows]) => `${material}: ${rows ?? 0} rows`).join(" · ")}
        </p>
      ) : null}
    </div>
  );
}
