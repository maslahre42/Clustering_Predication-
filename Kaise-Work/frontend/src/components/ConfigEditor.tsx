import { useState, type ReactNode } from "react";
import {
  MATERIAL_TYPES,
  type ConfigDefaults,
  type MaterialType,
  type PolicyConfigOverride,
  type RoutingConfigOverride,
} from "../lib/api";
import { formatDensity } from "../lib/format";
import { AssumptionTag } from "./Badges";
import { Panel } from "./Panel";
import { ErrorState, LoadingState } from "./states";

/**
 * Demo-config editor (§5.2 ConfigDefaults): §3.1 policy fields + §5.2 routing
 * fields. Empty input = inherit server default (no override sent). Per §4.6 the
 * [demo assumption] tag stays visible on every assumption field even after the
 * value is edited — overrides never relabel facts.
 */

type NumberKind = "int" | "float";

interface FieldSpec {
  name: string;
  label: string;
  unit: string;
  kind: NumberKind;
  /** "policy" or "routing" — which §5.2 defaults object holds this field */
  section: "policy" | "routing";
  /** dot path into routing defaults, e.g. "densities_kg_per_litre.brown" */
  defaultPath?: string;
}

const POLICY_NUMBER_FIELDS: FieldSpec[] = [
  { name: "select_threshold_pct", label: "Select threshold", unit: "%", kind: "int", section: "policy" },
  { name: "uncertainty_buffer_pct", label: "Uncertainty buffer", unit: "%", kind: "int", section: "policy" },
];

const ROUTING_NUMBER_FIELDS: FieldSpec[] = [
  { name: "container_volume_litres", label: "Container volume", unit: "L", kind: "int", section: "routing" },
  ...MATERIAL_TYPES.map(
    (m): FieldSpec => ({
      name: `densities_kg_per_litre.${m}`,
      label: `Density (${m})`,
      unit: "kg/L",
      kind: "float",
      section: "routing",
      defaultPath: `densities_kg_per_litre.${m}`,
    }),
  ),
  { name: "vehicle_volume_capacity_litres", label: "Vehicle volume capacity", unit: "L", kind: "int", section: "routing" },
  { name: "vehicle_weight_capacity_kg", label: "Vehicle weight capacity", unit: "kg", kind: "int", section: "routing" },
  { name: "vehicle_count_available", label: "Vehicles available", unit: "vehicles", kind: "int", section: "routing" },
  { name: "stop_service_minutes", label: "Stop service time", unit: "min", kind: "int", section: "routing" },
  { name: "disposal_service_minutes", label: "Disposal service time", unit: "min", kind: "int", section: "routing" },
  { name: "max_shift_minutes", label: "Max shift", unit: "min", kind: "int", section: "routing" },
  { name: "avg_speed_kmh", label: "Avg speed", unit: "km/h", kind: "float", section: "routing" },
  { name: "detour_factor", label: "Detour factor", unit: "× straight line", kind: "float", section: "routing" },
  { name: "solver_time_limit_s", label: "Solver time limit", unit: "s", kind: "float", section: "routing" },
];

type NumberText = Record<string, string>;

const inputClass = "w-28 rounded border border-slate-300 bg-white px-2 py-1 text-sm disabled:opacity-50";

const EMPTY_NUMBER_TEXT: NumberText = {};
for (const f of [...POLICY_NUMBER_FIELDS, ...ROUTING_NUMBER_FIELDS]) {
  EMPTY_NUMBER_TEXT[f.name] = "";
}

function parseNumber(text: string, kind: NumberKind): number | undefined {
  const trimmed = text.trim();
  if (trimmed === "") return undefined;
  const value = kind === "int" ? Number.parseInt(trimmed, 10) : Number.parseFloat(trimmed);
  return Number.isFinite(value) ? value : Number.NaN;
}

function defaultValue(config: ConfigDefaults | null, spec: FieldSpec): number | undefined {
  if (config === null) return undefined;
  if (spec.section === "policy") {
    const value = config.policy?.[spec.name as keyof ConfigDefaults["policy"]];
    return typeof value === "number" ? value : undefined;
  }
  if (spec.defaultPath !== undefined) {
    const [parent, child] = spec.defaultPath.split(".");
    const nested = (config.routing as unknown as Record<string, Record<string, number>>)?.[parent];
    const value = nested?.[child];
    return typeof value === "number" ? value : undefined;
  }
  const value = (config.routing as unknown as Record<string, unknown>)?.[spec.name];
  return typeof value === "number" ? value : undefined;
}

