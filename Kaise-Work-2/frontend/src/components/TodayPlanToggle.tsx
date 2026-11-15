import { useEffect, useState } from "react";
import {
  ApiError,
  runScenarios,
  type ScenarioResponse,
  type ScenarioStrategy,
} from "../lib/api";
import { t, tf, type Lang, type TranslationKey } from "../lib/i18n";
import { EmptyState, ErrorState, LoadingState } from "./states";

/**
 * W1/W2 (M16 v4): "Today ↔ With our plan" toggle. §6 rules baked in:
 * - cost is NEVER shown without a service-level indicator beside it;
 * - the observed anchor (26.9 % in the real capture — value always from the
 *   API, never hardcoded) is the "today" service level, basis
 *   `observed_emptying_records` [observed]; strategy service blocks are
 *   simulated and labelled as such ("simulation based on historical rates,
 *   not a prediction of reality");
 * - tradeoffs are shown straight: a plan that costs MORE is said to cost
 *   more; a plan that costs less while serving worse is visibly flagged.
 * All numbers come from POST /api/scenarios (empty body → server defaults,
 * §5.2.4 — no client-side constants).
 */

type Side = "today" | "plan";

export interface TodayPlanToggleProps {
  lang: Lang;
  /** Bumped on dataset change — re-runs the scenarios request. */
  datasetVersion: number;
  /** Bumped by the config editor's Recalculate button. */
  recalculateKey?: number;
}

function strategyById(
  payload: ScenarioResponse | null,
  id: ScenarioStrategy["id"],
): ScenarioStrategy | null {
  const s = payload?.strategies.find((x) => x.id === id);
  return s !== undefined ? s : null;
}

function isFiniteNumber(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value);
}

/** Defensive §5.2.4 payload guard — malformed responses degrade, never crash. */
function validScenarios(payload: ScenarioResponse | null): ScenarioResponse | null {
  if (payload === null) return null;
  if (!Array.isArray(payload.strategies) || payload.strategies.length !== 2) return null;
  if (strategyById(payload, "fixed_frequency") === null) return null;
  if (strategyById(payload, "demand_driven") === null) return null;
  const anchor = payload.observed_anchor;
  if (anchor === null || anchor === undefined || anchor.basis !== "observed_emptying_records") {
    return null;
  }
  return payload;
}

/** Signed EUR/year delta text — derived from the response, never fabricated. */
function formatDelta(delta: number | null): string {
  if (delta === null || !Number.isFinite(delta)) return "— EUR/year";
  const abs = `${Math.abs(delta).toLocaleString("en-US", { maximumFractionDigits: 0 })} EUR/year`;
  return delta > 0 ? `+${abs}` : delta < 0 ? `−${abs}` : "0 EUR/year";
}

