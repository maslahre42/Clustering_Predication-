/**
 * Shared vitest fixtures — synthetic demo payloads mirroring docs/contracts.md
 * §5.2 shapes. Labelled synthetic; never mistaken for observed data.
 */
import type {
  ComparisonResponse,
  ComparisonScenario,
  ConfigDefaults,
  DaysToFullResponse,
  DatasetSummary,
  RouteResponse,
  ScenarioResponse,
  SelectionResponse,
  SeriesStatus,
  SimulationResponse,
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
          { node_type: "depot", id: "demo_depot", name: "Demo Depot", lat: 49.14, lon: 9.22 },
          {
            node_type: "stop",
            location_id: "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
            material_type: "brown",
            lat: 49.15,
            lon: 9.21,
            container_volume_litres: 1900,
            predicted_fill_pct: 92,
            service_minutes: 10,
            point_id: "stop:aaaaaaaa…:brown",
          },
          {
            node_type: "disposal",
            id: "demo_disposal",
            name: "Demo Disposal",
            lat: 49.145,
            lon: 9.215,
            service_minutes: 30,
          },
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
      collected_volume_by_material: { brown: 1200, green: 0, white: 0 },
      collected_weight_kg: 600,
      stops_served: 2,
      stops_total: 3,
    },
    fleet_recommendation: {
      vehicle_type_id: "demo_truck",
      count: 1,
      basis: { ceil_by_volume: 1, ceil_by_weight: 1 },
    },
    travel_time_mode: "fixed_per_leg",
    cost: {
      vehicles_used: 1,
      cost_eur_per_day: 500,
      cost_eur_per_year: 100000,
      fleet_cost: { trucks: 1, cost_eur_per_day: 500, cost_eur_per_year: 100000 },
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
    container_volume_litres: 3000,
    densities_kg_per_litre: { brown: 0.5, green: 0.5, white: 0.5 },
    vehicle_volume_capacity_litres: 12000,
    vehicle_weight_capacity_kg: 10000,
    vehicle_count_available: 3,
    vehicle_compartment_volume_litres: null, // absent ⇒ equal thirds (§4.2)
    stop_service_minutes: 5,
    disposal_service_minutes: 30,
    max_shift_minutes: 480,
    travel_time_mode: "fixed_per_leg",
    fixed_travel_minutes: 10,
    cost_per_truck_day_eur: 500,
    operating_days_per_week: 5,
    operating_days_per_year: 200,
    geography_seed: 0,
    geography_spread_km: 6.0,
    containers_per_series: 1, // §4.6 v4 [demo assumption — Q11]
    frequency_days: 28, // §4.7 v4 [demo assumption — Q10]
    avg_speed_kmh: 30,
    detour_factor: 1.4,
    solver_solution_limit: 200,
    solver_time_limit_s: 30.0,
  },
  assumption_fields: [
    "select_threshold_pct",
    "uncertainty_buffer_pct",
    "overfull_always_selected",
    "container_volume_litres",
    "vehicle_volume_capacity_litres",
  ],
  sources: {
    select_threshold_pct: "demo assumption",
    uncertainty_buffer_pct: "demo assumption",
    overfull_always_selected: "demo assumption",
    container_volume_litres: "representative",
    densities_kg_per_litre: "literature",
    vehicle_volume_capacity_litres: "demo assumption",
    vehicle_weight_capacity_kg: "demo assumption",
    vehicle_count_available: "demo assumption",
    vehicle_compartment_volume_litres: "demo assumption",
    stop_service_minutes: "representative",
    disposal_service_minutes: "demo assumption",
    max_shift_minutes: "representative",
    travel_time_mode: "representative",
    fixed_travel_minutes: "representative",
    cost_per_truck_day_eur: "representative",
    operating_days_per_week: "representative",
    operating_days_per_year: "representative",
    geography_seed: "demo assumption",
    geography_spread_km: "demo assumption",
    containers_per_series: "demo assumption",
    frequency_days: "demo assumption",
    avg_speed_kmh: "demo assumption",
    detour_factor: "demo assumption",
    solver_solution_limit: "demo assumption",
    solver_time_limit_s: "demo assumption",
    horizon_days: "demo assumption",
  },
  // v4 verbatim labels (real capture v4/config.json shape): [representative] /
  // [literature] / [demo assumption] stay distinguishable in the UI (§6).
  source_labels: {
    container_volume_litres: "[representative]",
    densities_kg_per_litre:
      "[literature] German AVV table AVV 20 01 02 (entsorgen-versorgen.de, retrieved 2026-11-14)",
    cost_per_truck_day_eur: "[representative]",
    frequency_days: "[demo assumption]",
    containers_per_series: "[demo assumption]",
  },
};