function isAssumption(config: ConfigDefaults | null, name: string): boolean {
  // Defensive: if the backend omitted assumption_fields, treat all config
  // fields as assumptions (§3.1/§4.6 — every default is one).
  if (config === null || !Array.isArray(config.assumption_fields)) return true;
  if (config.assumption_fields.length === 0) return true;
  return config.assumption_fields.includes(name) || config.assumption_fields.includes("all");
}

export function ConfigEditor({
  config,
  loading,
  error,
  policyOverride,
  routingOverride,
  onPolicyChange,
  onRoutingChange,
}: {
  config: ConfigDefaults | null;
  loading: boolean;
  error: string | null;
  policyOverride: PolicyConfigOverride;
  routingOverride: RoutingConfigOverride;
  onPolicyChange: (override: PolicyConfigOverride) => void;
  onRoutingChange: (override: RoutingConfigOverride) => void;
}) {
  const [policyText, setPolicyText] = useState<NumberText>(EMPTY_NUMBER_TEXT);
  const [routingText, setRoutingText] = useState<NumberText>(EMPTY_NUMBER_TEXT);
  const [overfullSelect, setOverfullSelect] = useState<"" | "true" | "false">("");

  function pushPolicy(next: NumberText, overfull: "" | "true" | "false") {
    setPolicyText(next);
    setOverfullSelect(overfull);
    const override: PolicyConfigOverride = {};
    for (const spec of POLICY_NUMBER_FIELDS) {
      const value = parseNumber(next[spec.name] ?? "", spec.kind);
      if (value !== undefined) {
        (override as Record<string, unknown>)[spec.name] = value;
      }
    }
    if (overfull !== "") override.overfull_always_selected = overfull === "true";
    onPolicyChange(override);
  }

  function pushRouting(next: NumberText) {
    setRoutingText(next);
    const override: RoutingConfigOverride = {};
    for (const spec of ROUTING_NUMBER_FIELDS) {
      const value = parseNumber(next[spec.name] ?? "", spec.kind);
      if (value === undefined) continue;
      if (spec.defaultPath !== undefined) {
        const child = spec.defaultPath.split(".")[1] as MaterialType;
        override.densities_kg_per_litre = {
          ...override.densities_kg_per_litre,
          [child]: value,
        };
      } else {
        (override as Record<string, unknown>)[spec.name] = value;
      }
    }
    onRoutingChange(override);
  }

  function reset() {
    pushPolicy({ ...EMPTY_NUMBER_TEXT }, "");
    pushRouting({ ...EMPTY_NUMBER_TEXT });
  }

  const invalid: string[] = [];
  for (const spec of [...POLICY_NUMBER_FIELDS, ...ROUTING_NUMBER_FIELDS]) {
    const text = (policyText[spec.name] ?? routingText[spec.name] ?? "").trim();
    if (text !== "" && Number.isNaN(parseNumber(text, spec.kind) as number)) {
      invalid.push(`${spec.label} (${spec.unit})`);
    }
  }

  return (
    <Panel
      title="Demo configuration (overrides)"
      subtitle={
        <>
          Defaults come from GET /api/config. Empty field = use default (no override sent). Every
          [demo assumption] stays labelled — editing a value never turns it into an observed fact
          (§4.6/§5.3).
        </>
      }
      testid="config-panel"
    >
      {loading ? <LoadingState label="Loading config defaults" /> : null}
      {error !== null && !loading ? (
        <ErrorState label="Could not load config" hint={`${error} — panels run with server defaults.`} />
      ) : null}

      {!loading && error === null ? (
        <div className="space-y-3" data-testid="config-editor">
          <FieldGroup caption="Policy (§3.1)">
            {POLICY_NUMBER_FIELDS.map((spec) => (
              <NumberFieldRow
                key={spec.name}
                spec={spec}
                text={policyText[spec.name] ?? ""}
                config={config}
                disabled={loading}
                onChange={(text) => pushPolicy({ ...policyText, [spec.name]: text }, overfullSelect)}
              />
            ))}
            <FieldRow
              label="Overfull always selected"
              unit=""
              assumption={isAssumption(config, "overfull_always_selected")}
              defaultValue={config?.policy?.overfull_always_selected}
              renderDefault={(v) => (v === undefined ? "—" : String(v))}
            >
              <select
                value={overfullSelect}
                disabled={loading}
                onChange={(e) => pushPolicy(policyText, e.target.value as "" | "true" | "false")}
                className={`rounded border border-slate-300 bg-white px-2 py-1 text-sm ${inputClass}`}
                data-testid="config-overfull_always_selected"
              >
                <option value="">inherit default</option>
                <option value="true">always select overfull</option>
                <option value="false">judge on numeric fill</option>
              </select>
            </FieldRow>
          </FieldGroup>

          <FieldGroup caption="Routing (§5.2 routing_config, §4.6 defaults)">
            {ROUTING_NUMBER_FIELDS.map((spec) => (
              <NumberFieldRow
                key={spec.name}
                spec={spec}
                text={routingText[spec.name] ?? ""}
                config={config}
                disabled={loading}
                onChange={(text) => pushRouting({ ...routingText, [spec.name]: text })}
              />
            ))}
          </FieldGroup>

          {invalid.length > 0 ? (
            <p className="text-xs text-red-600" data-testid="config-invalid">
              Ignored (not valid numbers): {invalid.join(", ")}
            </p>
          ) : null}

          <div className="flex items-center justify-between">
            <button
              type="button"
              onClick={reset}
              className="rounded border border-slate-300 px-3 py-1 text-xs font-medium text-slate-600 hover:bg-slate-50"
              data-testid="config-reset"
            >
              Reset to defaults
            </button>
            <p className="text-xs text-slate-500" data-testid="override-count">
              Active overrides: {Object.keys(policyOverride).length + Object.keys(routingOverride).length}
            </p>
          </div>
        </div>
      ) : null}
    </Panel>
  );
}

