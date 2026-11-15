import { useEffect, useState } from "react";
import {
  ApiError,
  fetchComparison,
  fetchDaysToFull,
  MATERIAL_TYPES,
  runCandidates,
  type ComparisonMethod,
  type ComparisonResponse,
  type ComparisonScenario,
  type DaysToFullResponse,
  type DatasetSummary,
  type FillStats,
  type FleetBudget,
  type SelectionResponse,
} from "../lib/api";
import { formatKg, formatLitres, formatMetres, formatMinutes, formatPct } from "../lib/format";
import { t, tf, type Lang, type TranslationKey } from "../lib/i18n";
import { DemoLoadButton } from "./DemoLoadButton";
import { GlassLegend } from "./GlassLegend";
import { PresentationMode } from "./PresentationMode";
import { TechDetails } from "./TechDetails";
import { TodayPlanToggle } from "./TodayPlanToggle";
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

/** Recommendation horizon for the overview (task-fixed 7 days) [demo assumption].
 *  Exported so the presentation mode reuses the same labelled constant. */
export const RECOMMENDATION_HORIZON_DAYS = 7;
const ISO_DATE = /^\d{4}-\d{2}-\d{2}$/;
const TOP_EXAMPLES = 5;

export interface OverviewProps {
  lang: Lang;
  summary: DatasetSummary | null;
  summaryLoading: boolean;
  summaryError: string | null;
  datasetVersion: number;
  /** Bumped by the config editor's Recalculate button — re-runs auto flows. */
  recalculateKey?: number;
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
 * Defensive §5.2.2 v4 payload guard: `scenarios` must be the fixed §4.7 v4
 * array of FOUR well-formed scenarios (naive_fixed_frequency FIRST, then
 * sweep_all / sweep_selected / ortools), `gains`/`optimised_determinism`
 * present.
 */
function validComparison(payload: ComparisonResponse | null): ComparisonResponse | null {
  if (payload === null) return null;
  if (!Array.isArray(payload.scenarios) || payload.scenarios.length !== 4) return null;
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

/** Defensive §5.2.3 v2 payload guard — malformed payloads degrade, never crash. */
function validDaysToFull(payload: DaysToFullResponse | null): DaysToFullResponse | null {
  if (payload === null) return null;
  const stats = payload.stats;
  if (typeof stats !== "object" || stats === null) return null;
  if (!isFiniteNumber(stats.series_total) || !isFiniteNumber(stats.series_with_estimate)) {
    return null;
  }
  if (!Array.isArray(payload.series) || !Array.isArray(payload.assumptions)) return null;
  return payload;
}

/**
 * §5.2.2/§4.7 v4 observed service anchor — the service level rendered beside
 * every cost (§6: cost is never shown alone). Null-safe: a missing/malformed
 * anchor renders the explicit "unavailable" note instead of a fabricated %.
 */
function validServiceAnchor(
  anchor: ComparisonResponse["observed_service_anchor"] | undefined,
): { pctText: string } | null {
  if (anchor === null || anchor === undefined || typeof anchor !== "object") return null;
  if (anchor.basis !== "observed_emptying_records") return null;
  const pct = anchor.share_full_or_overfull_pct;
  if (!isFiniteNumber(pct)) return null;
  return { pctText: `${pct.toFixed(1)} %` };
}

/** EUR amounts from the v3 cost fields — unit-explicit, "—" when missing. */
function formatEur(value: number | null | undefined): string {
  return isFiniteNumber(value) ? `${value.toLocaleString("en-US")} EUR` : "— EUR";
}

/**
 * Defensive §5.2.2 v3 fleet-budget guard — malformed payloads hide the card.
 */
function validFleetBudget(budget: FleetBudget | null | undefined): FleetBudget | null {
  if (budget === null || budget === undefined || typeof budget !== "object") return null;
  if (
    typeof budget.vehicle_type_id !== "string" ||
    budget.vehicle_type_id === "" ||
    !isFiniteNumber(budget.trucks) ||
    !isFiniteNumber(budget.cost_eur_per_day) ||
    !isFiniteNumber(budget.cost_eur_per_year)
  ) {
    return null;
  }
  return budget;
}

/**
 * Defensive §5.2.3 v2 stats_by_material guard (W3 tanks): all three materials
 * must carry finite series counts; median_days may be null (no estimate) —
 * the tank for that material degrades to "—" instead of being dropped.
 */
function validStatsByMaterial(
  payload: DaysToFullResponse | null,
): DaysToFullResponse["stats_by_material"] | null {
  const byMaterial = payload?.stats_by_material;
  if (byMaterial === null || byMaterial === undefined || typeof byMaterial !== "object") {
    return null;
  }
  for (const material of ["brown", "green", "white"] as const) {
    const stats = byMaterial[material];
    if (typeof stats !== "object" || stats === null) return null;
    if (!isFiniteNumber(stats.series_total) || !isFiniteNumber(stats.series_with_estimate)) {
      return null;
    }
  }
  return byMaterial;
}

/** Per-scenario cost row value (§5.2.2 v3), e.g. "1,500 EUR/day · 300,000 EUR/year". */
function formatCostRow(scenario: ComparisonScenario): string {
  if (!isFiniteNumber(scenario.cost_eur_per_day) || !isFiniteNumber(scenario.cost_eur_per_year)) {
    return "— EUR/day · — EUR/year";
  }
  return `${formatEur(scenario.cost_eur_per_day)}/day · ${formatEur(scenario.cost_eur_per_year)}/year`;
}

export function Overview({
  lang,
  summary,
  summaryLoading,
  summaryError,
  datasetVersion,
  recalculateKey = 0,
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

  // Days-to-full KPI (§5.2.3 v3 GET /api/days-to-full) — [predicted] estimates.
  const [daysToFull, setDaysToFull] = useState<DaysToFullResponse | null>(null);
  const [daysToFullLoading, setDaysToFullLoading] = useState(false);
  const [daysToFullError, setDaysToFullError] = useState<string | null>(null);

  // W5: presentation mode overlay (opened from the hero button).
  const [presentationOpen, setPresentationOpen] = useState(false);

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
  }, [asOf, datasetVersion, recalculateKey]);

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
  }, [hasDataset, datasetVersion, recalculateKey]);

  // Days-to-full (§5.2.3 v3) — like the comparison: 404 before a dataset is a
  // state fact (empty card note), never an error; estimates are [predicted].
  useEffect(() => {
    if (!hasDataset) {
      setDaysToFull(null);
      setDaysToFullError(null);
      return;
    }
    let cancelled = false;
    setDaysToFullLoading(true);
    setDaysToFullError(null);
    fetchDaysToFull()
      .then((payload) => {
        if (cancelled) return;
        if (validDaysToFull(payload) === null) {
          setDaysToFull(null);
          setDaysToFullError("Unexpected /api/days-to-full response shape");
          return;
        }
        setDaysToFull(payload);
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        setDaysToFull(null);
        if (!(err instanceof ApiError && err.status === 404)) {
          setDaysToFullError(err instanceof ApiError ? err.message : String(err));
        }
      })
      .finally(() => {
        if (!cancelled) setDaysToFullLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [hasDataset, datasetVersion, recalculateKey]);

  const fillStats = validFillStats(summary);
  const selected = selection?.selected ?? [];
  const skipped = selection?.skipped ?? [];
  const noForecastCount = skipped.filter((s) => s.reason_code === "no_forecast").length;
  // §5.2.2 v4: naive_fixed_frequency (status quo) first, then the three
  // §4.7 scenarios (sweep_all, sweep_selected, ortools).
  const comparisonValid = validComparison(comparison);
  const fixedFreq = scenarioByMethod(comparisonValid, "naive_fixed_frequency");
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
  // §5.2.3 v2 stats — all numbers come from the API, never hardcoded.
  const dtfStats = validDaysToFull(daysToFull)?.stats ?? null;
  // v3 fleet budget — validated once, reused by guard and card body.
  const fleetBudget = validFleetBudget(comparisonValid?.fleet_budget ?? null);
  // §6: service anchor rendered beside every cost row in the comparison card.
  const serviceAnchor = validServiceAnchor(comparisonValid?.observed_service_anchor);
  // W3 tanks: per-material filling times from the §5.2.3 v2 payload.
  const statsByMaterial = validStatsByMaterial(daysToFull);
  const maxMedianDays =
    statsByMaterial !== null
      ? Math.max(
          ...MATERIAL_TYPES.map((m) => {
            const v = statsByMaterial[m].median_days;
            return typeof v === "number" && Number.isFinite(v) ? v : 0;
          }),
        )
      : 0;

  return (
    <div className="space-y-4" data-testid="overview-root">
      {/* Hero: headline + 2-sentence problem statement + glass legend */}
      <section className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <h2 className="max-w-3xl text-xl font-bold text-slate-900">
            {t(lang, "overview.headline")}
          </h2>
          <div className="flex items-center gap-3">
            <GlassLegend lang={lang} />
            <button
              type="button"
              onClick={() => setPresentationOpen(true)}
              data-testid="presentation-open"
              className="rounded bg-slate-900 px-3 py-1.5 text-sm font-semibold text-white hover:bg-slate-700"
            >
              {t(lang, "overview.presentation.open")}
            </button>
          </div>
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

      {/* Three plain-language key numbers (plus the v3 days-to-full prediction) */}
      {!summaryLoading && summaryError === null && hasDataset ? (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4" data-testid="overview-keynumbers">
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
          <KeyNumberCard
            title={t(lang, "overview.keynum.daysToFull.title")}
            value={
              dtfStats !== null && dtfStats.median_days !== null ? `${dtfStats.median_days.toFixed(1)} d` : "— d"
            }
            testid="keynum-days-to-full"
          >
            {daysToFullLoading ? (
              t(lang, "overview.state.daysToFullLoading")
            ) : daysToFullError !== null ? (
              <span className="text-amber-700">{daysToFullError}</span>
            ) : dtfStats === null || dtfStats.series_with_estimate === 0 ? (
              t(lang, "overview.keynum.daysToFull.noData")
            ) : (
              <>
                {tf(lang, "overview.keynum.daysToFull.note", {
                  n: dtfStats.series_with_estimate.toLocaleString("en-US"),
                  total: dtfStats.series_total.toLocaleString("en-US"),
                })}
                {daysToFull !== null ? (
                  <>
                    <span className="mt-1 block">
                      {t(lang, "overview.keynum.daysToFull.method")}: {daysToFull.method} —{" "}
                      {t(lang, "overview.keynum.daysToFull.predicted")}
                    </span>
                    <span className="mt-1 block">{daysToFull.assumptions.join(" · ")}</span>
                  </>
                ) : null}
              </>
            )}
          </KeyNumberCard>
        </div>
      ) : null}

      {/* W3: filling time per material (§5.2.3 v2 stats_by_material) with the
          mandatory §1.5 caveat near the rates — [predicted], never observed. */}
      {!summaryLoading && summaryError === null && hasDataset && statsByMaterial !== null && daysToFull !== null ? (
        <section className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm" data-testid="filling-tanks">
          <h3 className="text-base font-semibold text-slate-900">{t(lang, "overview.tanks.title")}</h3>
          <p className="mt-1 text-xs leading-relaxed text-slate-500">
            {tf(lang, "overview.tanks.note", { pct: `${daysToFull.target_pct} %` })}
          </p>
          <div className="mt-3 space-y-2">
            {MATERIAL_TYPES.map((material) => {
              const stats = statsByMaterial[material];
              const median =
                typeof stats.median_days === "number" && Number.isFinite(stats.median_days)
                  ? `${stats.median_days.toFixed(1)} d`
                  : "— d";
              const widthPct =
                maxMedianDays > 0 &&
                typeof stats.median_days === "number" &&
                Number.isFinite(stats.median_days)
                  ? Math.max(4, (stats.median_days / maxMedianDays) * 100)
                  : 0;
              const swatch =
                material === "brown"
                  ? "bg-amber-800"
                  : material === "green"
                    ? "bg-emerald-600"
                    : "bg-slate-400";
              const lowerBoundRaw = stats.lower_bound_share_pct;
              const lbPct =
                typeof lowerBoundRaw === "number" && Number.isFinite(lowerBoundRaw)
                  ? lowerBoundRaw
                  : null;
              return (
                <div key={material} className="text-xs text-slate-700" data-testid={`tank-${material}`}>
                  <div className="flex items-baseline justify-between gap-2">
                    <span className="font-medium">{t(lang, `legend.${material}` as TranslationKey)}</span>
                    <span className="font-semibold text-slate-900">{median}</span>
                  </div>
                  <div className="mt-1 h-3 w-full overflow-hidden rounded bg-slate-100">
                    <div className={`h-full ${swatch}`} style={{ width: `${widthPct}%` }} />
                  </div>
                  {lbPct !== null && lbPct > 0 ? (
                    <p className="mt-0.5 text-amber-700">
                      {tf(lang, "overview.tanks.lowerBound", {
                        pct: `${lbPct.toFixed(1)} %`,
                      })}
                    </p>
                  ) : null}
                </div>
              );
            })}
          </div>
          {/* Mandatory §1.5 caveat + model assumptions — echoed by the API, rendered verbatim. */}
          <div className="mt-3 rounded border border-amber-200 bg-amber-50 px-3 py-2" data-testid="tanks-caveat">
            <p className="text-xs font-semibold text-amber-900">{t(lang, "overview.tanks.caveatTitle")}</p>
            <ul className="mt-1 list-disc pl-4 text-xs leading-relaxed text-amber-800">
              {daysToFull.assumptions.map((line) => (
                <li key={line}>{line}</li>
              ))}
            </ul>
          </div>
        </section>
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

      {/* Today ↔ with-our-plan toggle: cost + service always together (§6, W1/W2) */}
      {!summaryLoading && summaryError === null && hasDataset ? (
        <TodayPlanToggle lang={lang} datasetVersion={datasetVersion} recalculateKey={recalculateKey} />
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

        {fixedFreq !== null &&
        sweepAll !== null &&
        sweepSelected !== null &&
        optimised !== null &&
        !comparisonLoading ? (
          <div className="mt-3 space-y-2">
            {serviceAnchor !== null ? (
              <p
                className="rounded border border-sky-200 bg-sky-50 px-3 py-2 text-xs font-semibold text-sky-900"
                data-testid="comparison-service-anchor"
              >
                {t(lang, "col.service")}:{" "}
                {tf(lang, "overview.compare.serviceAnchor", { pct: serviceAnchor.pctText })}
              </p>
            ) : (
              <p
                className="rounded border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800"
                data-testid="comparison-service-anchor"
              >
                {t(lang, "overview.compare.serviceAnchorUnavailable")}
              </p>
            )}
            <ol className="space-y-2" data-testid="comparison-steps">
              <ComparisonStep
                index={1}
                title={t(lang, "overview.compare.step0.title")}
                rows={[
                  [t(lang, "col.distance"), formatMetres(fixedFreq.distance_m)],
                  [
                    t(lang, "col.stopsServed"),
                    `${fixedFreq.stops_served.toLocaleString("en-US")} / ${fixedFreq.stops_total.toLocaleString("en-US")}`,
                  ],
                  [t(lang, "col.duration"), formatMinutes(fixedFreq.duration_min)],
                  [t(lang, "col.trucks"), `${fixedFreq.recommended_trucks} ${t(lang, "unit.vehicles")}`],
                  [t(lang, "col.volume"), formatLitres(fixedFreq.collected_volume_litres)],
                  [t(lang, "col.weight"), formatKg(fixedFreq.collected_weight_kg)],
                  [t(lang, "col.cost"), formatCostRow(fixedFreq)],
                  [
                    t(lang, "col.distancePerKg"),
                    fixedFreq.distance_per_kg_m !== null
                      ? `${fixedFreq.distance_per_kg_m.toFixed(1)} m/kg`
                      : "— m/kg",
                  ],
                ]}
              />
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
                  [t(lang, "col.cost"), formatCostRow(sweepAll)],
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
                  [t(lang, "col.cost"), formatCostRow(sweepSelected)],
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
                  [t(lang, "col.cost"), formatCostRow(optimised)],
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
            {optimised.travel_time_mode === "fixed_per_leg" ? (
              <p className="text-xs leading-relaxed text-slate-500" data-testid="comparison-flatmode-note">
                {t(lang, "overview.compare.flatModeNote")}
              </p>
            ) : null}
            {savingsPct !== null ? (
              <p className="text-xs font-semibold text-emerald-700" data-testid="comparison-savings">
                {tf(lang, "overview.compare.savings", { pct: `${savingsPct.toFixed(1)} %` })}
              </p>
            ) : null}
            {fleetBudget !== null ? (
              <div
                className="rounded border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-700"
                data-testid="fleet-budget"
              >
                <p className="text-sm font-semibold text-slate-800">
                  {t(lang, "overview.fleetBudget.title")}
                </p>
                <dl className="mt-1 grid gap-x-4 gap-y-0.5 sm:grid-cols-2">
                  <div className="flex justify-between gap-2">
                    <dt className="text-slate-500">{t(lang, "col.trucks")}</dt>
                    <dd className="text-right text-slate-800">
                      {fleetBudget.trucks} {t(lang, "unit.vehicles")} ({fleetBudget.vehicle_type_id})
                    </dd>
                  </div>
                  <div className="flex justify-between gap-2">
                    <dt className="text-slate-500">{t(lang, "overview.fleetBudget.perDay")}</dt>
                    <dd className="text-right text-slate-800">{formatEur(fleetBudget.cost_eur_per_day)}</dd>
                  </div>
                  <div className="flex justify-between gap-2">
                    <dt className="text-slate-500">{t(lang, "overview.fleetBudget.perYear")}</dt>
                    <dd className="text-right text-slate-800">{formatEur(fleetBudget.cost_eur_per_year)}</dd>
                  </div>
                </dl>
                <p className="mt-1 text-slate-500">{t(lang, "overview.fleetBudget.note")}</p>
              </div>
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

      {/* W5 presentation overlay (6 slides, ←/→, Esc; §6 labels stay visible) */}
      {presentationOpen ? (
        <PresentationMode
          lang={lang}
          summary={summary}
          onClose={() => setPresentationOpen(false)}
        />
      ) : null}
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
    method === "naive_fixed_frequency"
      ? "overview.compare.step0.short"
      : method === "naive_sweep_all"
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