/**
 * §5.2.2 ComparisonResponse (v4 scenarios + v3 cost fields) — mirrors the
 * verbatim real capture (frontend/src/test/fixtures/real-capture/v4/
 * comparison.json, 2026-11-14): 4-scenario array with `naive_fixed_frequency`
 * FIRST (§4.7 status quo), then sweep_all / sweep_selected / ortools;
 * nullable per-metrics; honestly-negative selection gain; determinism
 * "identical"; per-scenario cost block; fleet budget; v4
 * `observed_service_anchor` beside cost. Distances are straight-line
 * derived, never road distance.
 */
function scenario(
  method: ComparisonScenario["method"],
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
    travel_time_mode: "fixed_per_leg",
    cost_eur_per_day: 1500, // 3 trucks in use × 500 EUR/truck-day [predicted]
    cost_eur_per_year: 300000, // × 200 operating days/year [predicted]
  };
}

export const comparisonFixture: ComparisonResponse = {
  as_of_date: "2026-09-30",
  target_date: "2026-10-28",
  horizon_days: 28,
  method: "persistence",
  scenarios: [
    scenario("naive_fixed_frequency", {
      status: "incomplete",
      distance_m: 355474,
      duration_min: 1410,
      stops_served: 60,
      stops_total: 637,
      collected_volume_litres: 84900,
      collected_weight_kg: 33960,
      unserved_count: 577,
      recommended_trucks: 183,
      fleet_basis: { ceil_by_volume: 183, ceil_by_weight: 88 },
      distance_per_stop_m: 5924.6,
      distance_per_kg_m: 10.5,
    }),
    scenario("naive_sweep_all", {
      status: "incomplete",
      distance_m: 454623,
      duration_min: 1420,
      stops_served: 50,
      stops_total: 1338,
      collected_volume_litres: 90300,
      collected_weight_kg: 36120,
      unserved_count: 1288,
      recommended_trucks: 183,
      fleet_basis: { ceil_by_volume: 183, ceil_by_weight: 88 },
      distance_per_stop_m: 9092.5,
      distance_per_kg_m: 12.6,
    }),
    scenario("naive_sweep_selected", {
      status: "incomplete",
      distance_m: 527021,
      duration_min: 1400,
      stops_served: 38,
      stops_total: 458,
      collected_volume_litres: 99900,
      collected_weight_kg: 39960,
      unserved_count: 420,
      recommended_trucks: 99,
      fleet_basis: { ceil_by_volume: 99, ceil_by_weight: 48 },
      distance_per_stop_m: 13869.0,
      distance_per_kg_m: 13.2,
    }),
    scenario("ortools", {
      status: "feasible",
      distance_m: 70175,
      duration_min: 580,
      stops_served: 34,
      stops_total: 458,
      collected_volume_litres: 45000,
      collected_weight_kg: 18000,
      unserved_count: 424,
      recommended_trucks: 99,
      fleet_basis: { ceil_by_volume: 99, ceil_by_weight: 48 },
      distance_per_stop_m: 2064.0,
      distance_per_kg_m: 3.9,
    }),
  ],
  gains: {
    selection_gain_m: -72398,
    routing_gain_m: 456846,
    total_gain_m: 384448,
  },
  optimised_determinism: {
    runs: 5,
    mode: "identical",
    distance_m_median: 70175.0,
    distance_m_min: 70175,
    distance_m_max: 70175,
  },
  fleet_budget: {
    vehicle_type_id: "demo_truck",
    trucks: 99,
    cost_eur_per_day: 49500,
    cost_eur_per_year: 9900000,
  },
  observed_service_anchor: {
    basis: "observed_emptying_records",
    share_full_or_overfull_pct: 26.9,
    max_fill_pct: 100.0,
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
    distance_m_median: 70175.0,
    distance_m_min: 69800,
    distance_m_max: 70900,
  },
};

