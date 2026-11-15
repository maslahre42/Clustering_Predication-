import { useEffect, useMemo, useState } from "react";
import {
  ApiError,
  fetchDaysToFull,
  MATERIAL_TYPES,
  type DaysToFullResponse,
  type MaterialType,
} from "../lib/api";
import { t, tf, type Lang, type TranslationKey } from "../lib/i18n";
import { MaterialBadge } from "./Badges";
import { Panel } from "./Panel";
import { EmptyState, ErrorState, LoadingState } from "./states";

/**
 * W9 (M16 v4): per-container interval view over the §5.2.3 v2 days-to-full
 * rows. Basis labels: rates/days-to-full are [predicted] estimates derived
 * from the observed emptying records (§1.5) — never shown as measurements.
 * Rows flagged `is_lower_bound` are censored lower bounds → the "at least"
 * marker; rows without an estimate carry their API reason, never a fabricated
 * value. The mandatory §1.5 caveat is rendered verbatim from the API's
 * `assumptions` right beside the rates.
 */

const VISIBLE_ROWS = 50;

export interface ContainersIntervalPanelProps {
  lang: Lang;
  datasetVersion: number;
}

type MaterialFilter = "all" | MaterialType;

export function ContainersIntervalPanel({ lang, datasetVersion }: ContainersIntervalPanelProps) {
  const [payload, setPayload] = useState<DaysToFullResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notFound, setNotFound] = useState(false);
  const [showAll, setShowAll] = useState(false);

  // Filters — state only; never a data assumption.
  const [material, setMaterial] = useState<MaterialFilter>("all");
  const [onlyLowerBound, setOnlyLowerBound] = useState(false);
  const [onlyWithoutEstimate, setOnlyWithoutEstimate] = useState(false);
  const [search, setSearch] = useState("");

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    setNotFound(false);
    setPayload(null);
    fetchDaysToFull()
      .then((data) => {
        if (cancelled) return;
        if (
          typeof data?.stats !== "object" ||
          data.stats === null ||
          !Array.isArray(data.series)
        ) {
          setError("Unexpected /api/days-to-full response shape (missing stats/series)");
          return;
        }
        setPayload(data);
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        if (err instanceof ApiError && err.status === 404) {
          setNotFound(true); // no dataset → empty state (§5.3)
        } else {
          setError(err instanceof ApiError ? err.message : String(err));
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [datasetVersion]);

  const filtered = useMemo(() => {
    const series = payload?.series ?? [];
    return series.filter((row) => {
      if (material !== "all" && row.material_type !== material) return false;
      if (onlyLowerBound && !row.is_lower_bound) return false;
      if (onlyWithoutEstimate && row.days_to_full !== null) return false;
      if (search !== "" && !row.location_id.toLowerCase().startsWith(search.toLowerCase())) {
        return false;
      }
      return true;
    });
  }, [payload, material, onlyLowerBound, onlyWithoutEstimate, search]);

  const visible = showAll ? filtered : filtered.slice(0, VISIBLE_ROWS);
  const targetPct = payload?.target_pct;

  return (
    <Panel
      title={t(lang, "containers.interval.title")}
      subtitle={t(lang, "containers.interval.subtitle")}
      testid="containers-interval"
    >
      {loading ? <LoadingState label={t(lang, "containers.interval.loading")} /> : null}
      {error !== null && !loading ? (
        <ErrorState label={t(lang, "containers.interval.error")} hint={error} />
      ) : null}
      {notFound && !loading && error === null ? (
        <EmptyState label={t(lang, "containers.interval.noDataset")} />
      ) : null}

      {!loading && error === null && !notFound && payload !== null ? (
        <div>
          {/* Filters first (keyboard order): material, lower-bound, no-estimate, search. */}
          <div className="flex flex-wrap items-center gap-3 text-xs text-slate-700" data-testid="interval-filters">
            <label>
              <span className="mr-1 font-medium">{t(lang, "containers.interval.material")}</span>
              <select
                value={material}
                onChange={(e) => setMaterial(e.target.value as MaterialFilter)}
                data-testid="interval-filter-material"
                className="rounded border border-slate-300 px-1 py-0.5"
              >
                <option value="all">{t(lang, "containers.interval.allMaterials")}</option>
                {MATERIAL_TYPES.map((m) => (
                  <option key={m} value={m}>
                    {t(lang, `legend.${m}` as TranslationKey)}
                  </option>
                ))}
              </select>
            </label>
            <label className="flex items-center gap-1">
              <input
                type="checkbox"
                checked={onlyLowerBound}
                onChange={(e) => setOnlyLowerBound(e.target.checked)}
                data-testid="interval-filter-lowerbound"
              />
              {t(lang, "containers.interval.onlyLowerBound")}
            </label>
            <label className="flex items-center gap-1">
              <input
                type="checkbox"
                checked={onlyWithoutEstimate}
                onChange={(e) => setOnlyWithoutEstimate(e.target.checked)}
                data-testid="interval-filter-noestimate"
              />
              {t(lang, "containers.interval.onlyWithoutEstimate")}
            </label>
            <label className="flex items-center gap-1">
              <span className="font-medium">{t(lang, "containers.interval.search")}</span>
              <input
                type="text"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder={t(lang, "containers.interval.searchPlaceholder")}
                data-testid="interval-filter-search"
                className="w-56 rounded border border-slate-300 px-1 py-0.5"
              />
            </label>
            <button
              type="button"
              onClick={() => setShowAll((s) => !s)}
              className="text-sky-700 hover:underline"
            >
              {showAll
                ? t(lang, "containers.interval.showFewer")
                : tf(lang, "containers.interval.showAll", { n: filtered.length })}
            </button>
          </div>
          <p className="mt-2 text-xs text-slate-500" data-testid="interval-count">
            {tf(lang, "containers.interval.count", {
              shown: visible.length,
              total: filtered.length.toLocaleString("en-US"),
              all: (payload.series.length ?? 0).toLocaleString("en-US"),
            })}
          </p>
          {visible.length === 0 ? (
            <div className="mt-2">
              <EmptyState label={t(lang, "containers.interval.noMatches")} />
            </div>
          ) : (
            <div className="mt-2 max-h-80 overflow-auto rounded border border-slate-200">
              <table className="w-full text-left text-xs">
                <thead className="sticky top-0 bg-slate-100 text-slate-600">
                  <tr>
                    <th className="px-2 py-1.5">{t(lang, "containers.interval.colLocation")}</th>
                    <th className="px-2 py-1.5">{t(lang, "containers.interval.colMaterial")}</th>
                    <th className="px-2 py-1.5">{t(lang, "col.rate")}</th>
                    <th className="px-2 py-1.5">{t(lang, "col.medianInterval")}</th>
                    <th className="px-2 py-1.5">
                      {targetPct !== undefined && targetPct !== null
                        ? tf(lang, "col.daysToFull", { pct: `${targetPct} %` })
                        : t(lang, "col.daysToFullPlain")}
                    </th>
                    <th className="px-2 py-1.5">{t(lang, "col.predictedFullDate")}</th>
                  </tr>
                </thead>
                <tbody data-testid="interval-rows">
                  {visible.map((row) => (
                    <tr key={`${row.location_id}·${row.material_type}`} className="border-t border-slate-100">
                      <td className="px-2 py-1.5 font-mono" title={row.location_id}>
                        {row.location_id.length <= 13
                          ? row.location_id
                          : `${row.location_id.slice(0, 13)}…`}
                      </td>
                      <td className="px-2 py-1.5">
                        <MaterialBadge material={row.material_type} />
                      </td>
                      <td className="px-2 py-1.5">
                        {row.rate_pct_per_day !== null
                          ? `${row.rate_pct_per_day.toFixed(2)} pp/d`
                          : "—"}
                      </td>
                      <td className="px-2 py-1.5">
                        {row.median_interval_days !== null
                          ? `${row.median_interval_days.toFixed(1)} d`
                          : "—"}
                      </td>
                      <td className="px-2 py-1.5" data-testid="interval-days-to-full">
                        {row.days_to_full !== null ? (
                          <>
                            {`${row.days_to_full.toFixed(1)} d`}
                            {row.is_lower_bound ? (
                              <span
                                className="ml-1 rounded border border-amber-300 bg-amber-100 px-1 py-0.5 font-semibold text-amber-900"
                                data-testid="interval-at-least"
                                title={t(lang, "containers.interval.atLeastTitle")}
                              >
                                {t(lang, "containers.interval.atLeast")}
                              </span>
                            ) : null}
                          </>
                        ) : (
                          <span className="text-slate-500">
                            {row.reason !== null
                              ? `${t(lang, "containers.interval.noEstimate")}: ${row.reason}`
                              : t(lang, "containers.interval.noEstimate")}
                          </span>
                        )}
                      </td>
                      <td className="px-2 py-1.5">{row.predicted_full_date ?? "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          {/* Mandatory §1.5 caveat beside the rates — echoed by the API, verbatim. */}
          <div className="mt-2 rounded border border-amber-200 bg-amber-50 px-3 py-2" data-testid="interval-caveat">
            <p className="text-xs font-semibold text-amber-900">
              {t(lang, "overview.tanks.caveatTitle")}
            </p>
            <ul className="mt-1 list-disc pl-4 text-xs leading-relaxed text-amber-800">
              {payload.assumptions.map((line) => (
                <li key={line}>{line}</li>
              ))}
            </ul>
          </div>
        </div>
      ) : null}
    </Panel>
  );
}
