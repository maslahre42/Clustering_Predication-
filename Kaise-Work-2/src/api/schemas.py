"""Pydantic request/response schemas — docs/contracts.md §5.2 (v1, agreed for
M10; §5 shapes are the authority; JSON snake_case).

Statuses are inherited from the underlying contracts: dataset fields are
[observed] (§1.1), forecast outputs [predicted] (§2.2), and every policy/
routing default is a [demo assumption] echoed via ``ConfigDefaults
.assumption_fields`` and the ``RouteResponse.assumptions`` labels (§5.3).
"""

from __future__ import annotations

from datetime import date
from typing import Annotated, Literal

from pydantic import BaseModel, Field

Method = Literal["persistence", "rate"]
PredictedState = Literal["normal", "full", "overfull"]
ReasonCode = Literal[
    "at_or_above_threshold",
    "overfull_state",
    "below_threshold",
    "no_forecast",
]
MaterialType = Literal["brown", "green", "white"]
SolutionStatus = Literal["optimal", "feasible", "infeasible", "timeout"]
TravelTimeMode = Literal["fixed_per_leg", "haversine_derived"]

FORECAST_METHOD_DEFAULT: Method = "persistence"
HORIZON_DAYS_DEFAULT = 28  # days [demo assumption — observed median reading gap]


# --- Dataset (§5.2 DatasetSummary; validation items from §1.3/§1.4) ---------


class ValidationErrorItem(BaseModel):
    """One §1.4 rule violation (row_number: 1-based data row; 0 = header)."""

    rule_id: str
    row_number: int
    message: str
    value: str | None = None


class FillStatsResponse(BaseModel):
    """§5.2.2 FillStats — fill-level shares over ``n_rows``. These are shares
    of *readings*, never emptying events (the data records no collection
    events). Overfull rows count only in ``share_readings_overfull_pct``
    (§1.1: the token is never coerced into the numeric shares)."""

    share_readings_full_or_above_pct: float  # numeric fill >= threshold_pct, 1 d.p.
    share_readings_overfull_pct: float  # overfull rows / n_rows, 1 d.p.
    share_readings_empty_pct: float  # numeric fill == 0, 1 d.p.
    threshold_pct: int  # echoed; 80 = §3.1 PolicyConfig default [demo assumption]


class DatasetSummaryResponse(BaseModel):
    """§5.2 DatasetSummary of the active dataset (n_errors is always 0 for an
    active dataset: uploads with errors are rejected and never stored)."""

    n_rows: int
    n_locations: int
    n_series: int
    date_min: date | None
    date_max: date | None
    rows_per_material: dict[MaterialType, int]
    n_errors: int
    n_warnings: int
    source_name: str
    fill_stats: FillStatsResponse


class DatasetUploadResponse(DatasetSummaryResponse):
    """§5.1 upload response: DatasetSummary plus the full error/warning lists."""

    errors: list[ValidationErrorItem]
    warnings: list[ValidationErrorItem]


class SeriesStatusResponse(BaseModel):
    """§5.2 SeriesStatus — one series with its most recent reading."""

    location_id: str
    material_type: MaterialType
    n_readings: int
    last_date: date
    last_fill_pct: int | None  # None iff last_is_overfull (§1.1: never coerced)
    last_is_overfull: bool


# --- Config defaults (§5.2 ConfigDefaults) ----------------------------------


class PolicyDefaults(BaseModel):
    """§3.1 fields (values from ``src.collection.policy.PolicyConfig``)."""

    select_threshold_pct: int
    uncertainty_buffer_pct: int
    overfull_always_selected: bool