/**
 * §5.2.3 DaysToFullResponse (v2, §1.5 semantics) — synthetic fixture
 * mirroring the verbatim real capture (frontend/src/test/fixtures/
 * real-capture/v4/days_to_full.json, 2026-11-14: real-CSV run
 * 1,303/1,338 series, median 59.3 d, target 90). All values [predicted]
 * from emptying records only; caveats are the API's own labelled
 * assumption strings (incl. the mandatory §1.5 caveat).
 */
export const daysToFullFixture: DaysToFullResponse = {
  method: "fill_at_emptying_rate",
  target_pct: 90,
  stats: {
    series_total: 1338,
    series_with_estimate: 1303,
    median_days: 59.3,
    mean_days: 101.7,
    min_days: 6.6,
    max_days: 2313.0,
    lower_bound_share_pct: 66.5,
  },
  stats_by_material: {
    brown: {
      series_total: 442,
      series_with_estimate: 422,
      median_days: 121.9,
      mean_days: 186.9,
      min_days: 22.5,
      max_days: 2313.0,
      lower_bound_share_pct: 36.3,
    },
    green: {
      series_total: 448,
      series_with_estimate: 439,
      median_days: 52.0,
      mean_days: 71.7,
      min_days: 10.2,
      max_days: 2079.0,
      lower_bound_share_pct: 73.6,
    },
    white: {
      series_total: 448,
      series_with_estimate: 442,
      median_days: 38.1,
      mean_days: 50.1,
      min_days: 6.6,
      max_days: 380.2,
      lower_bound_share_pct: 88.5,
    },
  },
  series: [
    {
      location_id: "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
      material_type: "brown",
      last_emptying_date: "2026-09-10",
      last_fill_pct: 20,
      last_is_overfull: false,
      rate_pct_per_day: 2.083333,
      median_interval_days: 34.0,
      days_to_full: 43.2,
      predicted_full_date: "2026-10-23",
      is_lower_bound: true,
      reason: null,
    },
    {
      location_id: "11111111-2222-3333-4444-555555555555",
      material_type: "white",
      last_emptying_date: "2026-09-21",
      last_fill_pct: null,
      last_is_overfull: true,
      rate_pct_per_day: null,
      median_interval_days: 28.0,
      days_to_full: null,
      predicted_full_date: null,
      is_lower_bound: true,
      reason: "no_numeric_fill",
    },
  ],
  assumptions: [
    "fill at emptying shows how full the container was when the schedule reached it — not how fast it would have filled [representative-stated §1.5]",
    "rates additionally assume no unobserved emptying between records [assumption]",
    "days_to_full assumes the container refills from 0 after each emptying [model assumption]",
    "target fill 90% [demo assumption — slide mockup]",
  ],
};

/**
 * §5.2.4 ScenarioResponse (v4) — mirrors the verbatim real capture
 * (frontend/src/test/fixtures/real-capture/v4/scenarios.json): cost AND
 * service always together (§6); demand_driven honestly costs MORE than
 * fixed_frequency while its service is better (max fill 80.0 = threshold).
 */
