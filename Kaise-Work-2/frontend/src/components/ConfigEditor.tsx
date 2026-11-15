import { useState, type ReactNode } from "react";
import {
  MATERIAL_TYPES,
  sourceLabel,
  type ConfigDefaults,
  type MaterialType,
  type PolicyConfigOverride,
  type RoutingConfigOverride,
  type TravelTimeMode,
} from "../lib/api";
import { formatDensity } from "../lib/format";
import { t, type Lang, type TranslationKey } from "../lib/i18n";
import { AssumptionTag, RepresentativeTag } from "./Badges";
import { Panel } from "./Panel";
import { ErrorState, LoadingState } from "./states";

/**
 * Config editor (§5.2 ConfigDefaults v3): §3.1 policy fields + §4.6 v3 routing
 * fields. Empty input = inherit server default (no override sent). Every field
 * carries its API-provided source tag: [representative] (verbal from the
 * challenge representative) is styled distinctly from [demo assumption]; a
 * missing `sources` map fails safe to [demo assumption] — editing a value
 * never turns it into an observed fact (§4.6/§5.3).
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
  /** key into ConfigDefaults.sources (defaults to name; nested fields set it) */
  sourceKey?: string;
  /** operator hint shown next to the default value (static, English) */
  hint?: string;
  /** operator hint translated via i18n (takes precedence over hint) */
  hintKey?: TranslationKey;
}

const POLICY_NUMBER_FIELDS: FieldSpec[] = [
  { name: "select_threshold_pct", label: "Select threshold", unit: "%", kind: "int", section: "policy" },
  { name: "uncertainty_buffer_pct", label: "Uncertainty buffer", unit: "%", kind: "int", section: "policy" },
];

/** Highlighted key parameters (M15): the five representative operating
 * parameters plus travel-time mode, cost parameters and the synthetic
 * geography knobs — each still tagged with its true source. */
const KEY_ROUTING_NUMBER_FIELDS: FieldSpec[] = [
  { name: "container_volume_litres", label: "Container volume", unit: "L", kind: "int", section: "routing" },
  ...MATERIAL_TYPES.map(
    (m): FieldSpec => ({
      name: `densities_kg_per_litre.${m}`,
      label: `Waste density (${m})`,
      unit: "kg/L",
      kind: "float",
      section: "routing",
      defaultPath: `densities_kg_per_litre.${m}`,
      sourceKey: "densities_kg_per_litre",
    }),
  ),
  { name: "vehicle_volume_capacity_litres", label: "Truck volume capacity", unit: "L", kind: "int", section: "routing" },
  { name: "vehicle_weight_capacity_kg", label: "Truck weight capacity", unit: "kg", kind: "int", section: "routing" },
  { name: "stop_service_minutes", label: "Emptying time per container", unit: "min", kind: "int", section: "routing" },
  { name: "fixed_travel_minutes", label: "Travel time per leg", unit: "min", kind: "int", section: "routing", hint: "applies to every leg incl. depot/disposal [interpretation]" },
  { name: "cost_per_truck_day_eur", label: "Truck cost", unit: "EUR/day", kind: "float", section: "routing" },
  { name: "operating_days_per_week", label: "Operating days", unit: "d/week", kind: "int", section: "routing" },
  { name: "operating_days_per_year", label: "Operating days", unit: "d/year", kind: "int", section: "routing" },
  { name: "geography_seed", label: "Bin locations: seed", unit: "seed", kind: "int", section: "routing", hint: "synthetic layout knob (0 = current layout)" },
  { name: "geography_spread_km", label: "Bin locations: spread", unit: "km", kind: "float", section: "routing", hint: "synthetic 1–spread km band" },
];

const OTHER_ROUTING_NUMBER_FIELDS: FieldSpec[] = [
  { name: "vehicle_count_available", label: "Vehicles available", unit: "vehicles", kind: "int", section: "routing" },
  ...MATERIAL_TYPES.map(
    (m): FieldSpec => ({
      name: `vehicle_compartment_volume_litres.${m}`,
      label: `Compartment (${m})`,
      unit: "L",
      kind: "int",
      section: "routing",
      defaultPath: `vehicle_compartment_volume_litres.${m}`,
      sourceKey: "vehicle_compartment_volume_litres",
      hintKey: "config.compartments.hint",
    }),
  ),
  { name: "disposal_service_minutes", label: "Disposal service time", unit: "min", kind: "int", section: "routing" },
  { name: "max_shift_minutes", label: "Max shift", unit: "min", kind: "int", section: "routing" },
  { name: "avg_speed_kmh", label: "Avg speed", unit: "km/h", kind: "float", section: "routing", hint: "haversine-derived mode only" },
  { name: "detour_factor", label: "Detour factor", unit: "× straight line", kind: "float", section: "routing" },
  { name: "solver_solution_limit", label: "Solver solution limit", unit: "solutions", kind: "int", section: "routing" },
  { name: "solver_time_limit_s", label: "Solver time limit", unit: "s", kind: "float", section: "routing", hint: "safety cap only" },
];

