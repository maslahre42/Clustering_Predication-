import { MATERIAL_TYPES, type MaterialType, type ReasonCode, type SolveStatus } from "../lib/api";
import { reasonLabel } from "../lib/format";

/**
 * Badges for enums. Reason codes (§3.4) and solver status (§4.3) get stable,
 * colour-coded labels; [demo assumption] tags stay visually explicit.
 */

const REASON_STYLES: Record<ReasonCode, string> = {
  at_or_above_threshold: "bg-emerald-100 text-emerald-800 border-emerald-300",
  overfull_state: "bg-red-100 text-red-800 border-red-300",
  below_threshold: "bg-slate-100 text-slate-600 border-slate-300",
  no_forecast: "bg-amber-100 text-amber-800 border-amber-300",
};

export function ReasonBadge({ code }: { code: ReasonCode }) {
  return (
    <span
      className={`inline-block rounded border px-1.5 py-0.5 text-xs font-medium ${REASON_STYLES[code] ?? "bg-slate-100 text-slate-600 border-slate-300"}`}
      data-testid="reason-badge"
    >
      {reasonLabel(code)}
    </span>
  );
}

const STATUS_STYLES: Record<SolveStatus, string> = {
  optimal: "bg-emerald-100 text-emerald-800 border-emerald-300",
  feasible: "bg-sky-100 text-sky-800 border-sky-300",
  infeasible: "bg-red-100 text-red-800 border-red-300",
  timeout: "bg-amber-100 text-amber-800 border-amber-300",
};

export function StatusBadge({ status }: { status: SolveStatus }) {
  return (
    <span
      className={`inline-block rounded border px-2 py-0.5 text-xs font-semibold uppercase ${STATUS_STYLES[status] ?? "bg-slate-100 text-slate-600 border-slate-300"}`}
      data-testid="solve-status"
    >
      solver status: {status}
    </span>
  );
}

/** [demo assumption] tag — always rendered, overrides never relabel facts (§4.6). */
export function AssumptionTag({ text = "demo assumption" }: { text?: string }) {
  return (
    <span
      className="inline-block rounded border border-amber-400 bg-amber-50 px-1.5 py-0.5 text-xs font-medium text-amber-800"
      data-testid="assumption-tag"
    >
      [demo assumption{"]"}
      {text === "demo assumption" ? null : <span className="font-normal"> {text}</span>}
    </span>
  );
}

/**
 * [representative] tag (§4.6 v3): the value came from the challenge
 * representative (verbal), not from data — visually distinct from the amber
 * [demo assumption] tag, still clearly NOT an observed fact (§5.3).
 */
export function RepresentativeTag() {
  return (
    <span
      className="inline-block rounded border border-sky-400 bg-sky-50 px-1.5 py-0.5 text-xs font-medium text-sky-800"
      data-testid="representative-tag"
    >
      [representative]
    </span>
  );
}

const MATERIAL_SWATCH: Record<MaterialType, string> = {
  brown: "bg-amber-800",
  green: "bg-emerald-600",
  white: "bg-slate-400",
};

export function MaterialBadge({ material }: { material: MaterialType }) {
  if (!MATERIAL_TYPES.includes(material)) return <span>{material}</span>;
  return (
    <span className="inline-flex items-center gap-1 text-xs text-slate-600">
      <span className={`inline-block h-2.5 w-2.5 rounded-full ${MATERIAL_SWATCH[material]}`} aria-hidden />
      {material}
    </span>
  );
}

/** State badge for predicted_state (§2.2): normal / full / overfull stay distinct. */
const STATE_STYLES: Record<string, string> = {
  normal: "bg-slate-100 text-slate-600 border-slate-300",
  full: "bg-orange-100 text-orange-800 border-orange-300",
  overfull: "bg-red-100 text-red-800 border-red-300",
};

export function StateBadge({ state }: { state: string | null }) {
  if (state === null) return <span className="text-xs text-slate-400">no state</span>;
  return (
    <span
      className={`inline-block rounded border px-1.5 py-0.5 text-xs font-medium ${STATE_STYLES[state] ?? "bg-slate-100 text-slate-600 border-slate-300"}`}
      data-testid="state-badge"
    >
      {state}
    </span>
  );
}
