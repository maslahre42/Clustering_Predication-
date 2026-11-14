import { MATERIAL_TYPES, type DatasetSummary } from "../lib/api";
import { formatDate, formatInt } from "../lib/format";
import { Panel } from "./Panel";
import { TechDetails } from "./TechDetails";
import { EmptyState, ErrorState, LoadingState } from "./states";

/**
 * KPI overview from GET /api/summary. These counts describe the active
 * dataset — observed data; nothing here is predicted or synthetic. The title
 * sentence is generated from the data (never hardcoded numbers); validation
 * counts and source name are technical and live in the collapsible details.
 */
export function KpiOverview({
  summary,
  loading,
  error,
}: {
  summary: DatasetSummary | null;
  loading: boolean;
  error: string | null;
}) {
  const insight =
    summary !== null && typeof summary.n_locations === "number"
      ? `${summary.n_locations.toLocaleString("en-US")} glass-container locations · ${formatDate(summary.date_min)} → ${formatDate(summary.date_max)}`
      : null;

  return (
    <Panel
      title="2 · Dataset overview (observed)"
      subtitle="What this shows: the scope of the uploaded fill-level readings. Why it matters: every forecast and route below is built only on this observed data."
      testid="kpi-panel"
    >
      {insight !== null ? (
        <p className="mb-2 text-sm font-semibold text-slate-800" data-testid="kpi-insight">
          {insight}
        </p>
      ) : null}
      {loading ? <LoadingState label="Loading summary" /> : null}
      {error !== null && !loading ? <ErrorState label="Could not load summary" hint={error} /> : null}
      {!loading && error === null && summary === null ? (
        <EmptyState label="No dataset loaded" hint="Upload a CSV above to populate the dashboard." />
      ) : null}
      {!loading && error === null && summary !== null ? (
        <div>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6" data-testid="kpi-grid">
            <Kpi label="Rows" value={formatInt(summary.n_rows, "rows")} />
            <Kpi label="Locations" value={formatInt(summary.n_locations, "locations")} />
            <Kpi label="Series" value={formatInt(summary.n_series, "series")} />
            <Kpi
              label="Date range"
              value={`${formatDate(summary.date_min)} → ${formatDate(summary.date_max)}`}
            />
            {MATERIAL_TYPES.map((material) => (
              <Kpi
                key={material}
                label={`${material} glass`}
                value={formatInt(summary.rows_per_material?.[material] ?? 0, "rows")}
              />
            ))}
          </div>
          {/* Technical metrics into the collapsible details (jury-usability pass). */}
          <div className="mt-2">
            <TechDetails label="Technical details" testid="kpi-tech-details">
              <p>Validation: errors {summary.n_errors} · warnings {summary.n_warnings}</p>
              <p>Source file: {summary.source_name}</p>
            </TechDetails>
          </div>
        </div>
      ) : null}
    </Panel>
  );
}

function Kpi({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border border-slate-200 bg-slate-50 px-3 py-2">
      <p className="text-xs font-medium uppercase tracking-wide text-slate-500">{label}</p>
      <p className="mt-0.5 text-sm font-semibold text-slate-900" data-testid="kpi-value">
        {value}
      </p>
    </div>
  );
}