const ALL_NUMBER_FIELDS = [...POLICY_NUMBER_FIELDS, ...KEY_ROUTING_NUMBER_FIELDS, ...OTHER_ROUTING_NUMBER_FIELDS];

type NumberText = Record<string, string>;

const inputClass = "w-28 rounded border border-slate-300 bg-white px-2 py-1 text-sm disabled:opacity-50";

const EMPTY_NUMBER_TEXT: NumberText = {};
for (const f of ALL_NUMBER_FIELDS) {
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

/**
 * Source tag for one field from the v3 `sources` map (fail-safe via
 * `sourceLabel`: anything missing/unknown labels [demo assumption], §5.3).
 */
function SourceTag({ config, sourceKey }: { config: ConfigDefaults | null; sourceKey: string }) {
  if (sourceLabel(config, sourceKey) === "representative") return <RepresentativeTag />;
  return <AssumptionTag />;
}

export function ConfigEditor({
  config,
  lang,
  loading,
  error,
  policyOverride,
  routingOverride,
  onPolicyChange,
  onRoutingChange,
  onRecalculate,
}: {
  config: ConfigDefaults | null;
  /** UI language — only the translated compartment hint uses it. */
  lang: Lang;
  loading: boolean;
  error: string | null;
  policyOverride: PolicyConfigOverride;
  routingOverride: RoutingConfigOverride;
  onPolicyChange: (override: PolicyConfigOverride) => void;
  onRoutingChange: (override: RoutingConfigOverride) => void;
  /** Recalculate button: re-runs the auto-computed views with these overrides. */
  onRecalculate?: () => void;
}) {
  const [policyText, setPolicyText] = useState<NumberText>(EMPTY_NUMBER_TEXT);
  const [routingText, setRoutingText] = useState<NumberText>(EMPTY_NUMBER_TEXT);
  const [overfullSelect, setOverfullSelect] = useState<"" | "true" | "false">("");
  const [travelModeSelect, setTravelModeSelect] = useState<"" | TravelTimeMode>("");

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

  function pushRouting(next: NumberText, travelMode: "" | TravelTimeMode) {
    setRoutingText(next);
    setTravelModeSelect(travelMode);
    const override: RoutingConfigOverride = {};
    for (const spec of [...KEY_ROUTING_NUMBER_FIELDS, ...OTHER_ROUTING_NUMBER_FIELDS]) {
      const value = parseNumber(next[spec.name] ?? "", spec.kind);
      if (value === undefined) continue;
      if (spec.defaultPath !== undefined) {
        const child = spec.defaultPath.split(".")[1] as MaterialType;
        if (spec.defaultPath.startsWith("densities_kg_per_litre")) {
          override.densities_kg_per_litre = {
            ...override.densities_kg_per_litre,
            [child]: value,
          };
        } else {
          override.vehicle_compartment_volume_litres = {
            ...override.vehicle_compartment_volume_litres,
            [child]: value,
          };
        }
      } else {
        (override as Record<string, unknown>)[spec.name] = value;
      }
    }
    if (travelMode !== "") override.travel_time_mode = travelMode;
    onRoutingChange(override);
  }

  function reset() {
    pushPolicy({ ...EMPTY_NUMBER_TEXT }, "");
    pushRouting({ ...EMPTY_NUMBER_TEXT }, "");
  }

  const invalid: string[] = [];
  for (const spec of ALL_NUMBER_FIELDS) {
    const text = (policyText[spec.name] ?? routingText[spec.name] ?? "").trim();
    if (text !== "" && Number.isNaN(parseNumber(text, spec.kind) as number)) {
      invalid.push(`${spec.label} (${spec.unit})`);
    }
  }

  const overrideCount =
    Object.keys(policyOverride).length + Object.keys(routingOverride).length;

  return (
    <Panel
      title="Configuration (overrides)"
      subtitle={
        <>
          Defaults come from GET /api/config. Empty field = use default (no override sent). Values
          from the challenge representative are tagged <strong>[representative]</strong> (blue);
          everything else stays <strong>[demo assumption]</strong> (amber) — editing a value never
          turns it into an observed fact (§4.6/§5.3). Use <strong>Recalculate</strong> to re-run the
          auto-computed views with these overrides.
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
                lang={lang}
                disabled={loading}
                onChange={(text) => pushPolicy({ ...policyText, [spec.name]: text }, overfullSelect)}
              />
            ))}
            <FieldRow
              label="Overfull always selected"
              unit=""
              sourceTag={<SourceTag config={config} sourceKey="overfull_always_selected" />}
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

          <FieldGroup caption="Key parameters (§4.6 v3 — highlighted)" accent>
            <FieldRow
              label="Travel time mode"
              unit=""
              sourceTag={<SourceTag config={config} sourceKey="travel_time_mode" />}
              defaultValue={config?.routing?.travel_time_mode}
              renderDefault={(v) =>
                typeof v === "string" && v !== ""
                  ? v === "fixed_per_leg"
                    ? "fixed_per_leg (10 min every leg)"
                    : "haversine_derived (speed × distance)"
                  : "—"
              }
            >
              <select
                value={travelModeSelect}
                disabled={loading}
                onChange={(e) =>
                  pushRouting(routingText, e.target.value as "" | TravelTimeMode)
                }
                className={`rounded border border-slate-300 bg-white px-2 py-1 text-sm ${inputClass}`}
                data-testid="config-travel_time_mode"
              >
                <option value="">inherit default</option>
                <option value="fixed_per_leg">fixed minutes per leg</option>
                <option value="haversine_derived">derived from distance &amp; speed</option>
              </select>
            </FieldRow>
            {KEY_ROUTING_NUMBER_FIELDS.map((spec) => (
              <NumberFieldRow
                key={spec.name}
                spec={spec}
                text={routingText[spec.name] ?? ""}
                config={config}
                lang={lang}
                disabled={loading}
                onChange={(text) => pushRouting({ ...routingText, [spec.name]: text }, travelModeSelect)}
              />
            ))}
          </FieldGroup>

          <FieldGroup caption="Other routing parameters (§4.6 v3)">
            {OTHER_ROUTING_NUMBER_FIELDS.map((spec) => (
              <NumberFieldRow
                key={spec.name}
                spec={spec}
                text={routingText[spec.name] ?? ""}
                config={config}
                lang={lang}
                disabled={loading}
                onChange={(text) => pushRouting({ ...routingText, [spec.name]: text }, travelModeSelect)}
              />
            ))}
          </FieldGroup>

          {invalid.length > 0 ? (
            <p className="text-xs text-red-600" data-testid="config-invalid">
              Ignored (not valid numbers): {invalid.join(", ")}
            </p>
          ) : null}

          <div className="flex items-center justify-between gap-2">
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={reset}
                className="rounded border border-slate-300 px-3 py-1 text-xs font-medium text-slate-600 hover:bg-slate-50"
                data-testid="config-reset"
              >
                Reset to defaults
              </button>
              <button
                type="button"
                onClick={() => onRecalculate?.()}
                disabled={invalid.length > 0}
                title="Re-run the auto-computed views (overview recommendation, comparison, days-to-full) with the current overrides. Route and forecast panels re-run via their own buttons."
                className="rounded bg-sky-700 px-3 py-1 text-xs font-semibold text-white hover:bg-sky-800 disabled:opacity-50"
                data-testid="config-recalculate"
              >
                Recalculate
              </button>
            </div>
            <p className="text-xs text-slate-500" data-testid="override-count">
              Active overrides: {overrideCount}
            </p>
          </div>
        </div>
      ) : null}
    </Panel>
  );
}

