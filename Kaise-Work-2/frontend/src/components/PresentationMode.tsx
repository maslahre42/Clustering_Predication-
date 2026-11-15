import { useEffect, useMemo, useRef, useState } from "react";
import {
  fetchComparison,
  fetchDaysToFull,
  runCandidates,
  runScenarios,
  type ComparisonResponse,
  type DaysToFullResponse,
  type DatasetSummary,
  type ScenarioResponse,
  type SelectionResponse,
} from "../lib/api";
import { t, tf, type Lang, type TranslationKey } from "../lib/i18n";
import { RECOMMENDATION_HORIZON_DAYS } from "./Overview";

/**
 * W5 (M16 v4): presentation mode — 6 slides, big type, ←/→ navigation, Esc
 * closes, native fullscreen (requestFullscreen, gracefully caught). Honesty
 * rules (§6) hold on EVERY slide: labels ([observed]/[predicted]/simulation
 * basis, straight-line distance) are never hidden; every number comes from a
 * live response (comparison / scenarios / days-to-full / candidates) and a
 * step whose data is missing renders an explicit "data not available" note —
 * never a fabricated value or a hard-coded figure.
 */

const STEP_COUNT = 6;

export interface PresentationModeProps {
  lang: Lang;
  summary: DatasetSummary | null;
  onClose: () => void;
}

interface Slice<T> {
  data: T | null;
  loading: boolean;
  error: boolean;
}

const initialSlice = <T,>(): Slice<T> => ({ data: null, loading: true, error: false });

function isFiniteNumber(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value);
}

/** Basis label shown on every data slide (§6 vocabulary). */
function BasisLabel({ children }: { children: React.ReactNode }) {
  return (
    <p className="mt-2 text-base text-amber-200" data-testid="presentation-basis">
      {children}
    </p>
  );
}

