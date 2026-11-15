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
    """§4.6 values; v1 applies vehicle fields to the single demo type."""

    container_volume_litres: int
    densities_kg_per_litre: dict[MaterialType, float]
    vehicle_volume_capacity_litres: int
    vehicle_weight_capacity_kg: int
    vehicle_count_available: int
    stop_service_minutes: int
    disposal_service_minutes: int
    max_shift_minutes: int
    avg_speed_kmh: float
    detour_factor: float
    solver_solution_limit: int
    solver_time_limit_s: float


class ConfigDefaultsResponse(BaseModel):
    """§5.2 ConfigDefaults: demo defaults plus the names of every field that
    is a demo assumption (policy + routing + forecast horizon)."""

    policy: PolicyDefaults
    routing: RoutingDefaults
    assumption_fields: list[str]


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
    stop_service_minutes: int | None = None
    disposal_service_minutes: int | None = None
    max_shift_minutes: int | None = None
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
    collected_weight_kg: int
    stops_served: int
    stops_total: int


class FleetBasisResponse(BaseModel):
    ceil_by_volume: int
    ceil_by_weight: int


class FleetRecommendationResponse(BaseModel):
    vehicle_type_id: str
    count: int
    basis: FleetBasisResponse


class RoutingSolutionResponse(BaseModel):
    """§4.3 RoutingSolution; status infeasible/timeout keeps selection+solution
    with unserved reasons (§5.3)."""

    status: SolutionStatus
    objective_value: int | None
    routes: list[RouteResponseItem]
    unserved: list[UnservedStopResponse]
    totals: SolutionTotalsResponse
    fleet_recommendation: FleetRecommendationResponse
    distance_provenance: str


class RouteResponse(BaseModel):
    selection: SelectionResponse
    solution: RoutingSolutionResponse
    assumptions: list[str]


# --- Comparison (§5.1 GET /api/comparison; §5.2.2 shapes, v2 2026-11-14) -----


ComparisonMethod = Literal["naive_sweep_all", "naive_sweep_selected", "ortools"]
"""§4.7 scenario ids, in the fixed scenarios-array order."""


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


class ComparisonResponse(BaseModel):
    """§5.2.2 v2 scenario comparison with gain decomposition; fixed CLI
    defaults (as_of 2026-09-30, horizon 28, persistence) echoed. Distances
    are haversine_straight_line_derived — never called road distance."""

    as_of_date: date
    target_date: date
    horizon_days: int
    method: Literal["persistence"]
    scenarios: list[ComparisonScenarioResponse]  # §4.7 ids, fixed order
    gains: ComparisonGainsResponse
    optimised_determinism: OptimisedDeterminismResponse
    distance_provenance: str
    assumptions: list[str]