function FieldGroup({
  caption,
  accent = false,
  children,
}: {
  caption: string;
  accent?: boolean;
  children: ReactNode;
}) {
  return (
    <fieldset
      className={`rounded border p-2 ${accent ? "border-sky-300 bg-sky-50/40" : "border-slate-200"}`}
    >
      <legend
        className={`px-1 text-xs font-semibold uppercase tracking-wide ${accent ? "text-sky-700" : "text-slate-500"}`}
      >
        {caption}
      </legend>
      <div className="space-y-1.5">{children}</div>
    </fieldset>
  );
}

function FieldRow({
  label,
  unit,
  sourceTag,
  defaultValue: def,
  renderDefault,
  hint,
  children,
}: {
  label: string;
  unit: string;
  sourceTag: ReactNode;
  defaultValue: unknown;
  renderDefault: (value: unknown) => string;
  hint?: string;
  children: ReactNode;
}) {
  return (
    <div className="flex flex-wrap items-center gap-2 text-xs">
      <span className="w-44 font-medium text-slate-700">{label}</span>
      {children}
      <span className="text-slate-400">
        {unit !== "" ? `(${unit}) ` : ""}default: {renderDefault(def)}
        {hint !== undefined ? <span className="text-slate-400"> — {hint}</span> : null}
      </span>
      {sourceTag}
    </div>
  );
}

function NumberFieldRow({
  spec,
  text,
  config,
  lang,
  disabled,
  onChange,
}: {
  spec: FieldSpec;
  text: string;
  config: ConfigDefaults | null;
  lang: Lang;
  disabled: boolean;
  onChange: (text: string) => void;
}) {
  const def = defaultValue(config, spec);
  const parsed = parseNumber(text, spec.kind);
  const invalidInput = text.trim() !== "" && (parsed === undefined || Number.isNaN(parsed));
  const defaultDisplay =
    spec.unit === "kg/L"
      ? formatDensity(def)
      : def === undefined
        ? "—"
        : `${def.toLocaleString("en-US")} ${spec.unit}`;
  return (
    <FieldRow
      label={spec.label}
      unit={spec.unit}
      sourceTag={<SourceTag config={config} sourceKey={spec.sourceKey ?? spec.name} />}
      defaultValue={def}
      renderDefault={() => defaultDisplay}
      hint={spec.hintKey !== undefined ? t(lang, spec.hintKey) : spec.hint}
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