class RoutingDefaults(BaseModel):
    """§4.6 v3 values; vehicle fields apply to the single demo type."""

    container_volume_litres: int
    densities_kg_per_litre: dict[MaterialType, float]
    vehicle_volume_capacity_litres: int
    vehicle_weight_capacity_kg: int
    vehicle_count_available: int
    vehicle_compartment_volume_litres: dict[MaterialType, int] | None
    stop_service_minutes: int
    disposal_service_minutes: int
    max_shift_minutes: int
    travel_time_mode: TravelTimeMode
    fixed_travel_minutes: int
    cost_per_truck_day_eur: float
    operating_days_per_week: int
    operating_days_per_year: int
    geography_seed: int
    geography_spread_km: float
    avg_speed_kmh: float
    detour_factor: float
    solver_solution_limit: int
    solver_time_limit_s: float
    containers_per_series: int  # §4.2/§4.6 v4 [demo assumption — Q11]
    frequency_days: int  # §4.7/§5.2.4 cycle length [demo assumption — Q10]


class ConfigDefaultsResponse(BaseModel):
    """§5.2 ConfigDefaults: demo defaults plus the names of every field that
    is a demo assumption, the v3 per-field ``sources`` map (§4.6 v3/v4:
    "representative" vs "demo assumption" vs "literature"), and the
    architect-approved ``source_labels`` wire carrier for the verbatim
    citation strings (e.g. ``DEMO_DENSITY_SOURCE_LABEL``) the UI assumptions
    panel renders distinguishably (§6)."""

    policy: PolicyDefaults
    routing: RoutingDefaults
    assumption_fields: list[str]
    sources: dict[str, Literal["representative", "demo assumption", "literature"]]
    source_labels: dict[str, str]  # field name → verbatim source label string


# --- Forecasts (§5.2 ForecastRequest/Response; records from §2.2) ------------


class ForecastRequest(BaseModel):
    """Body of POST /api/forecasts; also the base of candidate/route requests."""

    as_of_date: date
    horizon_days: int = Field(default=HORIZON_DAYS_DEFAULT, ge=1)
    method: Method = FORECAST_METHOD_DEFAULT


class ForecastRecordResponse(BaseModel):
    """One §2.2 record (percent units, clipped to [0, 100])."""

    location_id: str
    material_type: MaterialType
    as_of_date: date
    target_date: date
    predicted_fill_pct: float
    predicted_state: PredictedState
    method: Method
    horizon_days: int


class ForecastResponse(BaseModel):
    as_of_date: date
    target_date: date
    method: Method
    forecasts: list[ForecastRecordResponse]


# --- Candidates (§5.2 CandidateRequest/SelectionResponse; §3.1/§3.3) --------


class PolicyConfigOverrides(BaseModel):
    """Partial §3.1 override; validated by constructing ``PolicyConfig``."""

    # No range constraints here on purpose: the domain constructor owns the
    # validation message that is surfaced on 422 (contract §5.3).

    select_threshold_pct: int | None = None
    uncertainty_buffer_pct: int | None = None
    overfull_always_selected: bool | None = None


class CandidateRequest(ForecastRequest):
    policy_config: PolicyConfigOverrides | None = None


class PolicyConfigEcho(BaseModel):
    """Effective §3.1 config after applying overrides (§5.3 echo rule)."""

    select_threshold_pct: int
    uncertainty_buffer_pct: int
    overfull_always_selected: bool


class CandidateResponse(BaseModel):
    """One §3.3 selected stop."""

    location_id: str
    material_type: MaterialType
    predicted_fill_pct: float
    predicted_state: PredictedState
    reason_code: ReasonCode
    detail: str


class SkipResponse(BaseModel):
    """One §3.3 skipped container with its explanation."""

    location_id: str
    material_type: MaterialType
    predicted_fill_pct: float | None
    predicted_state: PredictedState | None
    reason_code: ReasonCode
    detail: str


class SelectionResponse(BaseModel):
    """§3.3 SelectionResult (dates None iff the forecast batch is empty)."""

    as_of_date: date | None
    target_date: date | None
    config: PolicyConfigEcho
    selected: list[CandidateResponse]
    skipped: list[SkipResponse]


# --- Route (§5.2 RouteRequest/RouteResponse; §4.3 RoutingSolution) -----------


