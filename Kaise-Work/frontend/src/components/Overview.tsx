import { useEffect, useState } from "react";
import {
  ApiError,
  fetchComparison,
  runCandidates,
  type ComparisonMethod,
  type ComparisonResponse,
  type ComparisonScenario,
  type DatasetSummary,
  type FillStats,
  type SelectionResponse,
} from "../lib/api";
import { formatKg, formatLitres, formatMetres, formatMinutes, formatPct } from "../lib/format";
import { t, tf, type Lang, type TranslationKey } from "../lib/i18n";
import { DemoLoadButton } from "./DemoLoadButton";
import { GlassLegend } from "./GlassLegend";
import { TechDetails } from "./TechDetails";
import { EmptyState, ErrorState, LoadingState } from "./states";

/**
 * Overview page (first nav tab; M11 jury-usability pass). Audience: jury and
 * city administrators. Plain-language key numbers from the API, a "today's
 * recommendation" work list with reasons, a 4-step how-it-works strip and a
 * fixed-vs-optimised before/after card. Labelling discipline (AGENTS rule 3,
 * §5.2.2): historical shares are shares of *readings* — never "emptyings"
 * (the data has no collection events); distances are straight-line estimates;
 * savings are labelled derived; solver statuses and raw metrics stay inside
 * the TechDetails collapsible.
 */

/** Recommendation horizon for the overview (task-fixed 7 days) [demo assumption]. */
const RECOMMENDATION_HORIZON_DAYS = 7;
const ISO_DATE = /^\d{4}-\d{2}-\d{2}$/;
const TOP_EXAMPLES = 5;

export interface OverviewProps {
  lang: Lang;
  summary: DatasetSummary | null;
  summaryLoading: boolean;
  summaryError: string | null;
  datasetVersion: number;
  /** Same handler as a CSV upload — a demo load activates the dataset (§5.1). */
  onDemoLoaded: (summary: DatasetSummary) => void;
}

function isFiniteNumber(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value);
}

/** Defensive fill_stats guard (App.test mock returns {status:"ok"} everywhere). */
function validFillStats(summary: DatasetSummary | null): FillStats | null {
  const fs = summary?.fill_stats;
  if (fs === null || fs === undefined) return null;
  if (!isFiniteNumber(fs.share_readings_full_or_above_pct) || !isFiniteNumber(fs.threshold_pct)) {
    return null;
  }
  return fs;
}

/** Defensive §5.2.2 scenario guard — malformed payloads degrade, never crash. */
function isScenario(value: unknown): boolean {
  if (typeof value !== "object" || value === null) return false;
  const s = value as Record<string, unknown>;
  return (
    typeof s.method === "string" &&
    typeof s.status === "string" &&
    isFiniteNumber(s.distance_m) &&
    isFiniteNumber(s.duration_min) &&
    isFiniteNumber(s.stops_served) &&
    isFiniteNumber(s.stops_total) &&
    isFiniteNumber(s.vehicles_used) &&
    isFiniteNumber(s.collected_volume_litres) &&
    isFiniteNumber(s.collected_weight_kg) &&
    isFiniteNumber(s.unserved_count) &&
    isFiniteNumber(s.recommended_trucks)
  );
}

/** Signed metres text for a nullable gain — null renders as "— m", never 0. */
function formatGain(gain: number | null | undefined): string {
  if (gain === null || gain === undefined || !Number.isFinite(gain)) return "— m";
  const abs = `${Math.abs(gain).toLocaleString("en-US")} m`;
  return gain < 0 ? `−${abs}` : `+${abs}`;
}

/**
 * Defensive §5.2.2 v2 payload guard: `scenarios` must be the fixed §4.7 array
 * of three well-formed scenarios, `gains`/`optimised_determinism` present.
 */
function validComparison(payload: ComparisonResponse | null): ComparisonResponse | null {
  if (payload === null) return null;
  if (!Array.isArray(payload.scenarios) || payload.scenarios.length !== 3) return null;
  if (!payload.scenarios.every((s) => isScenario(s))) return null;
  const det = payload.optimised_determinism;
  if (
    det === null ||
    det === undefined ||
    !isFiniteNumber(det.runs) ||
    (det.mode !== "identical" && det.mode !== "median_of_runs")
  ) {
    return null;
  }
  return payload;
}

