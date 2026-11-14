/**
 * Shared vitest fixtures — synthetic demo payloads mirroring docs/contracts.md
 * §5.2 shapes. Labelled synthetic; never mistaken for observed data.
 */
import type {
  ComparisonResponse,
  ComparisonScenario,
  ConfigDefaults,
  DatasetSummary,
  RouteResponse,
  SelectionResponse,
  SeriesStatus,
} from "../lib/api";

export const summaryFixture: DatasetSummary = {
  n_rows: 11701,
  n_locations: 449,
  n_series: 1338,
  date_min: "2025-01-01",
  date_max: "2026-10-31",
  rows_per_material: { brown: 3901, green: 3900, white: 3900 },
  n_errors: 0,
  n_warnings: 0,
  source_name: "glass_fill_levels_anonymized_f.csv",
};

/**
 * §5.2.2 fill_stats variant — synthetic values (no collection events in the
 * data; "full or above" means readings at/above the 80 % threshold).
 */
export const summaryWithFillStats: DatasetSummary = {
  ...summaryFixture,
  fill_stats: {
    share_readings_full_or_above_pct: 10.2,
    share_readings_overfull_pct: 10.2,
    share_readings_empty_pct: 0.4,
    threshold_pct: 80,
  },
};

export const containersFixture: SeriesStatus[] = [
  {
    location_id: "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
    material_type: "brown",
    n_readings: 26,
    last_date: "2026-10-31",
    last_fill_pct: 60,
    last_is_overfull: false,
  },
  {
    location_id: "ffff1111-2222-3333-4444-555555555555",
    material_type: "green",
    n_readings: 24,
    last_date: "2026-10-30",
    last_fill_pct: null,
    last_is_overfull: true,
  },
];

export const selectionFixture: SelectionResponse = {
  as_of_date: "2026-10-31",
  target_date: "2026-11-28",
  config: { select_threshold_pct: 80, uncertainty_buffer_pct: 0, overfull_always_selected: true },
  selected: [
    {
      location_id: "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
      material_type: "brown",
      predicted_fill_pct: 92,
      predicted_state: "full",
      reason_code: "at_or_above_threshold",
      detail: "predicted 92.0 >= threshold 80 + buffer 0",
    },
    {
      location_id: "ffff1111-2222-3333-4444-555555555555",
      material_type: "green",
      predicted_fill_pct: 100,
      predicted_state: "overfull",
      reason_code: "overfull_state",
      detail: "overfull token — state override",
    },
  ],
  skipped: [
    {
      location_id: "11111111-2222-3333-4444-555555555555",
      material_type: "white",
      predicted_fill_pct: 40,
      predicted_state: "normal",
      reason_code: "below_threshold",
      detail: "predicted 40.0 < threshold 80 + buffer 0",
    },
  ],
};

export const routeResponseFixture: RouteResponse = {
  selection: selectionFixture,
  solution: {
    status: "feasible",
    objective_value: 18400,
    routes: [
      {
        vehicle_type_id: "demo_truck",
        sequence: [
          { id: "demo_depot", name: "Demo Depot", lat: 49.14, lon: 9.22 },
          {
            location_id: "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
            material_type: "brown",
            lat: 49.15,
            lon: 9.21,
            container_volume_litres: 1900,
            predicted_fill_pct: 92,
            service_minutes: 10,
          },
          { id: "demo_disposal", name: "Demo Disposal", lat: 49.145, lon: 9.215, service_minutes: 30 },
        ],
        load_progression: [[1200, 600]],
        distance_m: 18400,
        duration_minutes: 95,
      },
    ],
    unserved: [
      {
        // Backend UnservedStopResponse is FLAT (real capture route.json).
        location_id: "11111111-2222-3333-4444-555555555555",
        material_type: "white",
        reason: "minimum round trip exceeds max_shift_minutes",
      },
    ],
    totals: {
      distance_m: 18400,
      duration_min: 95,
      collected_volume_litres: 1200,
      collected_weight_kg: 600,
      stops_served: 2,
      stops_total: 3,
    },
    fleet_recommendation: {
      vehicle_type_id: "demo_truck",
      count: 1,
      basis: { ceil_by_volume: 1, ceil_by_weight: 1 },
    },
    distance_provenance: "haversine_straight_line_derived",
  },
  assumptions: [
    "Coordinates, depot and disposal sites are synthetic [demo assumption].",
    "Distances are straight-line derived, not road distance [demo assumption].",
  ],
};