class RoutingConfigOverrides(BaseModel):
    """Partial §4.6 override; keys fixed by §5.2, applied to the single demo
    vehicle type. Validated by constructing ``RoutingConfig``/fleet schemas
    (§5.3: the domain message is surfaced on 422)."""

    container_volume_litres: int | None = None
    densities_kg_per_litre: dict[MaterialType, float] | None = None
    vehicle_volume_capacity_litres: int | None = None
    vehicle_weight_capacity_kg: int | None = None
    vehicle_count_available: int | None = None
    vehicle_compartment_volume_litres: dict[MaterialType, int] | None = None
    stop_service_minutes: int | None = None
    disposal_service_minutes: int | None = None
    max_shift_minutes: int | None = None
    travel_time_mode: TravelTimeMode | None = None
    fixed_travel_minutes: int | None = None
    cost_per_truck_day_eur: float | None = None
    operating_days_per_week: int | None = None
    operating_days_per_year: int | None = None
    geography_seed: int | None = None
    geography_spread_km: float | None = None
    containers_per_series: int | None = None  # §4.2/§4.6 v4 [demo assumption — Q11]
    frequency_days: int | None = None  # §4.7/§5.2.4 cycle length [demo assumption]
    avg_speed_kmh: float | None = None
    detour_factor: float | None = None
    solver_solution_limit: int | None = None
    solver_time_limit_s: float | None = None


class RouteRequest(CandidateRequest):
    routing_config: RoutingConfigOverrides | None = None


class DepotNode(BaseModel):
    node_type: Literal["depot"]
    id: str
    name: str
    lat: float
    lon: float


class DisposalNode(BaseModel):
    node_type: Literal["disposal"]
    id: str
    name: str
    lat: float
    lon: float
    service_minutes: int


class StopNode(BaseModel):
    node_type: Literal["stop"]
    location_id: str
    material_type: MaterialType
    lat: float
    lon: float
    container_volume_litres: int
    predicted_fill_pct: float
    service_minutes: int
    point_id: str


SequenceNode = Annotated[
    DepotNode | DisposalNode | StopNode,
    Field(discriminator="node_type"),
]


class RouteResponseItem(BaseModel):
    """One §4.3 Route: load_progression pairs are (volume_litres, weight_kg)."""

    vehicle_type_id: str
    sequence: list[SequenceNode]
    load_progression: list[tuple[int, int]]
    distance_m: int
    duration_minutes: int


class UnservedStopResponse(BaseModel):
    """§4.3 unserved entry — never silently dropped."""

    location_id: str
    material_type: MaterialType
    reason: str


class SolutionTotalsResponse(BaseModel):
    distance_m: int
    duration_min: int
    collected_volume_litres: int
    collected_volume_by_material: dict[MaterialType, int]  # litres per material (§4.3 v3)
    collected_weight_kg: int
    stops_served: int
    stops_total: int
    # §4.3 v4 [predicted] derived passthrough (solver.derive_shift_totals):
    # busiest-truck duration and stops_served / vehicles_used (1 d.p.).
    shift_minutes_used: int
    stops_per_shift: float


class FleetBasisResponse(BaseModel):
    ceil_by_volume: int
    ceil_by_weight: int


class FleetRecommendationResponse(BaseModel):
    vehicle_type_id: str
    count: int
    basis: FleetBasisResponse


class SolutionFleetCostResponse(BaseModel):
    """§4.3 v3 ``cost.fleet_cost`` — the fleet-recommendation cost
    (``trucks`` = ``fleet_recommendation.count``). All figures [predicted]
    derived from the §4.6 cost parameters, never invoiced amounts (§4.4)."""

    trucks: int
    cost_eur_per_day: float
    cost_eur_per_year: float


class SolutionCostResponse(BaseModel):
    """§4.3 v3 cost block — pure derivations: ``cost_eur_per_day =
    vehicles_used x cost_per_truck_day_eur``; ``cost_eur_per_year =
    cost_eur_per_day x operating_days_per_year``. [predicted] derived,
    never invoiced amounts (§4.4)."""

    vehicles_used: int
    cost_eur_per_day: float
    cost_eur_per_year: float
    fleet_cost: SolutionFleetCostResponse


