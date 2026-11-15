import { useEffect, useMemo, useState } from "react";
import {
  ApiError,
  runScenarios,
  runSimulation,
  type ScenarioResponse,
  type ScenarioStrategy,
  type SimulationResponse,
} from "../lib/api";
import { t, tf, type Lang, type TranslationKey } from "../lib/i18n";
import { Panel } from "./Panel";
import { TechDetails } from "./TechDetails";
import { EmptyState, ErrorState, LoadingState } from "./states";

/**
 * W4 (M16 v4): planning-lever what-if panel — POST /api/scenarios +
 * POST /api/simulation. §6: cost AND service level are always reported and
 * rendered together; the observed anchor ([observed]) is the reference
 * service level. Sliders are initialised from the API config defaults — the
 * panel hardcodes no thresholds, costs, capacities or frequencies; sliders
 * stay disabled until GET /api/config has loaded. The timeline is a plain
 * CSS-bar chart (no chart dependency) and ALWAYS carries the mega-day
 * model-consequence note (§5.2.5 replay initialisation: series without
 * pre-window history start at fill 0 on the same day → synchronised
 * collection days; a replay artefact, not observed behaviour).
 */

/** Slider bounds are UI ergonomics only — values come from config/responses. */
const SLIDER_BOUNDS = {
  frequency_days: { min: 1, max: 56, step: 1 },
  containers_per_series: { min: 1, max: 5, step: 1 },
  cost_per_truck_day_eur: { min: 100, max: 1000, step: 50 },
  max_shift_minutes: { min: 240, max: 600, step: 30 },
  vehicle_volume_capacity_litres: { min: 6000, max: 24000, step: 1000 },
} as const;

type SliderField = keyof typeof SLIDER_BOUNDS;

export interface ScenariosPanelProps {
  lang: Lang;
  config: import("../lib/api").ConfigDefaults | null;
  configLoading: boolean;
  datasetVersion: number;
  recalculateKey?: number;
}

function isFiniteNumber(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value);
}

/** Defensive §5.2.4 payload guard — malformed responses degrade, never crash. */
function validScenarios(payload: ScenarioResponse | null): ScenarioResponse | null {
  if (payload === null) return null;
  if (!Array.isArray(payload.strategies) || payload.strategies.length !== 2) return null;
  const ids = payload.strategies.map((s) => s.id).sort();
  if (ids[0] !== "demand_driven" || ids[1] !== "fixed_frequency") return null;
  const anchor = payload.observed_anchor;
  if (anchor === null || anchor === undefined || anchor.basis !== "observed_emptying_records") {
    return null;
  }
  return payload;
}

/** Defensive §5.2.5 payload guard. */
function validSimulation(payload: SimulationResponse | null): SimulationResponse | null {
  if (payload === null) return null;
  if (!Array.isArray(payload.strategies) || payload.strategies.length !== 2) return null;
  if (!payload.strategies.every((s) => Array.isArray(s.days))) return null;
  const basis = payload.data_basis;
  if (
    basis === null ||
    basis === undefined ||
    basis.records !== "observed" ||
    basis.rates !== "derived" ||
    basis.plan !== "simulated"
  ) {
    return null;
  }
  return payload;
}

function strategyById(
  payload: ScenarioResponse | null,
  id: ScenarioStrategy["id"],
): ScenarioStrategy | null {
  const s = payload?.strategies.find((x) => x.id === id);
  return s !== undefined ? s : null;
}