export const scenariosFixture: ScenarioResponse = {
  strategies: [
    {
      id: "fixed_frequency",
      truck_days: 852,
      stops_total: 15636,
      cost_eur_total: 426000.0,
      cost_eur_per_year: 244126.07,
      service: {
        basis: "simulated",
        overflow_share_pct: 2.4,
        share_emptyings_full_or_overfull_pct: 14.4,
        max_fill_pct: 366.4,
      },
    },
    {
      id: "demand_driven",
      truck_days: 1040,
      stops_total: 9993,
      cost_eur_total: 520000.0,
      cost_eur_per_year: 297994.27,
      service: {
        basis: "simulated",
        overflow_share_pct: 0.0,
        share_emptyings_full_or_overfull_pct: 0.0,
        max_fill_pct: 80.0,
      },
    },
  ],
  skipped_series: [
    {
      location_id: "bbbbbbbb-cccc-dddd-eeee-ffffffffffff",
      material_type: "brown",
      reason: "not_enough_records",
    },
  ],
  observed_anchor: {
    basis: "observed_emptying_records",
    share_full_or_overfull_pct: 26.9,
    max_fill_pct: 100.0,
  },
  config_echo: {
    frequency_days: 28,
    simulation_days: 349,
    select_threshold_pct: 80.0,
    container_volume_litres: 3000,
    containers_per_series: 1,
    service_minutes_per_stop: 5,
    fixed_travel_minutes: 10,
    disposal_service_minutes: 30,
    max_shift_minutes: 480,
    volume_capacity_litres: 12000,
    weight_capacity_kg: 10000,
    density_kg_per_litre: 0.4,
    cost_per_truck_day_eur: 500.0,
    operating_days_per_year: 200,
    travel_time_mode: "fixed_per_leg",
  },
  assumptions: [
    "simulation based on historical rates, not a prediction of reality",
    "[demo assumption] frequency_days=28 (fixed-collection-cycle length, §4.7/§5.2.4; real schedule unknown [Q10])",
  ],
};

/**
 * §5.2.5 SimulationResponse (v4) — small synthetic fixture mirroring the
 * verbatim real capture (frontend/src/test/fixtures/real-capture/v4/
 * simulation.json): daily replay, data_basis vocabulary, calibration pair.
 * The first days show the model consequence of the replay initialisation:
 * series without pre-window history start at 0 on the same day and
 * synchronise onto a few "mega-days" (labelled in the UI, §6).
 */
export const simulationFixture: SimulationResponse = {
  start_date: "2025-10-17",
  end_date: "2026-09-30",
  data_basis: { records: "observed", rates: "derived", plan: "simulated" },
  strategies: [
    {
      id: "fixed_frequency",
      days: [
        {
          date: "2025-10-17",
          collections: 0,
          overflow_containers: 0,
          truck_days: 0,
          cumulative_cost_eur: 0.0,
        },
        {
          date: "2025-11-14",
          collections: 1303,
          overflow_containers: 12,
          truck_days: 852,
          cumulative_cost_eur: 426000.0,
        },
        {
          date: "2026-09-30",
          collections: 0,
          overflow_containers: 0,
          truck_days: 0,
          cumulative_cost_eur: 426000.0,
        },
      ],
    },
    {
      id: "demand_driven",
      days: [
        {
          date: "2025-10-17",
          collections: 0,
          overflow_containers: 0,
          truck_days: 0,
          cumulative_cost_eur: 0.0,
        },
        {
          date: "2025-12-05",
          collections: 640,
          overflow_containers: 0,
          truck_days: 400,
          cumulative_cost_eur: 200000.0,
        },
      ],
    },
  ],
  calibration: {
    simulated_fill_at_emptying_median_pct: 42.5,
    observed_fill_at_emptying_median_pct: 60.0,
  },
  skipped_series: [
    {
      location_id: "bbbbbbbb-cccc-dddd-eeee-ffffffffffff",
      material_type: "brown",
      reason: "not_enough_records",
    },
  ],
  config_echo: scenariosFixture.config_echo,
  assumptions: [
    "simulation based on historical rates, not a prediction of reality",
    "per-series fill model: rate_pct_per_day x days since last emptying (container refills from 0 after each emptying; §5.2.3/§5.2.5)",
  ],
};