class RoutingSolutionResponse(BaseModel):
    """§4.3 RoutingSolution; status infeasible/timeout keeps selection+solution
    with unserved reasons (§5.3). v3 adds the ``travel_time_mode`` echo and
    the derived ``cost`` block."""

    status: SolutionStatus
    objective_value: int | None
    routes: list[RouteResponseItem]
    unserved: list[UnservedStopResponse]
    totals: SolutionTotalsResponse
    fleet_recommendation: FleetRecommendationResponse
    travel_time_mode: TravelTimeMode  # echoed effective mode (§4.2/§4.3 v3)
    cost: SolutionCostResponse
    distance_provenance: str


class RouteResponse(BaseModel):
    selection: SelectionResponse
    solution: RoutingSolutionResponse
    assumptions: list[str]


# --- Comparison (§5.1 GET /api/comparison; §5.2.2 shapes, v2 2026-11-14) -----


ComparisonMethod = Literal[
    "naive_fixed_frequency",
    "naive_sweep_all",
    "naive_sweep_selected",
    "ortools",
]
"""§4.7 scenario ids, in the fixed scenarios-array order (v4: the
fixed-frequency status quo joins first)."""


class ComparisonScenarioResponse(BaseModel):
    """§5.2.2 one comparison scenario (naive area sweep or OR-Tools optimised).

    Per-stop/per-kg metrics are ``null`` on zero denominators (e.g. fleet
    exhausted before any stop) — never a fabricated 0-division value."""

    method: ComparisonMethod
    status: str  # naive: complete|incomplete; ortools: §4.3 solver status
    distance_m: int
    duration_min: int
    stops_served: int
    stops_total: int
    vehicles_available: int
    vehicles_used: int
    collected_volume_litres: int
    collected_weight_kg: int
    unserved_count: int
    recommended_trucks: int
    fleet_basis: FleetBasisResponse
    distance_per_stop_m: float | None  # distance_m / stops_served, 1 d.p.
    distance_per_kg_m: float | None  # distance_m / collected_weight_kg, 1 d.p.
    travel_time_mode: TravelTimeMode  # echoed effective mode (§4.6 v3)
    cost_eur_per_day: float  # [predicted] vehicles_used x cost_per_truck_day_eur
    cost_eur_per_year: float  # [predicted] cost_eur_per_day x operating_days_per_year


class ComparisonGainsResponse(BaseModel):
    """§4.7 gain decomposition (metres). ``routing_gain_m``/``total_gain_m``
    are ``null`` when the optimised scenario has no usable solution
    (infeasible/timeout) — a gain against 0 would be fabricated."""

    selection_gain_m: int | None  # naive_sweep_all - naive_sweep_selected
    routing_gain_m: int | None  # naive_sweep_selected - ortools (median)
    total_gain_m: int | None


class OptimisedDeterminismResponse(BaseModel):
    """§4.7 repetition protocol over ``runs`` optimised solves: ``mode`` is
    ``"identical"`` iff min == max (deterministic solution-limit stop);
    otherwise ``"median_of_runs"`` — the median is the value used in the UI
    and docs. A ``median_of_runs`` outcome means wall-clock variance was
    observed (safety cap or early exhaust), reported, never hidden."""

    runs: int
    mode: Literal["identical", "median_of_runs"]
    distance_m_median: float
    distance_m_min: int
    distance_m_max: int


class FleetBudgetResponse(BaseModel):
    """§5.2.2 ``fleet_budget`` — the ortools scenario's fleet recommendation
    priced at the §4.6 cost rates (decision ③). [predicted] derived, never
    invoiced amounts (§4.4)."""

    vehicle_type_id: str
    trucks: int
    cost_eur_per_day: float
    cost_eur_per_year: float


