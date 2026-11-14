import { useState } from "react";
import {
  ApiError,
  runRoute,
  type PolicyConfigOverride,
  type Route,
  type RouteResponse,
  type RoutingConfigOverride,
} from "../lib/api";
import {
  formatKg,
  formatLitres,
  formatMetres,
  formatMinutes,
  formatPct,
  formatStopKey,
  provenanceLabel,
} from "../lib/format";
import { StatusBadge } from "./Badges";
import { ForecastParamsForm, type ForecastParams } from "./ForecastParamsForm";
import { Panel } from "./Panel";
import { RouteMap } from "./RouteMap";
import { TechDetails } from "./TechDetails";
import { EmptyState, ErrorState, LoadingState } from "./states";

/**
 * Route view (§5.1 POST /api/route): pipeline forecast → policy → geography →
 * solve. Shows map with per-route polylines and ordered stops, unserved stops
 * with reasons (never hidden, §4.4), totals with units, fleet recommendation,
 * and the echoed assumptions array ([demo assumption] labels).
 */
export function RoutePanel({
  defaultAsOf,
  policyOverride,
  routingOverride,
  onRoute,
}: {
  defaultAsOf: string | null;
  policyOverride: PolicyConfigOverride;
  routingOverride: RoutingConfigOverride;
  onRoute: (response: RouteResponse) => void;
}) {
  const [params, setParams] = useState<ForecastParams>({
    as_of_date: defaultAsOf ?? "",
    horizon_days: 28,
    method: "persistence",
  });
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<RouteResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleRun() {
    setBusy(true);
    setError(null);
    try {
      const response = await runRoute({
        as_of_date: params.as_of_date,
        horizon_days: params.horizon_days,
        method: params.method,
        policy_config: policyOverride,
        routing_config: routingOverride,
      });
      setResult(response);
      onRoute(response);
    } catch (err) {
      setResult(null);
      setError(err instanceof ApiError ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  const canRun =
    !busy &&
    params.as_of_date !== "" &&
    Number.isFinite(params.horizon_days) &&
    params.horizon_days >= 1;

  const solution = result?.solution ?? null;
  const degraded = solution !== null && (solution.status === "infeasible" || solution.status === "timeout");

  // Data-generated insight sentence (from the API solution, never hardcoded).
  const insightTitle =
    solution !== null
      ? `${solution.routes.length} route(s) serve ${solution.totals.stops_served} of ${solution.totals.stops_total} stops — ${solution.unserved.length} unserved are listed with reasons`
      : "5 · Route proposal";

  return (
    <Panel
      title={insightTitle}
      subtitle={
        <>
          What this shows: the order stops are visited, totals with units, and why each unserved
          stop was skipped. Why it matters: drivers get a feasible, explainable tour. Computed over{" "}
          <strong>synthetic demo geography</strong> — coordinates, depot, disposal, fleet and
          travel matrix are [demo assumption]; distances are straight-line derived, not road
          distance (§4.2/§5.3).
        </>
      }
      testid="route-panel"
    >
      <div className="flex flex-wrap items-end gap-3">
        <ForecastParamsForm value={params} onChange={setParams} disabled={busy} />
        <button
          type="button"
          onClick={() => void handleRun()}
          disabled={!canRun}
          className="rounded bg-sky-700 px-3 py-1.5 text-sm font-medium text-white hover:bg-sky-800 disabled:opacity-50"
          data-testid="route-run"
        >
          {busy ? "Solving…" : "Compute route proposal"}
        </button>
      </div>

      {busy ? <div className="mt-3"><LoadingState label="Forecasting, selecting and solving" hint="solver time limit bounded" /></div> : null}
      {error !== null && !busy ? (
        <div className="mt-3"><ErrorState label="Route computation failed" hint={error} /></div>
      ) : null}
      {!busy && result === null && error === null ? (
        <div className="mt-3">
          <EmptyState
            label="No route computed yet"
            hint="Run with an as-of date to get a labelled demo route proposal."
          />
        </div>
      ) : null}

      {result !== null && !busy && solution !== null ? (
        <div className="mt-3 space-y-4" data-testid="route-result">
          {degraded ? (
            <div
              className="rounded-md border border-amber-400 bg-amber-50 px-3 py-2 text-sm text-amber-900"
              data-testid="degraded-status"
            >
              Solver returned <strong>{solution.status}</strong> — unserved stops are listed below,
              never hidden (contract §4.4).
            </div>
          ) : null}

          {/* Solver status + provenance are technical: collapsible details
              (still in the DOM for tests/tools, hidden from the main view). */}
          <TechDetails label="Technical details" testid="route-tech-details">
            <div className="flex flex-wrap items-center gap-2">
              <StatusBadge status={solution.status} />
              <span>{provenanceLabel(solution.distance_provenance)}</span>
            </div>
            <p>Objective value: {solution.objective_value ?? "—"}</p>
          </TechDetails>

          <TotalsBar response={result} />

          <RouteMap solution={solution} />

          <div className="grid gap-4 lg:grid-cols-2">
            <div className="space-y-3">
              <p className="text-sm font-semibold text-slate-700">
                Routes ({solution.routes.length})
              </p>
              {solution.routes.length === 0 ? (
                <p className="text-xs text-slate-400">No routes — all stops unserved.</p>
              ) : (
                solution.routes.map((route, i) => (
                  <RouteCard key={i} index={i} route={route} />
                ))
              )}
            </div>
            <div className="space-y-3">
              <p className="text-sm font-semibold text-slate-700">
                Unserved ({solution.unserved.length})
              </p>
              {solution.unserved.length === 0 ? (
                <p className="text-xs text-slate-400" data-testid="unserved-none">
                  All stops served.
                </p>
              ) : (
                <ul
                  className="max-h-64 space-y-1 overflow-auto rounded border border-red-200 bg-red-50 p-2 text-xs text-red-800"
                  data-testid="unserved-list"
                >
                  {solution.unserved.map((u, i) => (
                    <li key={i}>
                      <span className="font-mono">{formatStopKey(u)}</span> — {u.reason}
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>
        </div>
      ) : null}
    </Panel>
  );
}

function TotalsBar({ response }: { response: RouteResponse }) {
  const { totals, fleet_recommendation } = response.solution;
  return (
    <div
      className="grid grid-cols-2 gap-3 rounded-md border border-slate-200 bg-slate-50 p-3 sm:grid-cols-3 lg:grid-cols-6"
      data-testid="route-totals"
    >
      <Total label="Distance" value={formatMetres(totals.distance_m)} />
      <Total label="Duration" value={formatMinutes(totals.duration_min)} />
      <Total label="Volume collected" value={formatLitres(totals.collected_volume_litres)} />
      <Total label="Weight collected" value={formatKg(totals.collected_weight_kg)} />
      <Total
        label="Stops served"
        value={`${totals.stops_served} of ${totals.stops_total}`}
      />
      <Total
        label={`Fleet: ${fleet_recommendation.vehicle_type_id}`}
        value={`${fleet_recommendation.count} vehicle(s) — by volume ⌈${fleet_recommendation.basis.ceil_by_volume}⌉, by weight ⌈${fleet_recommendation.basis.ceil_by_weight}⌉ (brief §4)`}
      />
    </div>
  );
}

function Total({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-xs font-medium uppercase tracking-wide text-slate-500">{label}</p>
      <p className="text-sm font-semibold text-slate-900">{value}</p>
    </div>
  );
}

function RouteCard({ index, route }: { index: number; route: Route }) {
  return (
    <div
      className="rounded border border-slate-200 p-2 text-xs"
      data-testid={`route-card-${index}`}
    >
      <p className="font-semibold text-slate-800">
        Route {index + 1} · {route.vehicle_type_id} · {formatMetres(route.distance_m)} ·{" "}
        {formatMinutes(route.duration_minutes)}
      </p>
      <ol className="mt-1 list-decimal space-y-0.5 pl-5 text-slate-600">
        {route.sequence.map((node, j) => {
          if ("location_id" in node) {
            return (
              <li key={j} className="font-mono">
                {node.location_id.slice(0, 13)}… · {node.material_type} ·{" "}
                {formatPct(node.predicted_fill_pct, 0)} ·{" "}
                {formatLitres(node.container_volume_litres)}
              </li>
            );
          }
          return (
            <li key={j}>
              {"service_minutes" in node ? "Disposal" : "Depot"} {node.id} ({node.name})
            </li>
          );
        })}
      </ol>
      {route.load_progression.length > 0 ? (
        <p className="mt-1 text-slate-500">
          Load progression (L / kg after each stop):{" "}
          {route.load_progression
            .map(([volumeLitres, weightKg]) => `${volumeLitres.toLocaleString("en-US")} L / ${weightKg.toLocaleString("en-US")} kg`)
            .join(" → ")}
        </p>
      ) : null}
    </div>
  );
}