/** One strategy cost+service block (§6: cost never alone). */
function StrategyBlock({
  lang,
  strategy,
  testid,
}: {
  lang: Lang;
  strategy: ScenarioStrategy;
  testid: string;
}) {
  const service = strategy.service;
  const shareFull = isFiniteNumber(service.share_emptyings_full_or_overfull_pct)
    ? `${service.share_emptyings_full_or_overfull_pct.toFixed(1)} %`
    : "— %";
  const overflow = isFiniteNumber(service.overflow_share_pct)
    ? `${service.overflow_share_pct.toFixed(1)} %`
    : "— %";
  const maxFill = isFiniteNumber(service.max_fill_pct)
    ? `${service.max_fill_pct.toFixed(1)} %`
    : "— %";
  return (
    <div className="rounded border border-slate-200 bg-slate-50 px-3 py-2" data-testid={testid}>
      <p className="text-lg font-bold text-slate-900">
        {strategy.cost_eur_total.toLocaleString("en-US")} EUR{" "}
        <span className="text-sm font-medium text-slate-500">
          {t(lang, "overview.toggle.costWindow")}
        </span>
      </p>
      <p className="text-sm text-slate-700">
        {t(lang, "overview.toggle.costYear")}:{" "}
        {strategy.cost_eur_per_year.toLocaleString("en-US", { maximumFractionDigits: 0 })}{" "}
        EUR/year
      </p>
      <dl className="mt-1 space-y-0.5 text-xs text-slate-600">
        <div className="flex justify-between gap-2">
          <dt>{t(lang, "overview.toggle.serviceFull")}</dt>
          <dd className="font-semibold text-slate-800">{shareFull}</dd>
        </div>
        <div className="flex justify-between gap-2">
          <dt>{t(lang, "overview.toggle.overflow")}</dt>
          <dd className="font-semibold text-slate-800">{overflow}</dd>
        </div>
        <div className="flex justify-between gap-2">
          <dt>{t(lang, "overview.toggle.maxFill")}</dt>
          <dd className="font-semibold text-slate-800">{maxFill}</dd>
        </div>
        <div className="flex justify-between gap-2">
          <dt>{t(lang, "overview.toggle.truckDays")}</dt>
          <dd className="font-semibold text-slate-800">
            {strategy.truck_days.toLocaleString("en-US")}
          </dd>
        </div>
        <div className="flex justify-between gap-2">
          <dt>{t(lang, "overview.toggle.stops")}</dt>
          <dd className="font-semibold text-slate-800">
            {strategy.stops_total.toLocaleString("en-US")}
          </dd>
        </div>
      </dl>
      <p className="mt-1 text-xs text-slate-500">{t(lang, "overview.toggle.simBasis")}</p>
    </div>
  );
}