class ObservedAnchorResponse(BaseModel):
    """§5.2.4 ``observed_anchor`` — the status-quo service level from the
    observed emptying records (§1.5: every record is an emptying record
    [representative-stated]). Share denominator is ``n_rows`` (FillStats
    convention §5.2.2): numerator = numeric fill >= 100 + overfull records —
    never a share of numeric rows only. ``None`` values iff no records."""

    basis: Literal["observed_emptying_records"]
    share_full_or_overfull_pct: float | None
    max_fill_pct: float | None  # numeric max record; null iff none numeric


class ComparisonResponse(BaseModel):
    """§5.2.2 v2 scenario comparison with gain decomposition; fixed CLI
    defaults (as_of 2026-09-30, horizon 28, persistence) echoed. Distances
    are haversine_straight_line_derived — never called road distance.
    v3 adds the per-scenario travel_time_mode/cost fields and the
    ``fleet_budget`` block (ortools fleet recommendation x §4.6 rates)."""

    as_of_date: date
    target_date: date
    horizon_days: int
    method: Literal["persistence"]
    scenarios: list[ComparisonScenarioResponse]  # §4.7 ids, fixed order (v4: fixed_frequency first)
    gains: ComparisonGainsResponse
    optimised_determinism: OptimisedDeterminismResponse
    fleet_budget: FleetBudgetResponse
    observed_service_anchor: ObservedAnchorResponse  # v4 §4.7: service level beside cost
    distance_provenance: str
    assumptions: list[str]


# --- Days-to-full (§5.1 GET /api/days-to-full; §5.2.3 v2, 2026-11-14) --------


DaysToFullReason = Literal[
    "not_enough_records",
    "zero_interval_only",
    "no_numeric_fill",
    "zero_rate",
]


class DaysToFullSeriesResponse(BaseModel):
    """One §5.2.3 v2 per-series row. ``days_to_full``/``predicted_full_date``
    are ``None`` exactly when ``reason`` is set (no estimate is ever
    fabricated). ``predicted_full_date`` is never clamped — it may lie in
    the past ("overdue")."""

    location_id: str
    material_type: MaterialType
    last_emptying_date: date
    last_fill_pct: int | None  # None iff last_is_overfull (§1.1: never coerced)
    last_is_overfull: bool
    rate_pct_per_day: float | None  # §1.5 median fill_at_emptying / interval_days
    median_interval_days: float | None  # median consecutive interval > 0
    days_to_full: float | None  # target_pct / rate, 1 d.p.
    predicted_full_date: date | None  # last_emptying_date + round(days_to_full)
    is_lower_bound: bool  # any rate candidate >= 100 or overfull (§1.5 censored)
    reason: DaysToFullReason | None  # None iff days_to_full present


class DaysToFullStatsResponse(BaseModel):
    """Aggregate stats over series with an estimate only; nulls when none."""

    series_total: int
    series_with_estimate: int
    median_days: float | None
    mean_days: float | None
    min_days: float | None
    max_days: float | None
    lower_bound_share_pct: float | None  # % of estimates flagged is_lower_bound, 1 d.p.


class DaysToFullResponse(BaseModel):
    """§5.2.3 v2 response: [predicted] per-series days-to-full estimates from
    emptying records only (§1.5 semantics). Mandatory §1.5 caveat and model
    assumptions are echoed in ``assumptions``."""

    method: Literal["fill_at_emptying_rate"]
    target_pct: int
    stats: DaysToFullStatsResponse
    stats_by_material: dict[MaterialType, DaysToFullStatsResponse]
    series: list[DaysToFullSeriesResponse]
    assumptions: list[str]


# --- Scenarios + simulation (§5.2.4/§5.2.5 v4, 2026-11-14) -------------------


class ScenarioRequest(BaseModel):
    """Body of POST /api/scenarios — planning-lever what-if; cost AND service
    level always reported together (§5.2.4). Overrides validated by
    constructing PolicyConfig/RoutingConfig (§5.3)."""

    frequency_days: int | None = Field(default=None, ge=1)  # default 28 [demo assumption]
    simulation_days: int | None = Field(default=None, ge=1)  # default: observed window length
    policy_config: PolicyConfigOverrides | None = None
    routing_config: RoutingConfigOverrides | None = None