export function PresentationMode({ lang, summary, onClose }: PresentationModeProps) {
  const [step, setStep] = useState(0);
  const overlayRef = useRef<HTMLDivElement | null>(null);

  const [comparison, setComparison] = useState<Slice<ComparisonResponse>>(initialSlice);
  const [scenarios, setScenarios] = useState<Slice<ScenarioResponse>>(initialSlice);
  const [daysToFull, setDaysToFull] = useState<Slice<DaysToFullResponse>>(initialSlice);
  const [selection, setSelection] = useState<Slice<SelectionResponse>>(initialSlice);

  const asOf =
    typeof summary?.date_max === "string" && /^\d{4}-\d{2}-\d{2}$/.test(summary.date_max)
      ? summary.date_max
      : null;

  // Native fullscreen — some environments (jsdom, denied permission) reject;
  // the presentation still works inline, so failures are caught, never fatal.
  useEffect(() => {
    const el = overlayRef.current;
    if (el !== null && typeof el.requestFullscreen === "function") {
      el.requestFullscreen().catch(() => {});
    }
  }, []);

  // Own fetches — slides degrade individually when one source fails.
  useEffect(() => {
    let cancelled = false;
    fetchComparison()
      .then((data) => {
        if (!cancelled) setComparison({ data, loading: false, error: false });
      })
      .catch(() => {
        if (!cancelled) setComparison({ data: null, loading: false, error: true });
      });
    runScenarios({})
      .then((data) => {
        if (!cancelled) setScenarios({ data, loading: false, error: false });
      })
      .catch(() => {
        if (!cancelled) setScenarios({ data: null, loading: false, error: true });
      });
    fetchDaysToFull()
      .then((data) => {
        if (!cancelled) setDaysToFull({ data, loading: false, error: false });
      })
      .catch(() => {
        if (!cancelled) setDaysToFull({ data: null, loading: false, error: true });
      });
    if (asOf !== null) {
      runCandidates({ as_of_date: asOf, horizon_days: RECOMMENDATION_HORIZON_DAYS, method: "persistence" })
        .then((data) => {
          if (!cancelled) setSelection({ data, loading: false, error: false });
        })
        .catch(() => {
          if (!cancelled) setSelection({ data: null, loading: false, error: true });
        });
    } else {
      setSelection({ data: null, loading: false, error: false });
    }
    return () => {
      cancelled = true;
    };
  }, [asOf]);

  // ←/→ navigate, Esc closes (window-level so fullscreen keeps working).
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "ArrowRight") setStep((s) => Math.min(STEP_COUNT - 1, s + 1));
      else if (e.key === "ArrowLeft") setStep((s) => Math.max(0, s - 1));
      else if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handler);
    return () => {
      window.removeEventListener("keydown", handler);
    };
  }, [onClose]);

  const fillStats = summary?.fill_stats ?? null;
  const anchor = comparison.data?.observed_service_anchor ?? null;
  const todayStrategy = scenarios.data?.strategies.find((s) => s.id === "fixed_frequency") ?? null;
  const planStrategy = scenarios.data?.strategies.find((s) => s.id === "demand_driven") ?? null;
  const sweepAll = comparison.data?.scenarios.find((s) => s.method === "naive_sweep_all") ?? null;
  const optimised = comparison.data?.scenarios.find((s) => s.method === "ortools") ?? null;
  const savingsPct =
    sweepAll !== null &&
    optimised !== null &&
    comparison.data !== null &&
    comparison.data.gains.total_gain_m !== null &&
    sweepAll.distance_m > 0
      ? (comparison.data.gains.total_gain_m / sweepAll.distance_m) * 100
      : null;
  const costDelta =
    todayStrategy !== null && planStrategy !== null
      ? planStrategy.cost_eur_per_year - todayStrategy.cost_eur_per_year
      : null;

  const tanks = useMemo(() => {
    const byMaterial = daysToFull.data?.stats_by_material;
    if (byMaterial === undefined || byMaterial === null) return [];
    return (["brown", "green", "white"] as const).map((material) => ({
      material,
      label: t(lang, `legend.${material}` as import("../lib/i18n").TranslationKey),
      medianDays: byMaterial[material]?.median_days ?? null,
      lowerBoundPct: byMaterial[material]?.lower_bound_share_pct ?? null,
    }));
  }, [daysToFull.data, lang]);

  const stepTitleKey = (
    [
      "presentation.s1.title",
      "presentation.s2.title",
      "presentation.s3.title",
      "presentation.s4.title",
      "presentation.s5.title",
      "presentation.s6.title",
    ] as const
  )[step] as TranslationKey;

  const dataUnavailable = (
    <p className="mt-6 text-2xl text-amber-200" data-testid="presentation-unavailable">
      {t(lang, "presentation.unavailable")}
    </p>
  );
  const dataLoading = (
    <p className="mt-6 text-2xl text-sky-200" data-testid="presentation-loading">
      {t(lang, "presentation.loading")}
    </p>
  );

  return (
    <div
      ref={overlayRef}
      className="fixed inset-0 z-50 flex flex-col bg-slate-900 p-10 text-white"
      data-testid="presentation-root"
    >
      <header className="flex items-baseline justify-between">
        <p className="text-lg font-semibold uppercase tracking-wide text-sky-300">
          {tf(lang, "presentation.stepOf", { i: step + 1, n: STEP_COUNT })}
        </p>
        <div className="flex items-center gap-4">
          <p className="text-sm text-slate-300">{t(lang, "presentation.hint")}</p>
          <button
            type="button"
            onClick={onClose}
            data-testid="presentation-close"
            className="rounded border border-slate-500 px-3 py-1 text-sm font-medium hover:bg-slate-800"
          >
            {t(lang, "presentation.close")}
          </button>
        </div>
      </header>

      <main className="mt-8 flex-1 overflow-auto">
        <h2 className="text-4xl font-bold">{t(lang, stepTitleKey)}</h2>

        {step === 0 ? (
          <div className="mt-6 max-w-4xl space-y-4">
            <p className="text-3xl leading-snug">{t(lang, "overview.headline")}</p>
            <p className="text-xl leading-relaxed text-slate-200">{t(lang, "overview.problem")}</p>
            <BasisLabel>{t(lang, "presentation.s1.basis")}</BasisLabel>
          </div>
        ) : null}

        {step === 1 ? (
          <div className="mt-6 max-w-4xl space-y-4">
            {comparison.loading || scenarios.loading ? (
              dataLoading
            ) : fillStats !== null && isFiniteNumber(fillStats.share_readings_full_or_above_pct) ? (
              <>
                <p className="text-6xl font-bold">
                  {fillStats.share_readings_full_or_above_pct.toFixed(1)} %
                </p>
                <p className="text-2xl text-slate-200">
                  {tf(lang, "presentation.s2.note", { thr: fillStats.threshold_pct })}
                </p>
                {anchor !== null && isFiniteNumber(anchor.share_full_or_overfull_pct) ? (
                  <p className="text-2xl text-sky-200">
                    {tf(lang, "overview.toggle.anchor", {
                      pct: `${anchor.share_full_or_overfull_pct.toFixed(1)} %`,
                    })}
                  </p>
                ) : null}
                <BasisLabel>{t(lang, "presentation.s2.basis")}</BasisLabel>
              </>
            ) : (
              dataUnavailable
            )}
          </div>
        ) : null}

        {step === 2 ? (
          <div className="mt-6 max-w-4xl space-y-4">
            {daysToFull.loading ? (
              dataLoading
            ) : tanks.length === 0 || daysToFull.error ? (
              dataUnavailable
            ) : (
              <>
                {tanks.map((tank) => (
                  <p key={tank.material} className="text-3xl">
                    <span className="font-bold">
                      {tank.medianDays !== null ? `${tank.medianDays.toFixed(1)} d` : "— d"}
                    </span>{" "}
                    <span className="text-slate-200">{tank.label}</span>
                    {tank.lowerBoundPct !== null && tank.lowerBoundPct > 0 ? (
                      <span className="ml-2 text-xl text-amber-200">
                        {tf(lang, "presentation.s3.atLeast", {
                          pct: `${tank.lowerBoundPct.toFixed(1)} %`,
                        })}
                      </span>
                    ) : null}
                  </p>
                ))}
                <p className="text-lg leading-relaxed text-amber-200">
                  {daysToFull.data?.assumptions[0] ?? ""}
                </p>
                <BasisLabel>{t(lang, "presentation.s3.basis")}</BasisLabel>
              </>
            )}
          </div>
        ) : null}

        {step === 3 ? (
          <div className="mt-6 max-w-4xl space-y-4">
            {selection.loading ? (
              dataLoading
            ) : selection.data !== null ? (
              <>
                <p className="text-6xl font-bold text-sky-300">
                  {selection.data.selected.length.toLocaleString("en-US")}
                </p>
                <p className="text-2xl text-slate-200">
                  {tf(lang, "overview.recommendation.toEmpty", {
                    n: selection.data.selected.length,
                  })}
                </p>
                <p className="text-2xl text-slate-300">
                  {tf(lang, "overview.recommendation.canWait", { n: selection.data.skipped.length })}
                </p>
                <BasisLabel>{t(lang, "presentation.s4.basis")}</BasisLabel>
              </>
            ) : (
              dataUnavailable
            )}
          </div>
        ) : null}

        {step === 4 ? (
          <div className="mt-6 max-w-4xl space-y-4">
            {scenarios.loading ? (
              dataLoading
            ) : todayStrategy !== null && planStrategy !== null ? (
              <>
                <p className="text-3xl">
                  <span className="font-bold">
                    {todayStrategy.cost_eur_total.toLocaleString("en-US")} EUR
                  </span>{" "}
                  <span className="text-slate-300">{t(lang, "overview.toggle.today")}</span>{" "}
                  <span className="text-slate-400">
                    · {todayStrategy.service.overflow_share_pct?.toFixed(1) ?? "—"} %{" "}
                    {t(lang, "presentation.s5.overflow")}
                  </span>
                </p>
                <p className="text-3xl">
                  <span className="font-bold text-sky-300">
                    {planStrategy.cost_eur_total.toLocaleString("en-US")} EUR
                  </span>{" "}
                  <span className="text-slate-300">{t(lang, "overview.toggle.plan")}</span>{" "}
                  <span className="text-slate-400">
                    · {planStrategy.service.overflow_share_pct?.toFixed(1) ?? "—"} %{" "}
                    {t(lang, "presentation.s5.overflow")}
                  </span>
                </p>
                {costDelta !== null ? (
                  costDelta === 0 ? (
                    <p className="text-2xl text-slate-300">
                      {t(lang, "presentation.s5.sameCost")}
                    </p>
                  ) : (
                    <p className="text-2xl text-amber-200">
                      {costDelta > 0
                        ? tf(lang, "overview.toggle.flagCostMoreServiceBetter", {
                            delta: `+${Math.round(costDelta).toLocaleString("en-US")} EUR/year`,
                          })
                        : tf(lang, "overview.toggle.flagCostLessServiceBetter", {
                            delta: `−${Math.abs(Math.round(costDelta)).toLocaleString("en-US")} EUR/year`,
                          })}
                    </p>
                  )
                ) : null}
                <BasisLabel>{t(lang, "overview.toggle.simBasis")}</BasisLabel>
              </>
            ) : (
              dataUnavailable
            )}
          </div>
        ) : null}

        {step === 5 ? (
          <div className="mt-6 max-w-4xl space-y-4">
            {comparison.loading ? (
              dataLoading
            ) : sweepAll !== null && optimised !== null ? (
              <>
                <p className="text-5xl font-bold">
                  {sweepAll.distance_m.toLocaleString("en-US")} m{" "}
                  <span className="text-slate-400">→</span>{" "}
                  <span className="text-sky-300">{optimised.distance_m.toLocaleString("en-US")} m</span>
                </p>
                <p className="text-2xl text-slate-200">
                  {t(lang, "overview.keynum.distance.fixed")} →{" "}
                  {t(lang, "overview.keynum.distance.optimised")}
                </p>
                {savingsPct !== null ? (
                  <p className="text-2xl text-emerald-300">
                    {tf(lang, "overview.compare.savings", { pct: `${savingsPct.toFixed(1)} %` })}
                  </p>
                ) : null}
                <BasisLabel>{t(lang, "presentation.s6.basis")}</BasisLabel>
              </>
            ) : (
              dataUnavailable
            )}
          </div>
        ) : null}
      </main>

      <footer className="mt-4 flex items-center justify-between">
        <button
          type="button"
          onClick={() => setStep((s) => Math.max(0, s - 1))}
          disabled={step === 0}
          data-testid="presentation-prev"
          className="rounded border border-slate-500 px-4 py-2 text-base font-semibold disabled:opacity-40"
        >
          ←
        </button>
        <p className="text-sm text-slate-400">{t(lang, "presentation.calmbasis")}</p>
        <button
          type="button"
          onClick={() => setStep((s) => Math.min(STEP_COUNT - 1, s + 1))}
          disabled={step === STEP_COUNT - 1}
          data-testid="presentation-next"
          className="rounded border border-slate-500 px-4 py-2 text-base font-semibold disabled:opacity-40"
        >
          →
        </button>
      </footer>
    </div>
  );
}