function scenarioByMethod(
  comparison: ComparisonResponse | null,
  method: ComparisonMethod,
): ComparisonScenario | null {
  const s = comparison?.scenarios.find((x) => x.method === method);
  return s !== undefined ? s : null;
}

export function Overview({
  lang,
  summary,
  summaryLoading,
  summaryError,
  datasetVersion,
  onDemoLoaded,
}: OverviewProps) {
  // Auto-run candidates (§5.1 POST /api/candidates) for "today's recommendation".
  const [selection, setSelection] = useState<SelectionResponse | null>(null);
  const [recLoading, setRecLoading] = useState(false);
  const [recError, setRecError] = useState<string | null>(null);

  // Fixed-vs-optimised comparison (§5.2.2 GET /api/comparison).
  const [comparison, setComparison] = useState<ComparisonResponse | null>(null);
  const [comparisonLoading, setComparisonLoading] = useState(false);
  const [comparisonError, setComparisonError] = useState<string | null>(null);
  const [comparisonNotFound, setComparisonNotFound] = useState(false);

  const asOf =
    typeof summary?.date_max === "string" && ISO_DATE.test(summary.date_max)
      ? summary.date_max
      : null;
  const hasDataset = summary !== null;

  // Auto-run candidates once the dataset exposes its last reading date.
  // Keyed on [date_max, datasetVersion] — a new upload (version bump) reruns.
  useEffect(() => {
    if (asOf === null) {
      setSelection(null);
      setRecError(null);
      return;
    }
    let cancelled = false;
    setRecLoading(true);
    setRecError(null);
    runCandidates({
      as_of_date: asOf,
      horizon_days: RECOMMENDATION_HORIZON_DAYS,
      method: "persistence",
    })
      .then((payload) => {
        if (cancelled) return;
        // Defensive shape guard: malformed responses set an error, never crash.
        if (!Array.isArray(payload.selected) || !Array.isArray(payload.skipped)) {
          setSelection(null);
          setRecError("Unexpected /api/candidates response shape (missing selected/skipped)");
          return;
        }
        setSelection(payload);
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setSelection(null);
          setRecError(err instanceof ApiError ? err.message : String(err));
        }
      })
      .finally(() => {
        if (!cancelled) setRecLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [asOf, datasetVersion]);

  // Comparison only exists once a dataset is loaded (404 before, §5.3 → empty state).
  useEffect(() => {
    if (!hasDataset) {
      setComparison(null);
      setComparisonNotFound(false);
      setComparisonError(null);
      return;
    }
    let cancelled = false;
    setComparisonLoading(true);
    setComparisonNotFound(false);
    setComparisonError(null);
    fetchComparison()
      .then((payload) => {
        if (cancelled) return;
        // Defensive shape guard: malformed v2 payload → error state, never crash.
        if (validComparison(payload) === null) {
          setComparison(null);
          setComparisonError("Unexpected /api/comparison response shape (missing scenarios/gains/determinism)");
          return;
        }
        setComparison(payload);
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        setComparison(null);
        if (err instanceof ApiError && err.status === 404) {
          setComparisonNotFound(true); // no dataset → empty state, not an error
        } else {
          setComparisonError(err instanceof ApiError ? err.message : String(err));
        }
      })
      .finally(() => {
        if (!cancelled) setComparisonLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [hasDataset, datasetVersion]);

  const fillStats = validFillStats(summary);
  const selected = selection?.selected ?? [];
  const skipped = selection?.skipped ?? [];
  const noForecastCount = skipped.filter((s) => s.reason_code === "no_forecast").length;
  // §5.2.2 v2: fixed-order scenarios (naive_sweep_all, naive_sweep_selected, ortools).
  const comparisonValid = validComparison(comparison);
  const sweepAll = scenarioByMethod(comparisonValid, "naive_sweep_all");
  const sweepSelected = scenarioByMethod(comparisonValid, "naive_sweep_selected");
  const optimised = scenarioByMethod(comparisonValid, "ortools");
  const gains = comparisonValid?.gains ?? null;
  const determinism = comparisonValid?.optimised_determinism ?? null;
  // Derived saving share = total gain ÷ status-quo distance. Purely derived
  // (gains come from the API); labelled as derived, never a measured fact.
  const savingsPct =
    gains !== null &&
    gains.total_gain_m !== null &&
    sweepAll !== null &&
    Number.isFinite(sweepAll.distance_m) &&
    sweepAll.distance_m > 0
      ? (gains.total_gain_m / sweepAll.distance_m) * 100
      : null;

  return (
    <div className="space-y-4" data-testid="overview-root">
      {/* Hero: headline + 2-sentence problem statement + glass legend */}
      <section className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <h2 className="max-w-3xl text-xl font-bold text-slate-900">
            {t(lang, "overview.headline")}
          </h2>
          <GlassLegend lang={lang} />
        </div>
        <p className="mt-2 max-w-3xl text-sm leading-relaxed text-slate-600">
          {t(lang, "overview.problem")}
        </p>
      </section>

      {/* Dataset-level states replace the key numbers while absent/failed */}
      {summaryLoading ? <LoadingState label={t(lang, "overview.state.loading")} /> : null}
      {summaryError !== null && !summaryLoading ? (
        <ErrorState label={t(lang, "overview.state.summaryError")} hint={summaryError} />
      ) : null}
      {!summaryLoading && summaryError === null && !hasDataset ? (
        <div className="space-y-3">
          <EmptyState label={t(lang, "overview.state.noDataset")} />
          <DemoLoadButton lang={lang} onLoaded={onDemoLoaded} />
        </div>
      ) : null}

      {/* Three plain-language key numbers */}
      {!summaryLoading && summaryError === null && hasDataset ? (
        <div className="grid gap-4 md:grid-cols-3" data-testid="overview-keynumbers">
          <KeyNumberCard
            title={t(lang, "overview.keynum.readings.title")}
            value={fillStats !== null ? formatPct(fillStats.share_readings_full_or_above_pct, 1) : "— %"}
            testid="keynum-readings"
          >
            {fillStats !== null ? (
              tf(lang, "overview.keynum.readings.note", { thr: fillStats.threshold_pct })
            ) : (
              t(lang, "overview.state.noFillStats")
            )}
          </KeyNumberCard>
          <KeyNumberCard
            title={t(lang, "overview.keynum.containers.title")}
            value={`${selected.length.toLocaleString("en-US")} ${t(lang, "unit.containers")}`}
            testid="keynum-containers"
          >
            {asOf !== null
              ? tf(lang, "overview.keynum.containers.note", { date: asOf })
              : t(lang, "overview.state.noAsOf")}
          </KeyNumberCard>
          <KeyNumberCard
            title={t(lang, "overview.keynum.distance.title")}
            value={
              sweepAll !== null && optimised !== null
                ? `${formatMetres(sweepAll.distance_m)} → ${formatMetres(optimised.distance_m)}`
                : "— m"
            }
            testid="keynum-distance"
          >
            {sweepAll !== null && optimised !== null ? (
              <>
                {t(lang, "overview.keynum.distance.fixed")}: {formatMetres(sweepAll.distance_m)} ·{" "}
                {t(lang, "overview.keynum.distance.optimised")}: {formatMetres(optimised.distance_m)}{" "}
                · {t(lang, "unit.vehicles")}: {sweepAll.recommended_trucks} →{" "}
                {optimised.recommended_trucks}
                {savingsPct !== null ? (
                  <span className="mt-1 block">
                    {tf(lang, "overview.keynum.distance.savings", {
                      pct: `${savingsPct.toFixed(1)} %`,
                    })}
                  </span>
                ) : null}
              </>
            ) : (
              t(lang, "overview.state.comparisonNoDataset")
            )}
          </KeyNumberCard>
        </div>
      ) : null}

      {/* Today's recommendation: N empty / M wait + top examples with reasons */}
      {!summaryLoading && summaryError === null && hasDataset ? (
        <section className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm" data-testid="recommendation">
          <div className="flex flex-wrap items-baseline justify-between gap-2">
            <h3 className="text-base font-semibold text-slate-900">
              {t(lang, "overview.recommendation.title")}
            </h3>
            {asOf !== null ? (
              <p className="text-xs text-slate-500">
                {tf(lang, "overview.recommendation.asof", { date: asOf })} ·{" "}
                {tf(lang, "overview.recommendation.horizon", { days: RECOMMENDATION_HORIZON_DAYS })}
              </p>
            ) : null}
          </div>

          {recLoading ? <div className="mt-3"><LoadingState label={t(lang, "overview.state.recommendationLoading")} /></div> : null}
          {recError !== null && !recLoading ? (
            <div className="mt-3"><ErrorState label={t(lang, "overview.state.recommendationError")} hint={recError} /></div>
          ) : null}
          {asOf === null && !recLoading && recError === null ? (
            <div className="mt-3"><EmptyState label={t(lang, "overview.state.noAsOf")} /></div>
          ) : null}

          {asOf !== null && !recLoading && recError === null && selection !== null ? (
            <div className="mt-3 space-y-3">
              <div className="flex flex-wrap gap-4 text-sm">
                <p className="font-semibold text-red-800">
                  {tf(lang, "overview.recommendation.toEmpty", { n: selected.length })}
                </p>
                <p className="font-semibold text-slate-600">
                  {tf(lang, "overview.recommendation.canWait", { n: skipped.length })}
                </p>
                {noForecastCount > 0 ? (
                  <p className="text-amber-700">
                    {tf(lang, "overview.recommendation.noForecast", { n: noForecastCount })}
                  </p>
                ) : null}
              </div>
              <ExampleList
                label={t(lang, "overview.recommendation.examples")}
                rows={[
                  ...selected.slice(0, TOP_EXAMPLES).map((c) => ({
                    key: `${c.location_id}·${c.material_type}`,
                    locationId: c.location_id,
                    material: c.material_type,
                    fill: formatPct(c.predicted_fill_pct, 0),
                    reason: t(lang, `overview.reason.${c.reason_code}` as TranslationKey),
                  })),
                ]}
                emptyLabel={t(lang, "overview.state.recommendationError")}
              />
              <p className="text-xs leading-relaxed text-slate-500">
                {t(lang, "overview.recommendation.caption")}
              </p>
            </div>
          ) : null}
        </section>
      ) : null}

      {/* How it works — static, shown even before data is loaded */}
      <section className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm" data-testid="how-strip">
        <h3 className="text-base font-semibold text-slate-900">{t(lang, "overview.how.title")}</h3>
        <ol className="mt-3 grid gap-2 text-sm text-slate-700 md:grid-cols-4">
          {(["step1", "step2", "step3", "step4"] as const).map((step, i) => (
            <li key={step} className="rounded border border-slate-200 bg-slate-50 px-3 py-2">
              <span className="mr-1 font-bold text-sky-700">{i + 1}.</span>
              {t(lang, `overview.how.${step}` as TranslationKey)}
            </li>
          ))}
        </ol>
      </section>

      {/* Before/after: fixed schedule vs optimised */}
      <section className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm" data-testid="comparison-card">
        <h3 className="text-base font-semibold text-slate-900">
          {t(lang, "overview.beforeafter.title")}
        </h3>
        <p className="mt-1 text-xs leading-relaxed text-slate-500">
          {t(lang, "overview.beforeafter.caption")}
        </p>

        {comparisonLoading ? (
          <div className="mt-3"><LoadingState label={t(lang, "overview.state.comparisonLoading")} /></div>
        ) : null}
        {comparisonError !== null && !comparisonLoading ? (
          <div className="mt-3"><ErrorState label={t(lang, "overview.state.comparisonError")} hint={comparisonError} /></div>
        ) : null}
        {!comparisonLoading && comparisonError === null && (comparisonNotFound || !hasDataset) ? (
          <div className="mt-3"><EmptyState label={t(lang, "overview.state.comparisonNoDataset")} /></div>
        ) : null}

        {sweepAll !== null && sweepSelected !== null && optimised !== null && !comparisonLoading ? (
          <div className="mt-3 space-y-2">
            <ol className="space-y-2" data-testid="comparison-steps">
              <ComparisonStep
                index={1}
                title={t(lang, "overview.compare.step1.title")}
                rows={[
                  [t(lang, "col.distance"), formatMetres(sweepAll.distance_m)],
                  [
                    t(lang, "col.stopsServed"),
                    `${sweepAll.stops_served.toLocaleString("en-US")} / ${sweepAll.stops_total.toLocaleString("en-US")}`,
                  ],
                  [t(lang, "col.duration"), formatMinutes(sweepAll.duration_min)],
                  [t(lang, "col.trucks"), `${sweepAll.recommended_trucks} ${t(lang, "unit.vehicles")}`],
                  [t(lang, "col.volume"), formatLitres(sweepAll.collected_volume_litres)],
                  [t(lang, "col.weight"), formatKg(sweepAll.collected_weight_kg)],
                  [
                    t(lang, "col.distancePerKg"),
                    sweepAll.distance_per_kg_m !== null
                      ? `${sweepAll.distance_per_kg_m.toFixed(1)} m/kg`
                      : "— m/kg",
                  ],
                ]}
              />
              <ComparisonStep
                index={2}
                title={t(lang, "overview.compare.step2.title")}
                rows={[
                  [t(lang, "col.distance"), formatMetres(sweepSelected.distance_m)],
                  [
                    t(lang, "col.stopsServed"),
                    `${sweepSelected.stops_served.toLocaleString("en-US")} / ${sweepSelected.stops_total.toLocaleString("en-US")}`,
                  ],
                  [t(lang, "col.duration"), formatMinutes(sweepSelected.duration_min)],
                  [t(lang, "col.trucks"), `${sweepSelected.recommended_trucks} ${t(lang, "unit.vehicles")}`],
                  [t(lang, "col.volume"), formatLitres(sweepSelected.collected_volume_litres)],
                  [t(lang, "col.weight"), formatKg(sweepSelected.collected_weight_kg)],
                  [
                    t(lang, "col.distancePerKg"),
                    sweepSelected.distance_per_kg_m !== null
                      ? `${sweepSelected.distance_per_kg_m.toFixed(1)} m/kg`
                      : "— m/kg",
                  ],
                ]}
              >
                {gains !== null && gains.selection_gain_m !== null ? (
                  <p
                    className={`text-xs font-semibold ${
                      gains.selection_gain_m < 0 ? "text-amber-700" : "text-emerald-700"
                    }`}
                    data-testid="comparison-selection-gain"
                  >
                    {tf(lang, "overview.compare.selectionGain", {
                      gain: formatGain(gains.selection_gain_m),
                    })}
                    {gains.selection_gain_m < 0 ? (
                      <> {t(lang, "overview.compare.selectionGainNegative")}</>
                    ) : null}
                  </p>
                ) : (
                  <p className="text-xs text-slate-500" data-testid="comparison-selection-gain">
                    {t(lang, "overview.compare.gainUnavailable")}
                  </p>
                )}
              </ComparisonStep>
              <ComparisonStep
                index={3}
                title={
                  determinism !== null
                    ? `${t(lang, "overview.compare.step3.title")} (${tf(lang, "overview.compare.step3.medianSuffix", { runs: determinism.runs })})`
                    : t(lang, "overview.compare.step3.title")
                }
                rows={[
                  [t(lang, "col.distance"), formatMetres(optimised.distance_m)],
                  [
                    t(lang, "col.stopsServed"),
                    `${optimised.stops_served.toLocaleString("en-US")} / ${optimised.stops_total.toLocaleString("en-US")}`,
                  ],
                  [t(lang, "col.duration"), formatMinutes(optimised.duration_min)],
                  [t(lang, "col.trucks"), `${optimised.recommended_trucks} ${t(lang, "unit.vehicles")}`],
                  [t(lang, "col.volume"), formatLitres(optimised.collected_volume_litres)],
                  [t(lang, "col.weight"), formatKg(optimised.collected_weight_kg)],
                  [
                    t(lang, "col.distancePerKg"),
                    optimised.distance_per_kg_m !== null
                      ? `${optimised.distance_per_kg_m.toFixed(1)} m/kg`
                      : "— m/kg",
                  ],
                ]}
              >
                {gains !== null && gains.routing_gain_m !== null ? (
                  <p className="text-xs font-semibold text-emerald-700" data-testid="comparison-routing-gain">
                    {tf(lang, "overview.compare.routingGain", { gain: formatGain(gains.routing_gain_m) })}
                  </p>
                ) : (
                  <p className="text-xs text-slate-500" data-testid="comparison-routing-gain">
                    {t(lang, "overview.compare.gainUnavailable")}
                  </p>
                )}
                {gains !== null && gains.total_gain_m !== null ? (
                  <p className="text-xs font-semibold text-emerald-700" data-testid="comparison-total-gain">
                    {tf(lang, "overview.compare.totalGain", { gain: formatGain(gains.total_gain_m) })}
                  </p>
                ) : null}
              </ComparisonStep>
            </ol>
            <p className="text-xs leading-relaxed text-slate-500" data-testid="comparison-perkg-note">
              {t(lang, "overview.compare.perKgNote")}
            </p>
            {savingsPct !== null ? (
              <p className="text-xs font-semibold text-emerald-700" data-testid="comparison-savings">
                {tf(lang, "overview.compare.savings", { pct: `${savingsPct.toFixed(1)} %` })}
              </p>
            ) : null}
            <TechDetails label={t(lang, "techdetails.label")} testid="comparison-tech-details">
              <p data-testid="comparison-statuses">
                {comparisonValid !== null
                  ? comparisonValid.scenarios
                      .map((s) => `${scenarioShortLabel(lang, s.method)}: ${s.status}`)
                      .join(" · ")
                  : null}
              </p>
              {determinism !== null ? (
                <p data-testid="comparison-determinism">
                  {determinism.mode === "identical"
                    ? tf(lang, "overview.compare.determinism.identical", {
                        runs: determinism.runs,
                        median: formatMetres(determinism.distance_m_median),
                      })
                    : tf(lang, "overview.compare.determinism.medianOfRuns", {
                        runs: determinism.runs,
                        median: formatMetres(determinism.distance_m_median),
                        min: formatMetres(determinism.distance_m_min),
                        max: formatMetres(determinism.distance_m_max),
                      })}
                </p>
              ) : null}
              <p>{comparisonValid?.distance_provenance === "haversine_straight_line_derived"
                ? "Distances: straight-line (haversine × detour factor) — NOT road distance"
                : `Distance provenance: ${comparisonValid?.distance_provenance ?? "—"}`}</p>
              <p className="text-slate-500">
                {t(lang, "overview.tech.assumptions")}:
              </p>
              <ul className="list-disc pl-4">
                {(comparisonValid?.assumptions ?? []).map((line) => (
                  <li key={line}>{line}</li>
                ))}
              </ul>
            </TechDetails>
          </div>
        ) : null}
      </section>

      {/* Calm note on demo assumptions + straight-line distances */}
      <p className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-xs leading-relaxed text-amber-800" data-testid="overview-calmnote">
        {t(lang, "overview.calmnote")}
      </p>
    </div>
  );
}

function KeyNumberCard({
  title,
  value,
  children,
  testid,
}: {
  title: string;
  value: string;
  children: React.ReactNode;
  testid: string;
}) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm" data-testid={testid}>
      <p className="text-xs font-medium uppercase tracking-wide text-slate-500">{title}</p>
      <p className="mt-1 text-2xl font-bold text-slate-900">{value}</p>
      <p className="mt-1 text-xs leading-relaxed text-slate-500">{children}</p>
    </div>
  );
}

function ExampleList({
  label,
  rows,
  emptyLabel,
}: {
  label: string;
  rows: Array<{ key: string; locationId: string; material: string; fill: string; reason: string }>;
  emptyLabel: string;
}) {
  return (
    <div>
      <p className="mb-1 text-sm font-semibold text-slate-700">{label}</p>
      {rows.length === 0 ? (
        <p className="text-xs text-slate-400">{emptyLabel}</p>
      ) : (
        <ul className="space-y-1" data-testid="recommendation-examples">
          {rows.map((row) => (
            <li
              key={row.key}
              className="rounded border border-slate-100 bg-slate-50 px-2 py-1 text-xs text-slate-700"
            >
              <span className="font-mono" title={row.locationId}>{row.locationId.slice(0, 13)}…</span>{" "}
              · {row.material} · {row.fill} — {row.reason}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

/** Short scenario label for the technical-details statuses line. */
function scenarioShortLabel(lang: Lang, method: ComparisonMethod): string {
  const key: TranslationKey =
    method === "naive_sweep_all"
      ? "overview.compare.step1.short"
      : method === "naive_sweep_selected"
        ? "overview.compare.step2.short"
        : "overview.compare.step3.short";
  return t(lang, key);
}

/** One numbered scenario step in the comparison story. */
function ComparisonStep({
  index,
  title,
  rows,
  children,
}: {
  index: number;
  title: string;
  rows: Array<[string, string]>;
  children?: React.ReactNode;
}) {
  return (
    <li className="rounded border border-slate-200 bg-slate-50 px-3 py-2" data-testid={`comparison-step-${index}`}>
      <p className="text-sm font-semibold text-slate-800">
        <span className="mr-1 font-bold text-sky-700">{index}.</span>
        {title}
      </p>
      <dl className="mt-1 grid gap-x-4 gap-y-0.5 text-xs text-slate-700 sm:grid-cols-2">
        {rows.map(([label, value]) => (
          <div key={label} className="flex justify-between gap-2">
            <dt className="text-slate-500">{label}</dt>
            <dd className="text-right text-slate-800">{value}</dd>
          </div>
        ))}
      </dl>
      {children}
    </li>
  );
}