class SimulationRequest(ScenarioRequest):
    """Body of POST /api/simulation — §5.2.5 daily replay, same parameters."""


class ScenarioServiceBlock(BaseModel):
    """§5.2.4 simulated service level — always reported beside cost (§6).
    ``None`` shares: no active series (all) or no emptying events
    (``share_emptyings_full_or_overfull_pct``) — never fabricated."""

    basis: Literal["simulated"] = "simulated"
    overflow_share_pct: float | None  # % container-days with fill > 100, 1 d.p.
    share_emptyings_full_or_overfull_pct: float | None  # 1 d.p.
    max_fill_pct: float | None  # max end-of-day simulated fill, 1 d.p.


class SkippedSeriesResponse(BaseModel):
    """A series excluded from the replay with its §5.2.3 reason — §4.4:
    never silently dropped, never fabricated."""

    location_id: str
    material_type: MaterialType
    reason: str


class ScenarioStrategyResponse(BaseModel):
    """§5.2.4 one strategy's cost + service aggregates. Cost figures are
    [predicted] derivations (truck_days x §4.6 rate; per-year proportional),
    never invoiced amounts (§4.4)."""

    id: Literal["fixed_frequency", "demand_driven"]
    truck_days: int
    stops_total: int
    cost_eur_total: float
    cost_eur_per_year: float
    service: ScenarioServiceBlock


class SimulationConfigEcho(BaseModel):
    """Effective simulation inputs after applying overrides (§5.3 echo rule:
    every response echoes its effective config)."""

    frequency_days: int
    simulation_days: int
    select_threshold_pct: float
    container_volume_litres: int
    containers_per_series: int
    service_minutes_per_stop: int
    fixed_travel_minutes: int
    disposal_service_minutes: int
    max_shift_minutes: int
    volume_capacity_litres: int
    weight_capacity_kg: int
    density_kg_per_litre: float
    cost_per_truck_day_eur: float
    operating_days_per_year: int
    travel_time_mode: TravelTimeMode


class ScenarioResponse(BaseModel):
    """§5.2.4 response: both strategies' cost + service, the observed
    service anchor, the effective config echo and assumption labels."""

    strategies: list[ScenarioStrategyResponse]
    skipped_series: list[SkippedSeriesResponse]  # identical set for both strategies
    observed_anchor: ObservedAnchorResponse
    config_echo: SimulationConfigEcho
    assumptions: list[str]


class SimulationDayRecord(BaseModel):
    """§5.2.5 one replayed day."""

    date: date
    collections: int
    overflow_containers: int
    truck_days: int
    cumulative_cost_eur: float


class SimulationStrategyResponse(BaseModel):
    """§5.2.5 one strategy's daily replay."""

    id: Literal["fixed_frequency", "demand_driven"]
    days: list[SimulationDayRecord]


class SimulationDataBasis(BaseModel):
    """§5.2.5 data-basis vocabulary (§6; EN/DE wording is frontend work)."""

    records: Literal["observed"] = "observed"
    rates: Literal["derived"] = "derived"
    plan: Literal["simulated"] = "simulated"


class CalibrationResponse(BaseModel):
    """§5.2.5 calibration sanity-check pair (TechDetails); either side
    ``None`` iff that side has no values."""

    simulated_fill_at_emptying_median_pct: float | None
    observed_fill_at_emptying_median_pct: float | None


class SimulationResponse(BaseModel):
    """§5.2.5 response: deterministic daily replay of both strategies over
    the window; no OR-Tools, no seasonality (§5.2.5)."""

    start_date: date
    end_date: date
    data_basis: SimulationDataBasis
    strategies: list[SimulationStrategyResponse]
    calibration: CalibrationResponse
    skipped_series: list[SkippedSeriesResponse]
    config_echo: SimulationConfigEcho
    assumptions: list[str]