/** One strategy cost+service block (§6: cost never alone). */
function StrategyCard({
  lang,
  strategy,
  testid,
}: {
  lang: Lang;
  strategy: ScenarioStrategy;
  testid: string;
}) {
  const service = strategy.service;
  const num = (v: number | null, digits = 1): string =>
    isFiniteNumber(v) ? `${v.toFixed(digits)} %` : "— %";
  return (
    <div className="rounded border border-slate-200 bg-slate-50 px-3 py-2" data-testid={testid}>
      <p className="text-base font-bold text-slate-900">
        {strategy.cost_eur_total.toLocaleString("en-US")} EUR{" "}
        <span className="text-xs font-medium text-slate-500">
          {t(lang, "overview.toggle.costWindow")}
        </span>
      </p>
      <p className="text-xs text-slate-700">
        {t(lang, "overview.toggle.costYear")}:{" "}
        {strategy.cost_eur_per_year.toLocaleString("en-US", { maximumFractionDigits: 0 })}{" "}
        EUR/year
      </p>
      <dl className="mt-1 space-y-0.5 text-xs text-slate-600">
        <div className="flex justify-between gap-2">
          <dt>{t(lang, "overview.toggle.serviceFull")}</dt>
          <dd className="font-semibold text-slate-800">
            {num(service.share_emptyings_full_or_overfull_pct)}
          </dd>
        </div>
        <div className="flex justify-between gap-2">
          <dt>{t(lang, "overview.toggle.overflow")}</dt>
          <dd className="font-semibold text-slate-800">{num(service.overflow_share_pct)}</dd>
        </div>
        <div className="flex justify-between gap-2">
          <dt>{t(lang, "overview.toggle.maxFill")}</dt>
          <dd className="font-semibold text-slate-800">{num(service.max_fill_pct)}</dd>
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

export function ScenariosPanel({
  lang,
  config,
  configLoading,
  datasetVersion,
  recalculateKey = 0,
}: ScenariosPanelProps) {
  // Slider state: undefined = "use server default"; initialised from config.
  const [sliders, setSliders] = useState<Partial<Record<SliderField, number>>>({});
  const [scenarioData, setScenarioData] = useState<ScenarioResponse | null>(null);
  const [simulationData, setSimulationData] = useState<SimulationResponse | null>(null);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notFound, setNotFound] = useState(false);

  const configReady = !configLoading && config !== null && config.routing !== undefined;

  // A new dataset (or a config Recalculate) invalidates previous results —
  // stale numbers must never linger across datasets.
  useEffect(() => {
    setScenarioData(null);
    setSimulationData(null);
    setError(null);
    setNotFound(false);
  }, [datasetVersion, recalculateKey]);

  // When config arrives (or changes), seed the sliders with the API defaults.
  useEffect(() => {
    if (!configReady || config === null) return;
    const r = config.routing;
    setSliders({
      frequency_days: r.frequency_days,
      containers_per_series: r.containers_per_series,
      cost_per_truck_day_eur: r.cost_per_truck_day_eur,
      max_shift_minutes: r.max_shift_minutes,
      vehicle_volume_capacity_litres: r.vehicle_volume_capacity_litres,
    });
  }, [configReady, config]);

  const run = () => {
    setRunning(true);
    setError(null);
    setNotFound(false);
    setScenarioData(null);
    setSimulationData(null);
    const routingConfig = {
      containers_per_series: sliders.containers_per_series,
      cost_per_truck_day_eur: sliders.cost_per_truck_day_eur,
      max_shift_minutes: sliders.max_shift_minutes,
      vehicle_volume_capacity_litres: sliders.vehicle_volume_capacity_litres,
    };
    const body = {
      frequency_days: sliders.frequency_days,
      routing_config: routingConfig,
    };
    // One Run button → both calls share the same levers (deterministic core).
    Promise.all([runScenarios(body), runSimulation(body)])
      .then(([scenarios, simulation]) => {
        if (validScenarios(scenarios) === null) {
          setError("Unexpected /api/scenarios response shape (missing strategies/anchor)");
          return;
        }
        if (validSimulation(simulation) === null) {
          setError("Unexpected /api/simulation response shape (missing strategies/data_basis)");
          return;
        }
        setScenarioData(scenarios);
        setSimulationData(simulation);
      })
      .catch((err: unknown) => {
        if (err instanceof ApiError && err.status === 404) {
          setNotFound(true); // no dataset → empty state (§5.3)
        } else {
          setError(err instanceof ApiError ? err.message : String(err));
        }
      })
      .finally(() => {
        setRunning(false);
      });
  };

  const today = strategyById(scenarioData, "fixed_frequency");
  const plan = strategyById(scenarioData, "demand_driven");
  const anchorPct =
    scenarioData !== null && isFiniteNumber(scenarioData.observed_anchor.share_full_or_overfull_pct)
      ? `${scenarioData.observed_anchor.share_full_or_overfull_pct.toFixed(1)} %`
      : null;

  // Timeline data: merge both strategies' days by index (lengths tolerated).
  const timeline = useMemo(() => {
    if (simulationData === null) return [];
    const fixed = simulationData.strategies.find((s) => s.id === "fixed_frequency");
    const demand = simulationData.strategies.find((s) => s.id === "demand_driven");
    const len = Math.max(fixed?.days.length ?? 0, demand?.days.length ?? 0);
    const rows: Array<{
      date: string;
      fixed: number | null;
      demand: number | null;
    }> = [];
    for (let i = 0; i < len; i += 1) {
      rows.push({
        date: fixed?.days[i]?.date ?? demand?.days[i]?.date ?? "",
        fixed: fixed?.days[i]?.collections ?? null,
        demand: demand?.days[i]?.collections ?? null,
      });
    }
    return rows;
  }, [simulationData]);

  const maxCollections = timeline.reduce(
    (max, row) => Math.max(max, row.fixed ?? 0, row.demand ?? 0),
    0,
  );

  const sliderRow = (
    field: SliderField,
    labelKey: TranslationKey,
    unit: string,
  ) => {
    const bounds = SLIDER_BOUNDS[field];
    const value = sliders[field];
    const disabled = !configReady || value === undefined;
    return (
      <label className="block text-xs text-slate-700">
        <span className="font-medium">
          {t(lang, labelKey)} [{unit}]
        </span>
        <span className="ml-1 font-semibold text-slate-900">
          {disabled ? "—" : (value ?? 0).toLocaleString("en-US")}
        </span>
        <input
          type="range"
          min={bounds.min}
          max={bounds.max}
          step={bounds.step}
          value={disabled ? bounds.min : (value ?? bounds.min)}
          disabled={disabled}
          onChange={(e) => setSliders((s) => ({ ...s, [field]: Number(e.target.value) }))}
          data-testid={`slider-${field}`}
          className="mt-1 w-full accent-sky-700"
        />
      </label>
    );
  };

  return (
    <div className="space-y-4" data-testid="scenarios-panel">
      <Panel
        title={t(lang, "scenarios.title")}
        subtitle={t(lang, "scenarios.subtitle")}
        testid="scenarios-levers"
      >
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          {sliderRow("frequency_days", "scenarios.frequencyDays", "days")}
          {sliderRow("containers_per_series", "scenarios.containersPerSeries", "containers")}
          {sliderRow("cost_per_truck_day_eur", "scenarios.costPerDay", "EUR/day")}
          {sliderRow("max_shift_minutes", "scenarios.shift", "min")}
          {sliderRow("vehicle_volume_capacity_litres", "scenarios.capacity", "litres")}
        </div>
        <div className="mt-3 flex items-center gap-3">
          <button
            type="button"
            onClick={run}
            disabled={running || !configReady}
            className="rounded bg-sky-700 px-3 py-1.5 text-sm font-semibold text-white disabled:opacity-50"
            data-testid="scenarios-run"
          >
            {running ? t(lang, "scenarios.running") : t(lang, "scenarios.run")}
          </button>
          {!configReady ? (
            <span className="text-xs text-slate-500">{t(lang, "scenarios.waitingForConfig")}</span>
          ) : null}
        </div>

        {running ? <div className="mt-3"><LoadingState label={t(lang, "scenarios.loading")} /></div> : null}
        {error !== null && !running ? (
          <div className="mt-3"><ErrorState label={t(lang, "scenarios.error")} hint={error} /></div>
        ) : null}
        {notFound && !running && error === null ? (
          <div className="mt-3"><EmptyState label={t(lang, "scenarios.noDataset")} /></div>
        ) : null}

        {scenarioData !== null && today !== null && plan !== null && !running ? (
          <div className="mt-3 space-y-2">
            <p
              className="rounded border border-sky-200 bg-sky-50 px-3 py-2 text-xs font-semibold text-sky-900"
              data-testid="scenarios-anchor"
            >
              {anchorPct !== null
                ? tf(lang, "overview.toggle.anchor", { pct: anchorPct })
                : t(lang, "overview.toggle.anchorUnavailable")}{" "}
              <span className="font-normal">{t(lang, "overview.toggle.anchorBasis")}</span>
            </p>
            <div className="grid gap-3 md:grid-cols-2">
              <StrategyCard lang={lang} strategy={today} testid="scenarios-strategy-fixed" />
              <StrategyCard lang={lang} strategy={plan} testid="scenarios-strategy-demand" />
            </div>
            <TechDetails label={t(lang, "techdetails.label")} testid="scenarios-tech-details">
              {scenarioData.config_echo !== null && scenarioData.config_echo !== undefined ? (
                <p data-testid="scenarios-config-echo">
                  {Object.entries(scenarioData.config_echo)
                    .map(([k, v]) => `${k}: ${String(v)}`)
                    .join(" · ")}
                </p>
              ) : null}
              <p data-testid="scenarios-skipped">
                {tf(lang, "scenarios.skipped", { n: scenarioData.skipped_series.length })}
                {scenarioData.skipped_series.length > 0
                  ? ` — ${[...new Set(scenarioData.skipped_series.map((s) => s.reason))].join(", ")}`
                  : ""}
              </p>
              <ul className="list-disc pl-4">
                {scenarioData.assumptions.map((line) => (
                  <li key={line}>{line}</li>
                ))}
              </ul>
            </TechDetails>
          </div>
        ) : null}
      </Panel>

      {/* Timeline (W9/W5 support): daily replay; the mega-day note is
          UNCONDITIONAL — it explains a model consequence, not observed data. */}
      <Panel
        title={t(lang, "scenarios.timeline.title")}
        subtitle={t(lang, "scenarios.timeline.subtitle")}
        testid="scenarios-timeline"
      >
        {simulationData !== null && !running ? (
          <div className="space-y-2">
            <p className="text-xs text-slate-600" data-testid="timeline-basis">
              {t(lang, "scenarios.timeline.basis")}
            </p>
            {maxCollections > 0 ? (
              <div className="space-y-2" data-testid="timeline-chart">
                {(
                  [
                    ["fixed", "scenarios.timeline.fixedLegend", "bg-amber-700"],
                    ["demand", "scenarios.timeline.demandLegend", "bg-sky-700"],
                  ] as const
                ).map(([key, labelKey, colour]) => (
                  <div key={key}>
                    <p className="text-xs font-medium text-slate-600">{t(lang, labelKey)}</p>
                    <div className="flex h-12 items-end gap-px">
                      {timeline.map((row, i) => {
                        const v = row[key];
                        const height =
                          v !== null && maxCollections > 0
                            ? Math.max(1, Math.round((v / maxCollections) * 100))
                            : 0;
                        return (
                          <div
                            key={`${key}-${i}`}
                            className={`${colour} w-full min-w-[1px]`}
                            style={{ height: `${height}%` }}
                            title={`${row.date}: ${v ?? 0}`}
                          />
                        );
                      })}
                    </div>
                  </div>
                ))}
                <p className="text-xs text-slate-600">
                  {tf(lang, "scenarios.timeline.spike", {
                    n: maxCollections.toLocaleString("en-US"),
                  })}
                </p>
              </div>
            ) : (
              <EmptyState label={t(lang, "scenarios.timeline.empty")} />
            )}
            {/* Model-consequence label (§5.2.5 addendum) — always visible. */}
            <p
              className="rounded border border-amber-200 bg-amber-50 px-3 py-2 text-xs leading-relaxed text-amber-800"
              data-testid="timeline-megaday-note"
            >
              {t(lang, "scenarios.timeline.megaDay")}
            </p>
            {simulationData.calibration !== null && simulationData.calibration !== undefined ? (
              <TechDetails label={t(lang, "techdetails.label")} testid="timeline-tech-details">
                <p data-testid="timeline-calibration">
                  {tf(lang, "scenarios.timeline.calibration", {
                    sim:
                      simulationData.calibration.simulated_fill_at_emptying_median_pct !== null
                        ? simulationData.calibration.simulated_fill_at_emptying_median_pct.toFixed(1)
                        : "—",
                    obs:
                      simulationData.calibration.observed_fill_at_emptying_median_pct !== null
                        ? simulationData.calibration.observed_fill_at_emptying_median_pct.toFixed(1)
                        : "—",
                  })}
                </p>
                <ul className="list-disc pl-4">
                  {simulationData.assumptions.map((line) => (
                    <li key={line}>{line}</li>
                  ))}
                </ul>
              </TechDetails>
            ) : null}
          </div>
        ) : (
          !running && error === null && !notFound ? (
            <EmptyState label={t(lang, "scenarios.timeline.empty")} />
          ) : null
        )}
      </Panel>
    </div>
  );
}