export const configFixture: ConfigDefaults = {
  policy: { select_threshold_pct: 80, uncertainty_buffer_pct: 0, overfull_always_selected: true },
  routing: {
    container_volume_litres: 1900,
    densities_kg_per_litre: { brown: 0.5, green: 0.5, white: 0.5 },
    vehicle_volume_capacity_litres: 12000,
    vehicle_weight_capacity_kg: 10000,
    vehicle_count_available: 3,
    stop_service_minutes: 10,
    disposal_service_minutes: 30,
    max_shift_minutes: 480,
    avg_speed_kmh: 30,
    detour_factor: 1.4,
    solver_time_limit_s: 5.0,
  },
  assumption_fields: [
    "select_threshold_pct",
    "uncertainty_buffer_pct",
    "overfull_always_selected",
    "container_volume_litres",
    "vehicle_volume_capacity_litres",
  ],
};

/**
 * §5.2.2 ComparisonResponse (v2) — synthetic fixture with the values observed
 * in the real 2026-11-14 live capture (frontend/src/test/fixtures/real-capture/
 * comparison.json): scenarios in the fixed §4.7 order, nullable per-metrics,
 * gains incl. the honestly-negative selection gain, determinism "identical".
 * Distances are straight-line derived, never road distance.
 */
function scenario(
  method: "naive_sweep_all" | "naive_sweep_selected" | "ortools",
  values: {
    status: string;
    distance_m: number;
    duration_min: number;
    stops_served: number;
    stops_total: number;
    collected_volume_litres: number;
    collected_weight_kg: number;
    unserved_count: number;
    recommended_trucks: number;
    fleet_basis: { ceil_by_volume: number; ceil_by_weight: number };
    distance_per_stop_m: number | null;
    distance_per_kg_m: number | null;
  },
): ComparisonScenario {
  return {
    method,
    ...values,
    vehicles_available: 3,
    vehicles_used: 3,
  };
}

export const comparisonFixture: ComparisonResponse = {
  as_of_date: "2026-09-30",
  target_date: "2026-10-28",
  horizon_days: 28,
  method: "persistence",
  scenarios: [
    scenario("naive_sweep_all", {
      status: "incomplete",
      distance_m: 230865,
      duration_min: 1389,
      stops_served: 78,
      stops_total: 1338,
      collected_volume_litres: 82270,
      collected_weight_kg: 41135,
      unserved_count: 1260,
      recommended_trucks: 116,
      fleet_basis: { ceil_by_volume: 116, ceil_by_weight: 70 },
      distance_per_stop_m: 2959.8,
      distance_per_kg_m: 5.6,
    }),
    scenario("naive_sweep_selected", {
      status: "incomplete",
      distance_m: 262995,
      duration_min: 1364,
      stops_served: 63,
      stops_total: 458,
      collected_volume_litres: 105830,
      collected_weight_kg: 52915,
      unserved_count: 395,
      recommended_trucks: 63,
      fleet_basis: { ceil_by_volume: 63, ceil_by_weight: 38 },
      distance_per_stop_m: 4174.5,
      distance_per_kg_m: 5.0,
    }),
    scenario("ortools", {
      status: "feasible",
      distance_m: 57657,
      duration_min: 546,
      stops_served: 40,
      stops_total: 458,
      collected_volume_litres: 47880,
      collected_weight_kg: 23940,
      unserved_count: 418,
      recommended_trucks: 63,
      fleet_basis: { ceil_by_volume: 63, ceil_by_weight: 38 },
      distance_per_stop_m: 1441.4,
      distance_per_kg_m: 2.4,
    }),
  ],
  gains: {
    selection_gain_m: -32130,
    routing_gain_m: 205338,
    total_gain_m: 173208,
  },
  optimised_determinism: {
    runs: 5,
    mode: "identical",
    distance_m_median: 57657.0,
    distance_m_min: 57657,
    distance_m_max: 57657,
  },
  distance_provenance: "haversine_straight_line_derived",
  assumptions: [
    "Coordinates, depot and disposal sites are synthetic [demo assumption].",
    "Distances are straight-line derived, not road distance [demo assumption].",
  ],
};

/**
 * Variant for the TechDetails median-of-runs wording (wall-clock solver
 * variance observed): synthetic spread around the observed median.
 */
export const comparisonMedianOfRunsFixture: ComparisonResponse = {
  ...comparisonFixture,
  optimised_determinism: {
    runs: 5,
    mode: "median_of_runs",
    distance_m_median: 57657.0,
    distance_m_min: 57100,
    distance_m_max: 58300,
  },
};
