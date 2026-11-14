/**
 * Display formatting with explicit units (AGENTS rule: show units on all
 * values). Dates are ISO date-only strings (§1.1) — rendered as-is, never
 * converted to another timezone.
 */

export function formatInt(value: number | null | undefined, unit: string): string {
  if (value === null || value === undefined || Number.isNaN(value)) return `— ${unit}`;
  return `${value.toLocaleString("en-US")} ${unit}`;
}

/** Distance: metres (§4.1), with a km aid for large values. */
export function formatMetres(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "— m";
  const m = `${value.toLocaleString("en-US")} m`;
  return value >= 1000 ? `${m} (${(value / 1000).toFixed(1)} km)` : m;
}

export function formatMinutes(value: number | null | undefined): string {
  return formatInt(value, "min");
}

export function formatLitres(value: number | null | undefined): string {
  return formatInt(value, "L");
}

export function formatKg(value: number | null | undefined): string {
  return formatInt(value, "kg");
}

/** Fill level: percent (§4.1), 1 decimal. */
export function formatPct(value: number | null | undefined, digits = 1): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "— %";
  return `${value.toFixed(digits)} %`;
}

/** Density: kg per litre (§4.1). */
export function formatDensity(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "— kg/L";
  return `${value.toFixed(2)} kg/L`;
}

export function formatDate(iso: string | null | undefined): string {
  return iso === null || iso === undefined || iso === "" ? "—" : iso;
}

/** Unserved entry label (backend UnservedStopResponse: flat location+material). */
export function formatStopKey(entry: { location_id: string; material_type: string }): string {
  return `${entry.location_id} · ${entry.material_type}`;
}

/** Human label for a reason_code (§3.4 enum). */
export function reasonLabel(code: string): string {
  return code.replaceAll("_", " ");
}

/** Human label for distance provenance (§4.2) — straight-line must never read as road distance. */
export function provenanceLabel(provenance: string): string {
  if (provenance === "haversine_straight_line_derived") {
    return "Distances: straight-line (haversine × detour factor) — NOT road distance";
  }
  if (provenance === "external") return "Distances: external matrix";
  return `Distances: ${provenance}`;
}
