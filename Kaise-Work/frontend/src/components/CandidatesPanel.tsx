import { useState, type ReactNode } from "react";
import {
  ApiError,
  runCandidates,
  type CandidateRequest,
  type PolicyConfigOverride,
  type SelectionResponse,
} from "../lib/api";
import { formatDate, formatPct } from "../lib/format";
import { MaterialBadge, ReasonBadge, StateBadge } from "./Badges";
import { ForecastParamsForm, type ForecastParams } from "./ForecastParamsForm";
import { Panel } from "./Panel";
import { EmptyState, ErrorState, LoadingState } from "./states";

/**
 * Forecast & candidate selection (§5.1 POST /api/forecasts + /api/candidates).
 * Selection and skips are both shown with reason_code badges + detail — nothing
 * is silently dropped (§3.4). Policy overrides come from the demo-config editor.
 */
export function CandidatesPanel({
  defaultAsOf,
  policyOverride,
}: {
  defaultAsOf: string | null;
  policyOverride: PolicyConfigOverride;
}) {
  const [params, setParams] = useState<ForecastParams>({
    as_of_date: defaultAsOf ?? "",
    horizon_days: 28,
    method: "persistence",
  });
  const [busy, setBusy] = useState(false);
  const [selection, setSelection] = useState<SelectionResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleRun() {
    setBusy(true);
    setError(null);
    const request: CandidateRequest = {
      as_of_date: params.as_of_date,
      horizon_days: params.horizon_days,
      method: params.method,
      policy_config: policyOverride,
    };
    try {
      setSelection(await runCandidates(request));
    } catch (err) {
      setSelection(null);
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

  // Data-generated insight sentence (from the API selection, never hardcoded).
  const insightTitle =
    selection !== null
      ? `${selection.selected.length} of ${selection.selected.length + selection.skipped.length} containers are expected to need emptying by ${selection.target_date ?? "—"} — ${selection.skipped.length} can wait`
      : "4 · Forecast & candidate stops";

  return (
    <Panel
      title={insightTitle}
      subtitle={
        <>
          What this shows: predicted fill per container and the policy decision with its reason.
          Why it matters: only containers that likely need service enter the route plan.
          Predicted fill is a <strong>model output</strong> [predicted], not observed. Selected vs
          skipped per policy §3 with reasons.
        </>
      }
      testid="candidates-panel"
    >
      <div className="flex flex-wrap items-end gap-3">
        <ForecastParamsForm value={params} onChange={setParams} disabled={busy} />
        <button
          type="button"
          onClick={() => void handleRun()}
          disabled={!canRun}
          className="rounded bg-sky-700 px-3 py-1.5 text-sm font-medium text-white hover:bg-sky-800 disabled:opacity-50"
          data-testid="candidates-run"
        >
          {busy ? "Running…" : "Run forecast & selection"}
        </button>
      </div>

      {busy ? <div className="mt-3"><LoadingState label="Forecasting and selecting candidates" /></div> : null}
      {error !== null && !busy ? (
        <div className="mt-3"><ErrorState label="Candidate selection failed" hint={error} /></div>
      ) : null}
      {!busy && selection === null && error === null ? (
        <div className="mt-3">
          <EmptyState
            label="No selection yet"
            hint="Pick as-of date + horizon and run to see predicted candidates."
          />
        </div>
      ) : null}

      {selection !== null && !busy ? (
        <div className="mt-3 space-y-3" data-testid="selection-result">
          <p className="text-xs text-slate-600">
            Batch {formatDate(selection.as_of_date)} → target {formatDate(selection.target_date)} ·
            selected <strong>{selection.selected.length}</strong> · skipped{" "}
            <strong>{selection.skipped.length}</strong>
          </p>
          <p className="text-xs text-slate-500">
            Effective policy (echo): threshold {selection.config.select_threshold_pct} % · buffer{" "}
            {selection.config.uncertainty_buffer_pct} % · overfull always selected:{" "}
            {String(selection.config.overfull_always_selected)} — all [demo assumption]
          </p>

          <SelectionTable
            caption="Selected"
            testid="selected-rows"
            rows={selection.selected.map((c) => ({
              key: `${c.location_id}·${c.material_type}`,
              locationId: c.location_id,
              material: <MaterialBadge material={c.material_type} />,
              fill: formatPct(c.predicted_fill_pct),
              state: <StateBadge state={c.predicted_state} />,
              reason: <ReasonBadge code={c.reason_code} />,
              detail: c.detail,
            }))}
            emptyLabel="No containers selected"
          />
          <SelectionTable
            caption="Skipped"
            testid="skipped-rows"
            rows={selection.skipped.map((s) => ({
              key: `${s.location_id}·${s.material_type}`,
              locationId: s.location_id,
              material: <MaterialBadge material={s.material_type} />,
              fill: formatPct(s.predicted_fill_pct),
              state: <StateBadge state={s.predicted_state} />,
              reason: <ReasonBadge code={s.reason_code} />,
              detail: s.detail,
            }))}
            emptyLabel="Nothing skipped"
          />
        </div>
      ) : null}
    </Panel>
  );
}

interface RowSpec {
  key: string;
  locationId: string;
  material: ReactNode;
  fill: string;
  state: ReactNode;
  reason: ReactNode;
  detail: string;
}

function SelectionTable({
  caption,
  rows,
  emptyLabel,
  testid,
}: {
  caption: string;
  rows: RowSpec[];
  emptyLabel: string;
  testid: string;
}) {
  return (
    <div>
      <p className="mb-1 text-sm font-semibold text-slate-700">
        {caption} ({rows.length})
      </p>
      {rows.length === 0 ? (
        <p className="text-xs text-slate-400">{emptyLabel}</p>
      ) : (
        <div className="max-h-64 overflow-auto rounded border border-slate-200">
          <table className="w-full text-left text-xs">
            <thead className="sticky top-0 bg-slate-100 text-slate-600">
              <tr>
                <th className="px-2 py-1.5">Location</th>
                <th className="px-2 py-1.5">Material</th>
                <th className="px-2 py-1.5">Predicted fill</th>
                <th className="px-2 py-1.5">State</th>
                <th className="px-2 py-1.5">Reason</th>
                <th className="px-2 py-1.5">Detail</th>
              </tr>
            </thead>
            <tbody data-testid={testid}>
              {rows.map((row) => (
                <tr key={row.key} className="border-t border-slate-100">
                  <td className="px-2 py-1.5 font-mono" title={row.locationId}>
                    {row.locationId.slice(0, 13)}…
                  </td>
                  <td className="px-2 py-1.5">{row.material}</td>
                  <td className="px-2 py-1.5">{row.fill}</td>
                  <td className="px-2 py-1.5">{row.state}</td>
                  <td className="px-2 py-1.5">{row.reason}</td>
                  <td className="px-2 py-1.5 text-slate-500">{row.detail}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