export function TodayPlanToggle({
  lang,
  datasetVersion,
  recalculateKey = 0,
}: TodayPlanToggleProps) {
  const [payload, setPayload] = useState<ScenarioResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notFound, setNotFound] = useState(false);
  const [side, setSide] = useState<Side>("today");

  // Empty body → every parameter uses the server default (§5.2.4) — the UI
  // hardcodes no thresholds, costs or frequencies.
  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    setNotFound(false);
    setPayload(null);
    runScenarios({})
      .then((data) => {
        if (cancelled) return;
        if (validScenarios(data) === null) {
          setError("Unexpected /api/scenarios response shape (missing strategies/anchor)");
          setPayload(null);
          return;
        }
        setPayload(data);
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        setPayload(null);
        if (err instanceof ApiError && err.status === 404) {
          setNotFound(true); // no dataset → empty state, not an error (§5.3)
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
  }, [datasetVersion, recalculateKey]);

  const today = strategyById(payload, "fixed_frequency");
  const plan = strategyById(payload, "demand_driven");
  const anchorPct =
    payload !== null && isFiniteNumber(payload.observed_anchor.share_full_or_overfull_pct)
      ? `${payload.observed_anchor.share_full_or_overfull_pct.toFixed(1)} %`
      : null;

  // Derived tradeoff (§6): cost delta AND service delta always together.
  const costDelta =
    today !== null && plan !== null ? plan.cost_eur_per_year - today.cost_eur_per_year : null;
  const serviceDelta =
    today !== null &&
    plan !== null &&
    isFiniteNumber(today.service.share_emptyings_full_or_overfull_pct) &&
    isFiniteNumber(plan.service.share_emptyings_full_or_overfull_pct)
      ? plan.service.share_emptyings_full_or_overfull_pct -
        today.service.share_emptyings_full_or_overfull_pct
      : null;
  let flagKey: TranslationKey | null = null;
  let flagClass = "";
  if (costDelta !== null && serviceDelta !== null) {
    // serviceDelta is on a BAD-service metric (share full-or-overfull):
    // > 0 = service WORSE, < 0 = better, 0 = unchanged (review #4 adjudication).
    if (costDelta === 0) {
      flagKey = "overview.toggle.flagSameCost";
      flagClass = "border-slate-300 bg-slate-100 text-slate-800";
    } else if (costDelta > 0 && serviceDelta > 0) {
      flagKey = "overview.toggle.flagCostMoreServiceWorse";
      flagClass = "border-red-300 bg-red-50 text-red-900";
    } else if (costDelta > 0 && serviceDelta === 0) {
      flagKey = "overview.toggle.flagCostMoreNoGain";
      flagClass = "border-amber-300 bg-amber-50 text-amber-900";
    } else if (costDelta > 0) {
      flagKey = "overview.toggle.flagCostMoreServiceBetter";
      flagClass = "border-amber-300 bg-amber-50 text-amber-900";
    } else if (serviceDelta > 0) {
      flagKey = "overview.toggle.flagCostLessServiceWorse";
      flagClass = "border-red-300 bg-red-50 text-red-900";
    } else if (serviceDelta === 0) {
      flagKey = "overview.toggle.flagCostLessNoServiceChange";
      flagClass = "border-emerald-300 bg-emerald-50 text-emerald-900";
    } else {
      flagKey = "overview.toggle.flagCostLessServiceBetter";
      flagClass = "border-emerald-300 bg-emerald-50 text-emerald-900";
    }
  }

  const toggleButton = (target: Side, labelKey: TranslationKey, testid: string) => (
    <button
      key={target}
      type="button"
      onClick={() => setSide(target)}
      aria-pressed={side === target}
      data-testid={testid}
      className={
        side === target
          ? "rounded bg-sky-700 px-3 py-1.5 text-sm font-semibold text-white"
          : "rounded border border-slate-300 bg-white px-3 py-1.5 text-sm font-medium text-slate-600 hover:bg-slate-100"
      }
    >
      {t(lang, labelKey)}
    </button>
  );

  return (
    <section className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm" data-testid="today-plan-toggle">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h3 className="text-base font-semibold text-slate-900">{t(lang, "overview.toggle.title")}</h3>
        <p className="text-xs text-slate-500">{t(lang, "overview.toggle.subtitle")}</p>
      </div>
      <div className="mt-2 flex gap-2" role="group" aria-label={t(lang, "overview.toggle.title")}>
        {toggleButton("today", "overview.toggle.today", "toggle-today")}
        {toggleButton("plan", "overview.toggle.plan", "toggle-plan")}
      </div>

      {loading ? (
        <div className="mt-3">
          <LoadingState label={t(lang, "overview.state.scenariosLoading")} />
        </div>
      ) : null}
      {error !== null && !loading ? (
        <div className="mt-3">
          <ErrorState label={t(lang, "overview.state.scenariosError")} hint={error} />
        </div>
      ) : null}
      {notFound && !loading && error === null ? (
        <div className="mt-3">
          <EmptyState label={t(lang, "overview.state.scenariosNoDataset")} />
        </div>
      ) : null}

      {!loading && error === null && !notFound && today !== null && plan !== null ? (
        <div className="mt-3 space-y-2">
          {/* Observed anchor — the reference service level beside every cost (§6). */}
          <p
            className="rounded border border-sky-200 bg-sky-50 px-3 py-2 text-xs font-semibold text-sky-900"
            data-testid="toggle-anchor"
          >
            {anchorPct !== null
              ? tf(lang, "overview.toggle.anchor", { pct: anchorPct })
              : t(lang, "overview.toggle.anchorUnavailable")}{" "}
            <span className="font-normal">{t(lang, "overview.toggle.anchorBasis")}</span>
          </p>

          {side === "today" ? (
            <StrategyBlock lang={lang} strategy={today} testid="toggle-strategy-today" />
          ) : (
            <div className="space-y-2" data-testid="toggle-strategy-plan">
              <StrategyBlock lang={lang} strategy={plan} testid="toggle-strategy-plan-block" />
              {flagKey !== null && costDelta !== null && serviceDelta !== null ? (
                <div className={`rounded border px-3 py-2 text-xs font-semibold ${flagClass}`} data-testid="toggle-tradeoff">
                  <p>
                    {tf(lang, flagKey, { delta: formatDelta(costDelta) })}
                  </p>
                  <p className="mt-0.5 font-normal">
                    {tf(lang, "overview.toggle.serviceDelta", {
                      delta: `${serviceDelta > 0 ? "+" : serviceDelta < 0 ? "−" : ""}${Math.abs(serviceDelta).toFixed(1)} pp`,
                    })}
                  </p>
                </div>
              ) : null}
            </div>
          )}
        </div>
      ) : null}
    </section>
  );
}