function FieldGroup({ caption, children }: { caption: string; children: ReactNode }) {
  return (
    <fieldset className="rounded border border-slate-200 p-2">
      <legend className="px-1 text-xs font-semibold uppercase tracking-wide text-slate-500">
        {caption}
      </legend>
      <div className="space-y-1.5">{children}</div>
    </fieldset>
  );
}

function FieldRow({
  label,
  unit,
  assumption,
  defaultValue: def,
  renderDefault,
  children,
}: {
  label: string;
  unit: string;
  assumption: boolean;
  defaultValue: unknown;
  renderDefault: (value: unknown) => string;
  children: ReactNode;
}) {
  return (
    <div className="flex flex-wrap items-center gap-2 text-xs">
      <span className="w-44 font-medium text-slate-700">{label}</span>
      {children}
      <span className="text-slate-400">
        {unit !== "" ? `(${unit}) ` : ""}default: {renderDefault(def)}
      </span>
      {assumption ? <AssumptionTag /> : null}
    </div>
  );
}

function NumberFieldRow({
  spec,
  text,
  config,
  disabled,
  onChange,
}: {
  spec: FieldSpec;
  text: string;
  config: ConfigDefaults | null;
  disabled: boolean;
  onChange: (text: string) => void;
}) {
  const def = defaultValue(config, spec);
  const parsed = parseNumber(text, spec.kind);
  const invalidInput = text.trim() !== "" && (parsed === undefined || Number.isNaN(parsed));
  const defaultDisplay =
    spec.unit === "kg/L" ? formatDensity(def) : def === undefined ? "—" : `${def.toLocaleString("en-US")} ${spec.unit}`;
  return (
    <FieldRow
      label={spec.label}
      unit={spec.unit}
      assumption={isAssumption(config, spec.name)}
      defaultValue={def}
      renderDefault={() => defaultDisplay}
    >
      <input
        type="text"
        inputMode="decimal"
        value={text}
        disabled={disabled}
        aria-label={spec.label}
        onChange={(e) => onChange(e.target.value)}
        className={`${inputClass} ${invalidInput ? "border-red-400 bg-red-50" : ""}`}
        data-testid={`config-${spec.name}`}
      />
    </FieldRow>
  );
}
