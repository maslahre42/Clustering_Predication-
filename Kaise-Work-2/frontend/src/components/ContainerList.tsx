import { useCallback, useEffect, useState } from "react";
import { ApiError, fetchContainers, type SeriesStatus } from "../lib/api";
import { formatDate, formatPct } from "../lib/format";
import { MaterialBadge } from "./Badges";
import { Panel } from "./Panel";
import { EmptyState, ErrorState, LoadingState } from "./states";

const VISIBLE_ROWS = 50;

/**
 * Container (series) list from GET /api/containers: last reading per series,
 * overfull series get a distinct badge (overfull is never coerced to 100, §1.1).
 */
export function ContainerList({ datasetVersion }: { datasetVersion: number }) {
  const [containers, setContainers] = useState<SeriesStatus[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notFound, setNotFound] = useState(false);
  const [showAll, setShowAll] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    setNotFound(false);
    try {
      const data = await fetchContainers();
      if (!Array.isArray(data)) {
        setContainers(null);
        setError("Unexpected /api/containers response shape (expected a list of SeriesStatus)");
      } else {
        setContainers(data);
      }
    } catch (err) {
      if (err instanceof ApiError && err.status === 404) {
        setNotFound(true);
        setContainers(null);
      } else {
        setError(err instanceof ApiError ? err.message : String(err));
      }
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load, datasetVersion]);

  const overfullCount = containers?.filter((c) => c.last_is_overfull).length ?? 0;
  const visible = showAll ? (containers ?? []) : (containers ?? []).slice(0, VISIBLE_ROWS);
  const overfullSharePct =
    containers !== null && containers.length > 0 ? (overfullCount / containers.length) * 100 : null;

  return (
    <Panel
      title="3 · Containers (observed last readings)"
      subtitle="What this shows: the last emptying record per (location, material) series. Why it matters: overfull containers should be collected first — fill is % of container volume; overfull is its own state, never 100 %."
      testid="containers-panel"
    >
      {loading ? <LoadingState label="Loading containers" /> : null}
      {error !== null && !loading ? <ErrorState label="Could not load containers" hint={error} /> : null}
      {notFound && !loading ? (
        <EmptyState label="No dataset loaded" hint="Upload a CSV above to list containers." />
      ) : null}
      {!loading && !notFound && error === null && containers !== null && containers.length === 0 ? (
        <EmptyState label="No containers in dataset" />
      ) : null}
      {!loading && containers !== null && containers.length > 0 ? (
        <div>
          {/* Data-generated insight sentence (numbers come from the API, never hardcoded). */}
          <p className="text-sm font-semibold text-slate-800" data-testid="containers-insight">
            {containers.length.toLocaleString("en-US")} container series — {overfullCount}{" "}
            currently overfull
            {overfullSharePct !== null ? ` (${overfullSharePct.toFixed(1)} % of series)` : ""}
          </p>
          {/* "Show all" stays the FIRST button in the panel (test + keyboard order). */}
          {containers.length > VISIBLE_ROWS ? (
            <button
              type="button"
              onClick={() => setShowAll((s) => !s)}
              className="mt-2 text-xs font-medium text-sky-700 hover:underline"
            >
              {showAll ? "Show fewer" : `Show all ${containers.length} series`}
            </button>
          ) : null}
          <p className="mt-2 text-xs text-slate-500" data-testid="container-count">
            {containers.length} series · {overfullCount} currently overfull
          </p>
          <div className="max-h-72 overflow-auto rounded border border-slate-200">
            <table className="w-full text-left text-xs">
              <thead className="sticky top-0 bg-slate-100 text-slate-600">
                <tr>
                  <th className="px-2 py-1.5">Location</th>
                  <th className="px-2 py-1.5">Material</th>
                  <th className="px-2 py-1.5">Readings</th>
                  <th className="px-2 py-1.5">Last date</th>
                  <th className="px-2 py-1.5">Last fill</th>
                </tr>
              </thead>
              <tbody data-testid="container-rows">
                {visible.map((c) => (
                  <tr key={`${c.location_id}·${c.material_type}`} className="border-t border-slate-100">
                    <td className="px-2 py-1.5 font-mono" title={c.location_id}>
                      {c.location_id.slice(0, 13)}…
                    </td>
                    <td className="px-2 py-1.5">
                      <MaterialBadge material={c.material_type} />
                    </td>
                    <td className="px-2 py-1.5">{c.n_readings}</td>
                    <td className="px-2 py-1.5">{formatDate(c.last_date)}</td>
                    <td className="px-2 py-1.5">
                      {c.last_is_overfull ? (
                        <span
                          className="inline-block rounded border border-red-300 bg-red-100 px-1.5 py-0.5 font-semibold text-red-800"
                          data-testid="overfull-badge"
                        >
                          overfull
                        </span>
                      ) : (
                        formatPct(c.last_fill_pct, 0)
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : null}
    </Panel>
  );
}
