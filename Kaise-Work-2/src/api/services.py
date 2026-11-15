"""M10 API orchestration — docs/contracts.md §5 (thin handlers call these).

No business logic lives here: every computation is delegated to the §1-§4
modules (``src.data.loader``, ``src.forecasting.*``, ``src.collection.policy``,
``src.routing.*``). This module only chains them, constructs the effective
configs from request overrides (validation errors propagate unchanged and are
mapped to 422 in ``src.api.main``, contract §5.3), keeps the single active
dataset in ``src.api.state``, and maps domain dataclasses to the §5.2 Pydantic
shapes.

Units per contract §4.1: litres, kilograms, metres, minutes, percent fill,
WGS84 degrees, km/h, kg/litre. Every demo value is labelled "[demo
assumption]" in responses — never presented as an observed fact.
"""

from __future__ import annotations

import statistics
import tempfile
from collections.abc import Sequence
from dataclasses import dataclass
from dataclasses import replace as dataclass_replace
from datetime import date, timedelta
from pathlib import Path
from typing import Literal, TypeVar

from src.api import hosted, schemas
from src.api.errors import ApiError, DemoDatasetMissingError
from src.api.state import store
from src.collection.policy import (
    Candidate,
    PolicyConfig,
    SelectionResult,
    Skip,
    select_candidates,
)
from src.collection.simulation import (
    SimulationConfig,
    StrategySimulation,
    simulate_strategy,
)
from src.collection.simulation import (
    calibration as simulate_calibration,
)
from src.collection.simulation import (
    observed_anchor as simulate_observed_anchor,
)
from src.data.loader import load_glass_fill_csv
from src.data.schema import (
    Dataset,
    LoadResult,
    ReadingRecord,
    ValidationError,
    ValidationWarning,
)
from src.forecasting.baseline import (
    METHOD_PERSISTENCE,
    BaselineMethod,
    ForecastRecord,
    forecast,
)
from src.forecasting.days_to_full import (
    DaysToFullStats,
    SeriesDaysToFull,
    build_days_to_full,
)
from src.forecasting.features import SeriesKey, build_feature_row, group_by_series
from src.forecasting.targets import EvaluationCase
from src.routing.demo_config import (
    DEMO_CONTAINER_VOLUME_LITRES,
    DEMO_COST_PER_TRUCK_DAY_EUR,
    DEMO_DENSITY_SOURCE_LABEL,
    DEMO_DEPOT_ID,
    DEMO_DISPOSAL_ID,
    DEMO_DISPOSAL_SERVICE_MINUTES,
    DEMO_OPERATING_DAYS_PER_YEAR,
    DEMO_STOP_SERVICE_MINUTES,
    DEMO_VEHICLE_COUNT_AVAILABLE,
    demo_depot,
    demo_disposal_site,
    demo_routing_config,
    demo_vehicle_type,
)
from src.routing.geography import (
    build_routing_problem,
    build_travel_matrix,
    synthetic_stop_coordinates,
)
from src.routing.naive import (
    SWEEP_CELL_SIZE_DEG,
    NaiveSolution,
    due_series_keys,
    naive_fixed_frequency_simulation,
    naive_sweep_simulation,
)
from src.routing.schemas import (
    Depot,
    DisposalSite,
    RoutingConfig,
    RoutingProblem,
    Stop,
    VehicleType,
    stop_point_id,
)
from src.routing.solver import Route, RoutingSolution, solve

ASSUMPTION_LABEL = "[demo assumption]"
REPRESENTATIVE_LABEL = "[representative]"

# --- Shared demo constants (§5.1/§5.2.2; single source for the M12 CLI and
# --- the API endpoints; compare_demo.py re-exports them) ---------------------

DEMO_CSV_PATH = Path("data/raw/glass_fill_levels_anonymized_f.csv")
"""POST /api/datasets/demo reads this one server-side constant path (§5.1) —
never a client-supplied value."""

COMPARISON_AS_OF_DEFAULT = date(2026, 9, 30)
"""Fixed v1 comparison default, echoed in ComparisonResponse (§5.2.2)."""

COMPARISON_HORIZON_DAYS_DEFAULT = 28  # days [demo assumption — observed median gap]

DETERMINISM_NOTE = (
    "Optimised scenario: OR-Tools stops on a fixed solution budget "
    "(solver_solution_limit) — repeated solves that reach the budget return "
    "identical totals.distance_m (contract §4.4/§4.7). The wall-clock "
    "solver_time_limit_s is a safety cap only: a run it stops before the "
    "budget is reported with status timeout and is explicitly not "
    "reproducible. The naive simulations are fully deterministic."
)

COMPARISON_RUNS = 5  # §4.7 repetition protocol [demo assumption]

_T = TypeVar("_T")


# --- Datasets (§5.1 POST /api/datasets, GET /api/summary, /api/containers) ---


def upload_dataset(content: bytes, source_name: str) -> LoadResult:
    """Validate uploaded CSV bytes via the §1 loader; store only when valid.

    The loader needs a file path, so bytes are spooled to a temporary file
    that is always removed. On validation errors the active dataset is left
    untouched (contract §5.3) and the caller reports the full error list.
    """
    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as handle:
        handle.write(content)
        temp_path = Path(handle.name)
    try:
        result = load_glass_fill_csv(temp_path)
    finally:
        temp_path.unlink(missing_ok=True)
    if not result.errors:
        store.set(result.dataset, result.warnings, source_name)
    return result


def fill_stats(readings: Sequence[ReadingRecord]) -> schemas.FillStatsResponse:
    """§5.2.2 fill-level shares over ``n_rows`` (shares of readings, not
    emptying events). Overfull rows count only in the overfull share (§1.1:
    ``fill_level_pct`` is None exactly for overfull rows, never coerced).
    The threshold echoes the §3.1 ``PolicyConfig`` default."""
    threshold = PolicyConfig().select_threshold_pct
    n_rows = len(readings)
    if n_rows == 0:
        return schemas.FillStatsResponse(
            share_readings_full_or_above_pct=0.0,
            share_readings_overfull_pct=0.0,
            share_readings_empty_pct=0.0,
            threshold_pct=threshold,
        )
    numeric_fills = [
        reading.fill_level_pct for reading in readings if reading.fill_level_pct is not None
    ]
    return schemas.FillStatsResponse(
        share_readings_full_or_above_pct=_share(
            sum(1 for fill in numeric_fills if fill >= threshold), n_rows
        ),
        share_readings_overfull_pct=_share(
            sum(1 for reading in readings if reading.is_overfull), n_rows
        ),
        share_readings_empty_pct=_share(sum(1 for fill in numeric_fills if fill == 0), n_rows),
        threshold_pct=threshold,
    )


def _share(count: int, total: int) -> float:
    """Percentage of ``total`` with 1 decimal place (§5.2.2)."""
    return round(count / total * 100, 1)


def dataset_summary() -> schemas.DatasetSummaryResponse:
    """§5.2 DatasetSummary of the active dataset (n_errors always 0)."""
    summary = store.dataset.summary
    return schemas.DatasetSummaryResponse(
        n_rows=summary.n_rows,
        n_locations=summary.n_locations,
        n_series=summary.n_series,
        date_min=summary.date_min,
        date_max=summary.date_max,
        rows_per_material=dict(summary.rows_per_material),
        n_errors=0,
        n_warnings=len(store.warnings),
        source_name=store.source_name,
        fill_stats=fill_stats(store.dataset.readings),
    )


def upload_response(result: LoadResult) -> schemas.DatasetUploadResponse:
    """Map a successful LoadResult to the §5.1 upload response shape."""
    summary = dataset_summary()
    return schemas.DatasetUploadResponse(
        **summary.model_dump(),
        errors=[validation_error_item(error) for error in result.errors],
        warnings=[validation_warning_item(warning) for warning in result.warnings],
    )


def validation_error_item(error: ValidationError) -> schemas.ValidationErrorItem:
    """Map one §1.4 error to its §5.2 wire shape (shared with POST /datasets)."""
    return schemas.ValidationErrorItem(
        rule_id=error.rule_id,
        row_number=error.row_number,
        message=error.message,
        value=error.value,
    )


def validation_warning_item(warning: ValidationWarning) -> schemas.ValidationErrorItem:
    return schemas.ValidationErrorItem(
        rule_id=warning.rule_id,
        row_number=warning.row_number,
        message=warning.message,
        value=warning.value,
    )


def load_demo_dataset() -> LoadResult:
    """POST /api/datasets/demo: validate the server-side demo CSV (§1 rules).

    The path is the single server-side constant ``DEMO_CSV_PATH`` (§5.1,
    never client-supplied); a missing file raises
    :class:`DemoDatasetMissingError` (mapped to 404 in ``main``). Validation
    behaves exactly like an upload: errors keep the active dataset unchanged
    (§5.3), success replaces it with a ``demo:``-prefixed ``source_name``.
    """
    if not DEMO_CSV_PATH.is_file():
        raise DemoDatasetMissingError(
            "Demo dataset is not available in this deployment: "
            f"{DEMO_CSV_PATH} does not exist. Upload a CSV with the same "
            "columns via POST /api/datasets, or mount the challenge CSV "
            "read-only at that path (see README 'Run with Docker') to "
            "enable the demo endpoint."
        )
    return upload_dataset(DEMO_CSV_PATH.read_bytes(), f"demo:{DEMO_CSV_PATH.name}")


def containers() -> list[schemas.SeriesStatusResponse]:
    """§5.2 SeriesStatus per series, ordered by (location_id, material_type)."""
    grouped = group_by_series(store.dataset.readings)
    statuses: list[schemas.SeriesStatusResponse] = []
    for key in sorted(grouped):
        readings = sorted(grouped[key], key=lambda reading: reading.date)
        last = readings[-1]  # dates unique within a series (invariant I1)
        statuses.append(
            schemas.SeriesStatusResponse(
                location_id=last.location_id,
                material_type=last.material_type,
                n_readings=len(readings),
                last_date=last.date,
                last_fill_pct=last.fill_level_pct,
                last_is_overfull=last.is_overfull,
            )
        )
    return statuses


# --- Config defaults (§5.1 GET /api/config) ----------------------------------

ConfigSourceLabel = Literal["representative", "demo assumption", "literature"]
"""§5.2 v3/v4 ConfigDefaults.sources value type (per-field source labels;
"literature" carries its verbatim citation in ``source_labels``)."""

ROUTING_FIELD_SOURCES: dict[str, ConfigSourceLabel] = {
    # §4.6 v3 per-field source labels: [representative] = verbal from the
    # challenge representative (14 Nov 2026); [demo assumption] = synthetic.
    "container_volume_litres": "representative",
    "densities_kg_per_litre": "literature",  # §4.6 v4: AVV 20 01 02, see DEMO_DENSITY_SOURCE_LABEL
    "vehicle_volume_capacity_litres": "demo assumption",
    "vehicle_weight_capacity_kg": "demo assumption",
    "vehicle_count_available": "demo assumption",
    "vehicle_compartment_volume_litres": "demo assumption",
    "stop_service_minutes": "representative",
    "disposal_service_minutes": "demo assumption",
    "max_shift_minutes": "representative",
    "travel_time_mode": "representative",
    "fixed_travel_minutes": "representative",
    "cost_per_truck_day_eur": "representative",
    "operating_days_per_week": "representative",
    "operating_days_per_year": "representative",
    "geography_seed": "demo assumption",
    "geography_spread_km": "demo assumption",
    "avg_speed_kmh": "demo assumption",
    "detour_factor": "demo assumption",
    "solver_solution_limit": "demo assumption",
    "solver_time_limit_s": "demo assumption",
    # §4.2/§4.6 v4 knobs (§5.2 echo; Q10/Q11 per docs/open_questions.md).
    "containers_per_series": "demo assumption",
    "frequency_days": "demo assumption",
}
POLICY_FIELD_SOURCES: dict[str, ConfigSourceLabel] = {
    name: "demo assumption" for name in schemas.PolicyDefaults.model_fields
}
FORECAST_FIELD_SOURCES: dict[str, ConfigSourceLabel] = {"horizon_days": "demo assumption"}


def config_defaults() -> schemas.ConfigDefaultsResponse:
    """§4.6 v3/§3.1 demo defaults, every demo-assumption field name, and the
    v3 ``sources`` map (§4.6 v3 / §5.2: representative vs demo assumption,
    per field). ``assumption_fields`` lists exactly the fields whose source
    is a demo assumption — representative fields are identified via
    ``sources`` so the UI never relabels them as facts."""
    policy = PolicyConfig()
    routing = demo_routing_config()
    vehicle = demo_vehicle_type()
    sources: dict[str, ConfigSourceLabel] = {
        **POLICY_FIELD_SOURCES,
        **FORECAST_FIELD_SOURCES,
        **ROUTING_FIELD_SOURCES,
    }
    if set(ROUTING_FIELD_SOURCES) != set(schemas.RoutingDefaults.model_fields):
        raise ValueError(  # pragma: no cover - guards an unlabelled v3 field
            "RoutingDefaults has fields missing from ROUTING_FIELD_SOURCES: "
            f"{sorted(set(schemas.RoutingDefaults.model_fields) - set(ROUTING_FIELD_SOURCES))}"
        )
    # Verbatim per-field source labels (§4.6 v4): the density carries the full
    # [literature] citation (DEMO_DENSITY_SOURCE_LABEL) unchanged; every other
    # field carries its §4.6 status tag from the sources map.
    source_labels: dict[str, str] = {
        name: (DEMO_DENSITY_SOURCE_LABEL if name == "densities_kg_per_litre" else f"[{source}]")
        for name, source in sources.items()
    }
    return schemas.ConfigDefaultsResponse(
        policy=schemas.PolicyDefaults(
            select_threshold_pct=policy.select_threshold_pct,
            uncertainty_buffer_pct=policy.uncertainty_buffer_pct,
            overfull_always_selected=policy.overfull_always_selected,
        ),
        routing=schemas.RoutingDefaults(
            container_volume_litres=DEMO_CONTAINER_VOLUME_LITRES,  # litres [representative §4.6 v3]
            densities_kg_per_litre=dict(routing.densities_kg_per_litre),
            vehicle_volume_capacity_litres=vehicle.volume_capacity_litres,
            vehicle_weight_capacity_kg=vehicle.weight_capacity_kg,
            vehicle_count_available=vehicle.count_available,
            vehicle_compartment_volume_litres=(
                dict(vehicle.compartment_volume_litres)
                if vehicle.compartment_volume_litres is not None
                else None
            ),
            stop_service_minutes=DEMO_STOP_SERVICE_MINUTES,
            disposal_service_minutes=DEMO_DISPOSAL_SERVICE_MINUTES,
            max_shift_minutes=routing.max_shift_minutes,
            travel_time_mode=routing.travel_time_mode,
            fixed_travel_minutes=routing.fixed_travel_minutes,
            cost_per_truck_day_eur=routing.cost_per_truck_day_eur,
            operating_days_per_week=routing.operating_days_per_week,
            operating_days_per_year=routing.operating_days_per_year,
            geography_seed=routing.geography_seed,
            geography_spread_km=routing.geography_spread_km,
            avg_speed_kmh=routing.avg_speed_kmh,
            detour_factor=routing.detour_factor,
            solver_solution_limit=routing.solver_solution_limit,
            solver_time_limit_s=routing.solver_time_limit_s,
            containers_per_series=routing.containers_per_series,
            frequency_days=routing.frequency_days,
        ),
        assumption_fields=[name for name, source in sources.items() if source == "demo assumption"],
        sources=sources,
        source_labels=source_labels,
    )


# --- Forecasts (§5.1 POST /api/forecasts) ------------------------------------


def run_forecasts(request: schemas.ForecastRequest) -> schemas.ForecastResponse:
    """Run the §2.3 baseline for every series with history at ``as_of_date``."""
    records = _forecast_batch(
        store.dataset,
        as_of=request.as_of_date,
        horizon_days=request.horizon_days,
        method=request.method,
    )
    return schemas.ForecastResponse(
        as_of_date=request.as_of_date,
        target_date=request.as_of_date + timedelta(days=request.horizon_days),
        method=request.method,
        forecasts=[_forecast_record_item(record) for record in records],
    )


def _forecast_batch(
    dataset: Dataset,
    as_of: date,
    horizon_days: int,
    method: BaselineMethod,
) -> list[ForecastRecord]:
    """One §2.2 record per series with at least one reading <= as_of.

    Inference targets (§2.1): target_date = as_of + horizon_days. Series with
    no history at as_of are omitted (they surface as `no_forecast` skips in
    the policy, §3.4); overfull-only histories yield no record (§2.3).
    """
    grouped = group_by_series(dataset.readings)
    target_date = as_of + timedelta(days=horizon_days)
    records: list[ForecastRecord] = []
    for key in sorted(grouped):
        features = build_feature_row(grouped[key], as_of)
        if features is None:
            continue
        case = EvaluationCase(
            location_id=key[0],
            material_type=key[1],
            as_of_date=as_of,
            target_date=target_date,
            horizon_days=horizon_days,
            truth_fill_pct=None,  # inference has no truth; baselines ignore it
            truth_is_overfull=False,
            features=features,
        )
        record = forecast(case, method)
        if record is not None:
            records.append(record)
    return records


def _forecast_record_item(record: ForecastRecord) -> schemas.ForecastRecordResponse:
    return schemas.ForecastRecordResponse(
        location_id=record.location_id,
        material_type=record.material_type,
        as_of_date=record.as_of_date,
        target_date=record.target_date,
        predicted_fill_pct=record.predicted_fill_pct,
        predicted_state=record.predicted_state,
        method=record.method,
        horizon_days=record.horizon_days,
    )


# --- Candidates (§5.1 POST /api/candidates) ----------------------------------


def run_candidates(request: schemas.CandidateRequest) -> schemas.SelectionResponse:
    """Forecast, then apply the §3 selection policy with the effective config."""
    records = _forecast_batch(
        store.dataset,
        as_of=request.as_of_date,
        horizon_days=request.horizon_days,
        method=request.method,
    )
    config = _effective_policy_config(request.policy_config)
    result = select_candidates(
        universe=group_by_series(store.dataset.readings).keys(),
        forecasts={(r.location_id, r.material_type): r for r in records},
        config=config,
    )
    return _selection_response(result)


def _effective_policy_config(
    overrides: schemas.PolicyConfigOverrides | None,
) -> PolicyConfig:
    """Construct PolicyConfig with the non-None overrides (§5.3 validation).

    The Pydantic override model already coerced and typed each field at the
    boundary; missing fields keep the §3.1 defaults from ``PolicyConfig``.
    """
    if overrides is None:
        return PolicyConfig()
    base = PolicyConfig()
    return PolicyConfig(
        select_threshold_pct=(
            base.select_threshold_pct
            if overrides.select_threshold_pct is None
            else overrides.select_threshold_pct
        ),
        uncertainty_buffer_pct=(
            base.uncertainty_buffer_pct
            if overrides.uncertainty_buffer_pct is None
            else overrides.uncertainty_buffer_pct
        ),
        overfull_always_selected=(
            base.overfull_always_selected
            if overrides.overfull_always_selected is None
            else overrides.overfull_always_selected
        ),
    )


def _selection_response(result: SelectionResult) -> schemas.SelectionResponse:
    return schemas.SelectionResponse(
        as_of_date=result.as_of_date,
        target_date=result.target_date,
        config=schemas.PolicyConfigEcho(
            select_threshold_pct=result.config.select_threshold_pct,
            uncertainty_buffer_pct=result.config.uncertainty_buffer_pct,
            overfull_always_selected=result.config.overfull_always_selected,
        ),
        selected=[_candidate_item(item) for item in result.selected],
        skipped=[_skip_item(item) for item in result.skipped],
    )


def _candidate_item(candidate: Candidate) -> schemas.CandidateResponse:
    return schemas.CandidateResponse(
        location_id=candidate.location_id,
        material_type=candidate.material_type,
        predicted_fill_pct=candidate.predicted_fill_pct,
        predicted_state=candidate.predicted_state,
        reason_code=candidate.reason_code,
        detail=candidate.detail,
    )


def _skip_item(skip: Skip) -> schemas.SkipResponse:
    """Map a §3.3 Skip with its explanation."""
    return schemas.SkipResponse(
        location_id=skip.location_id,
        material_type=skip.material_type,
        predicted_fill_pct=skip.predicted_fill_pct,
        predicted_state=skip.predicted_state,
        reason_code=skip.reason_code,
        detail=skip.detail,
    )


# --- Route (§5.1 POST /api/route) --------------------------------------------


def run_route(
    request: schemas.RouteRequest,
    apply_hosted_cap: bool = True,
) -> schemas.RouteResponse:
    """Full pipeline: forecast -> policy -> synthetic geography -> matrix ->
    problem -> solve. Always returns selection + solution (§5.3).

    Invalid overrides raise the domain errors (PolicyConfigError/
    RoutingSchemaError) before any solving; ``main`` maps them to 422 with
    the validation message.

    Deployment knob ``WASTECITY_MAX_STOPS`` (``src.api.hosted``) caps how
    many policy-selected candidates are handed to the solver: the first N in
    the §3.3 selection order (``selection.selected`` is already sorted that
    way). The remainder surfaces in ``solution.unserved`` with an explicit
    ``hosted_demo_stop_cap`` reason — never silently dropped (AGENTS rule 9)
    — and ``totals.stops_total`` still counts every policy-selected stop, so
    ``stops_served + len(unserved) == stops_total`` holds. Unset → no cap.

    ``apply_hosted_cap=False`` bypasses the stop cap (the interactive
    ``POST /api/route`` default stays True): the §4.7 comparison must keep
    its full basis — capping only the ortools row would make
    ``routing_gain_m`` misleading, so ``run_comparison`` calls this with the
    cap off. The ``WASTECITY_SOLVER_TIME_LIMIT_S`` override is NOT affected
    by this flag (a pure stopping-criterion safety knob, no basis effect).
    """
    policy_config = _effective_policy_config(request.policy_config)
    routing = _effective_routing(request.routing_config)

    records = _forecast_batch(
        store.dataset,
        as_of=request.as_of_date,
        horizon_days=request.horizon_days,
        method=request.method,
    )
    selection = select_candidates(
        universe=group_by_series(store.dataset.readings).keys(),
        forecasts={(r.location_id, r.material_type): r for r in records},
        config=policy_config,
    )

    # Hosted stop cap (deployment knob): deterministically keep the first N
    # of the policy-ordered selected candidates for the solver. The
    # comparison core passes apply_hosted_cap=False to stay on the full
    # §4.7 basis (see run_route docstring).
    cap = hosted.hosted_max_stops() if apply_hosted_cap else None
    solver_candidates = list(selection.selected)
    capped_out: list[Candidate] = []
    if cap is not None and cap < len(solver_candidates):
        capped_out = solver_candidates[cap:]
        solver_candidates = solver_candidates[:cap]

    depot = demo_depot()
    disposal = routing.disposal
    coordinates = synthetic_stop_coordinates(
        ((c.location_id, c.material_type) for c in solver_candidates),
        depot,
        seed=routing.config.geography_seed,
        max_radius_km=routing.config.geography_spread_km,
    )
    stops = [
        Stop(
            location_id=candidate.location_id,
            material_type=candidate.material_type,
            lat=coordinates[(candidate.location_id, candidate.material_type)][0],
            lon=coordinates[(candidate.location_id, candidate.material_type)][1],
            container_volume_litres=routing.container_volume_litres,
            predicted_fill_pct=candidate.predicted_fill_pct,
            service_minutes=routing.stop_service_minutes,
        )
        for candidate in solver_candidates
    ]
    travel = build_travel_matrix(depot, [disposal], stops, routing.config)
    problem = build_routing_problem(
        solver_candidates,
        depot,
        [disposal],
        [routing.vehicle],
        routing.container_volume_litres,
        routing.config,
        coordinates,
        travel,
        service_minutes_per_stop=routing.stop_service_minutes,
    )
    solution = solve(problem)

    solution_response = _solution_response(solution, disposal, depot)
    if capped_out:
        solution_response = _apply_hosted_stop_cap(
            solution_response, selection.selected, capped_out, cap
        )

    return schemas.RouteResponse(
        selection=_selection_response(selection),
        solution=solution_response,
        assumptions=_assumption_labels(
            request, routing, cap, len(selection.selected), len(capped_out)
        ),
    )


def _apply_hosted_stop_cap(
    solution: schemas.RoutingSolutionResponse,
    selected: Sequence[Candidate],
    capped_out: Sequence[Candidate],
    cap: int | None,
) -> schemas.RoutingSolutionResponse:
    """Surface the deployment stop cap in the response (never silently
    dropped, AGENTS rule 9): capped-out stops join ``unserved`` with an
    explicit ``hosted_demo_stop_cap`` reason and ``stops_total`` counts every
    policy-selected stop, keeping the reconcile invariant
    ``stops_served + len(unserved) == stops_total``. Merged list sorted for a
    deterministic presentation."""
    capped_unserved = [
        schemas.UnservedStopResponse(
            location_id=candidate.location_id,
            material_type=candidate.material_type,
            reason=(
                f"hosted_demo_stop_cap: deployment setting "
                f"WASTECITY_MAX_STOPS={cap} handed only the first {cap} of "
                f"{len(selected)} policy-selected stops to the solver; the "
                "policy selection itself is unchanged and shown in "
                "`selection`"
            ),
        )
        for candidate in capped_out
    ]
    merged = sorted(
        [*solution.unserved, *capped_unserved],
        key=lambda item: (item.location_id, item.material_type),
    )
    return solution.model_copy(
        update={
            "unserved": merged,
            "totals": solution.totals.model_copy(update={"stops_total": len(selected)}),
        }
    )


@dataclass(frozen=True)
class _EffectiveRouting:
    """Effective §4.6 routing inputs after applying request overrides."""

    config: RoutingConfig
    vehicle: VehicleType
    disposal: DisposalSite
    container_volume_litres: int
    stop_service_minutes: int
    solver_time_limit_from_env: bool = False
    """True when ``WASTECITY_SOLVER_TIME_LIMIT_S`` supplied the effective
    time limit (the request did not override it); drives the response label."""


def _effective_routing(
    overrides: schemas.RoutingConfigOverrides | None,
) -> _EffectiveRouting:
    """Merge §4.6 v3 defaults with overrides and validate by constructing the
    domain schemas (RoutingConfig/VehicleType/DisposalSite; §5.3 — their
    validation messages surface on 422). v3 fields (``travel_time_mode``,
    ``fixed_travel_minutes``, cost/operating rates, geography knobs,
    ``vehicle_compartment_volume_litres``) ride the same constructors: the
    sum==capacity compartment rule is VehicleType's own validation.

    The Pydantic override model already coerced each field to its declared
    type at the boundary, so only typed values reach the constructors here.

    Deployment knob ``WASTECITY_SOLVER_TIME_LIMIT_S`` (``src.api.hosted``)
    supplies the default ``solver_time_limit_s`` when the request does not
    override it; unset/invalid → the §4.6 default (byte-identical behaviour).
    """
    base_config = demo_routing_config()
    base_vehicle = demo_vehicle_type()
    base_disposal = demo_disposal_site()
    env_time_limit = hosted.hosted_solver_time_limit_s()

    def _pick(override: _T | None, base: _T) -> _T:
        """First non-None of (override, base) — the §5.3 merge rule."""
        return base if override is None else override

    def _effective_time_limit(override: float | None) -> tuple[float, bool]:
        """Effective solver_time_limit_s: request override wins, then the
        deployment env knob, then the §4.6 default; bool = from-env."""
        if override is not None:
            return override, False
        if env_time_limit is not None:
            return env_time_limit, True
        return base_config.solver_time_limit_s, False

    if overrides is None:
        time_limit_s, from_env = _effective_time_limit(None)
        if from_env:
            base_config = dataclass_replace(base_config, solver_time_limit_s=time_limit_s)
        return _EffectiveRouting(
            config=base_config,
            vehicle=base_vehicle,
            disposal=base_disposal,
            container_volume_litres=DEMO_CONTAINER_VOLUME_LITRES,
            stop_service_minutes=DEMO_STOP_SERVICE_MINUTES,
            solver_time_limit_from_env=from_env,
        )

    time_limit_s, from_env = _effective_time_limit(overrides.solver_time_limit_s)
    config = RoutingConfig(
        max_shift_minutes=_pick(overrides.max_shift_minutes, base_config.max_shift_minutes),
        densities_kg_per_litre=_pick(
            overrides.densities_kg_per_litre, dict(base_config.densities_kg_per_litre)
        ),
        detour_factor=_pick(overrides.detour_factor, base_config.detour_factor),
        avg_speed_kmh=_pick(overrides.avg_speed_kmh, base_config.avg_speed_kmh),
        solver_solution_limit=_pick(
            overrides.solver_solution_limit, base_config.solver_solution_limit
        ),
        solver_time_limit_s=time_limit_s,
        travel_time_mode=_pick(overrides.travel_time_mode, base_config.travel_time_mode),
        fixed_travel_minutes=_pick(
            overrides.fixed_travel_minutes, base_config.fixed_travel_minutes
        ),
        cost_per_truck_day_eur=_pick(
            overrides.cost_per_truck_day_eur, base_config.cost_per_truck_day_eur
        ),
        operating_days_per_week=_pick(
            overrides.operating_days_per_week, base_config.operating_days_per_week
        ),
        operating_days_per_year=_pick(
            overrides.operating_days_per_year, base_config.operating_days_per_year
        ),
        geography_seed=_pick(overrides.geography_seed, base_config.geography_seed),
        geography_spread_km=_pick(overrides.geography_spread_km, base_config.geography_spread_km),
        # §4.2/§4.6 v4 knobs (RoutingConfig constructor validates int >= 1 → 422).
        containers_per_series=_pick(
            overrides.containers_per_series, base_config.containers_per_series
        ),
        frequency_days=_pick(overrides.frequency_days, base_config.frequency_days),
    )
    vehicle = VehicleType(
        id=base_vehicle.id,
        name=base_vehicle.name,
        volume_capacity_litres=_pick(
            overrides.vehicle_volume_capacity_litres, base_vehicle.volume_capacity_litres
        ),
        weight_capacity_kg=_pick(
            overrides.vehicle_weight_capacity_kg, base_vehicle.weight_capacity_kg
        ),
        count_available=_pick(overrides.vehicle_count_available, base_vehicle.count_available),
        compartment_volume_litres=_pick(
            overrides.vehicle_compartment_volume_litres,
            base_vehicle.compartment_volume_litres,
        ),
    )
    disposal = DisposalSite(
        id=base_disposal.id,
        name=base_disposal.name,
        lat=base_disposal.lat,
        lon=base_disposal.lon,
        service_minutes=_pick(overrides.disposal_service_minutes, base_disposal.service_minutes),
    )
    return _EffectiveRouting(
        config=config,
        vehicle=vehicle,
        disposal=disposal,
        container_volume_litres=_pick(
            overrides.container_volume_litres, DEMO_CONTAINER_VOLUME_LITRES
        ),
        stop_service_minutes=_pick(overrides.stop_service_minutes, DEMO_STOP_SERVICE_MINUTES),
        solver_time_limit_from_env=from_env,
    )


def _solution_response(
    solution: RoutingSolution,
    disposal: DisposalSite,
    depot: Depot,
) -> schemas.RoutingSolutionResponse:
    return schemas.RoutingSolutionResponse(
        status=solution.status,
        objective_value=solution.objective_value,
        routes=[_route_item(route, disposal, depot) for route in solution.routes],
        unserved=[
            schemas.UnservedStopResponse(
                location_id=stop.stop_key[0],
                material_type=stop.stop_key[1],
                reason=stop.reason,
            )
            for stop in solution.unserved
        ],
        totals=schemas.SolutionTotalsResponse(
            distance_m=solution.totals.distance_m,
            duration_min=solution.totals.duration_min,
            collected_volume_litres=solution.totals.collected_volume_litres,
            collected_volume_by_material=dict(solution.totals.collected_volume_by_material),
            collected_weight_kg=solution.totals.collected_weight_kg,
            stops_served=solution.totals.stops_served,
            stops_total=solution.totals.stops_total,
            # §4.3 v4 [predicted] derived passthrough (solver.derive_shift_totals).
            shift_minutes_used=solution.totals.shift_minutes_used,
            stops_per_shift=solution.totals.stops_per_shift,
        ),
        fleet_recommendation=schemas.FleetRecommendationResponse(
            vehicle_type_id=solution.fleet_recommendation.vehicle_type_id,
            count=solution.fleet_recommendation.count,
            basis=schemas.FleetBasisResponse(
                ceil_by_volume=solution.fleet_recommendation.basis.ceil_by_volume,
                ceil_by_weight=solution.fleet_recommendation.basis.ceil_by_weight,
            ),
        ),
        travel_time_mode=solution.travel_time_mode,
        cost=schemas.SolutionCostResponse(
            vehicles_used=solution.cost.vehicles_used,
            cost_eur_per_day=solution.cost.cost_eur_per_day,
            cost_eur_per_year=solution.cost.cost_eur_per_year,
            fleet_cost=schemas.SolutionFleetCostResponse(
                trucks=solution.cost.fleet_cost.trucks,
                cost_eur_per_day=solution.cost.fleet_cost.cost_eur_per_day,
                cost_eur_per_year=solution.cost.fleet_cost.cost_eur_per_year,
            ),
        ),
        distance_provenance=solution.distance_provenance,
    )


def _route_item(
    route: Route,
    disposal: DisposalSite,
    depot: Depot,
) -> schemas.RouteResponseItem:
    nodes: list[schemas.SequenceNode] = []
    for node in route.sequence:
        if isinstance(node, Stop):
            nodes.append(
                schemas.StopNode(
                    node_type="stop",
                    location_id=node.location_id,
                    material_type=node.material_type,
                    lat=node.lat,
                    lon=node.lon,
                    container_volume_litres=node.container_volume_litres,
                    predicted_fill_pct=node.predicted_fill_pct,
                    service_minutes=node.service_minutes,
                    point_id=stop_point_id(node),
                )
            )
        elif isinstance(node, DisposalSite):
            nodes.append(
                schemas.DisposalNode(
                    node_type="disposal",
                    id=node.id,
                    name=node.name,
                    lat=node.lat,
                    lon=node.lon,
                    service_minutes=node.service_minutes,
                )
            )
        else:
            nodes.append(
                schemas.DepotNode(
                    node_type="depot",
                    id=depot.id,
                    name=depot.name,
                    lat=node.lat,
                    lon=node.lon,
                )
            )
    return schemas.RouteResponseItem(
        vehicle_type_id=route.vehicle_type_id,
        sequence=nodes,
        load_progression=route.load_progression,
        distance_m=route.distance_m,
        duration_minutes=route.duration_minutes,
    )


def _assumption_labels(
    request: schemas.RouteRequest,
    routing: _EffectiveRouting,
    cap: int | None,
    n_selected: int,
    n_capped_out: int,
) -> list[str]:
    """Labelled assumption strings for the §5.2 RouteResponse (§5.3), with the
    §4.6 v3 per-value sources: [representative] (verbal from the challenge
    representative, 14 Nov 2026) vs [demo assumption] (synthetic).

    Deployment knobs (``src.api.hosted``) get explicit "[deployment setting]"
    labels — they are not demo assumptions about the challenge. The stop-cap
    label appears only when the cap actually reduced the solver hand-off
    (``n_capped_out > 0``); with both env vars unset the label list is
    unchanged from the pre-knob contract.
    """
    config = routing.config
    labels = [
        f"{ASSUMPTION_LABEL} forecast horizon_days={request.horizon_days} "
        "(brief defines no horizon; default is the observed median reading gap)",
        f"{ASSUMPTION_LABEL} synthetic stop coordinates derived from SHA-256 of "
        "series keys — no real coordinates exist in the data; distances are "
        "haversine_straight_line_derived, not road distance",
        f"{ASSUMPTION_LABEL} synthetic depot '{DEMO_DEPOT_ID}' and disposal site "
        f"'{DEMO_DISPOSAL_ID}' near Heilbronn",
        f"{REPRESENTATIVE_LABEL} container_volume_litres={routing.container_volume_litres}",
        f"{DEMO_DENSITY_SOURCE_LABEL} densities_kg_per_litre="  # §4.6 v4 verbatim label
        + ", ".join(
            f"{material}={density}" for material, density in config.densities_kg_per_litre.items()
        )
        + " kg/litre",
        f"{ASSUMPTION_LABEL} vehicle '{routing.vehicle.id}': "
        f"{routing.vehicle.volume_capacity_litres} L / "
        f"{routing.vehicle.weight_capacity_kg} kg x "
        f"{routing.vehicle.count_available} available",
        f"{REPRESENTATIVE_LABEL} stop_service_minutes={routing.stop_service_minutes}, "
        f"{ASSUMPTION_LABEL} disposal_service_minutes={routing.disposal.service_minutes}",
        f"{REPRESENTATIVE_LABEL} max_shift_minutes={config.max_shift_minutes}",
        f"{REPRESENTATIVE_LABEL} travel_time_mode={config.travel_time_mode}"
        + (
            f", fixed_travel_minutes={config.fixed_travel_minutes} on every leg "
            "incl. depot/disposal [interpretation — open question]"
            if config.travel_time_mode == "fixed_per_leg"
            else f", avg_speed_kmh={config.avg_speed_kmh}, "
            f"detour_factor={config.detour_factor} (matrix derivation "
            f"[demo assumption])"
        ),
        f"{REPRESENTATIVE_LABEL} cost_per_truck_day_eur={config.cost_per_truck_day_eur:g}, "
        f"operating_days_per_week={config.operating_days_per_week}, "
        f"operating_days_per_year={config.operating_days_per_year} (cost figures "
        "derived from them are [predicted], never invoiced amounts)",
        f"{ASSUMPTION_LABEL} geography_seed={config.geography_seed}, "
        f"geography_spread_km={config.geography_spread_km:g} km (synthetic-layout "
        "sensitivity knobs; defaults reproduce the current coordinates)",
        f"{ASSUMPTION_LABEL} solver_solution_limit={config.solver_solution_limit} "
        "(primary stopping criterion, deterministic; §4.7)",
        # §4.2/§4.6 v4 knobs — effective values echoed per §5.3.
        f"{ASSUMPTION_LABEL} containers_per_series={config.containers_per_series} "
        "(multiplies litres collected and stop service minutes; the predicted "
        "fill % is the series aggregate and does NOT change — Q11), "
        f"frequency_days={config.frequency_days} "
        "(fixed-collection-cycle length, §4.7/§5.2.4; real schedule unknown "
        "[open question Q10])",
    ]
    if routing.solver_time_limit_from_env:
        labels.append(
            "[deployment setting] solver_time_limit_s="
            f"{config.solver_time_limit_s} via WASTECITY_SOLVER_TIME_LIMIT_S "
            "(hosted deployment knob; an explicit request override still "
            "wins; not a demo assumption about the challenge)"
        )
    else:
        labels.append(
            f"{ASSUMPTION_LABEL} solver_time_limit_s={config.solver_time_limit_s} "
            "(safety cap only; fires ⇒ status timeout, run not reproducible; §4.7)"
        )
    if n_capped_out > 0:
        labels.append(
            "[deployment setting] WASTECITY_MAX_STOPS: solver received the "
            f"first {n_selected - n_capped_out} of {n_selected} "
            "policy-selected stops (§3.3 order preserved); the remainder is "
            "listed in `unserved` with reason hosted_demo_stop_cap; "
            "deployment knob, not a demo assumption about the challenge"
        )
    return labels


# --- Days-to-full (§5.1 GET /api/days-to-full; §5.2.3 v2, 2026-11-14) --------


def days_to_full() -> schemas.DaysToFullResponse:
    """§5.2.3 v2 days-to-full estimates for every series of the active
    dataset, computed by ``src.forecasting.days_to_full`` (§2/§5 modules only
    — no business logic here). [predicted] from emptying records only
    (§1.5); the mandatory §1.5 caveat and model assumptions are echoed in
    ``assumptions``. 404 on no dataset is the shared ``NoDatasetError``
    mapping (``store.dataset`` raises it)."""
    result = build_days_to_full(store.dataset)
    return schemas.DaysToFullResponse(
        method=result.method,
        target_pct=result.target_pct,
        stats=_days_to_full_stats(result.stats),
        stats_by_material={
            material: _days_to_full_stats(stats)
            for material, stats in result.stats_by_material.items()
        },
        series=[
            schemas.DaysToFullSeriesResponse(
                location_id=row.location_id,
                material_type=row.material_type,
                last_emptying_date=row.last_emptying_date,
                last_fill_pct=row.last_fill_pct,
                last_is_overfull=row.last_is_overfull,
                rate_pct_per_day=row.rate_pct_per_day,
                median_interval_days=row.median_interval_days,
                days_to_full=row.days_to_full,
                predicted_full_date=row.predicted_full_date,
                is_lower_bound=row.is_lower_bound,
                reason=row.reason,
            )
            for row in result.series
        ],
        assumptions=list(result.assumptions),
    )


def _days_to_full_stats(stats: DaysToFullStats) -> schemas.DaysToFullStatsResponse:
    """Map one §5.2.3 stats block (shared by overall and per-material)."""
    return schemas.DaysToFullStatsResponse(
        series_total=stats.series_total,
        series_with_estimate=stats.series_with_estimate,
        median_days=stats.median_days,
        mean_days=stats.mean_days,
        min_days=stats.min_days,
        max_days=stats.max_days,
        lower_bound_share_pct=stats.lower_bound_share_pct,
    )


# --- Comparison (§5.1 GET /api/comparison; §5.2.2; shared with the M12 CLI) --


@dataclass(frozen=True)
class ComparisonRun:
    """Everything the §5.2.2 v2/v4 ComparisonResponse and the M12 CLI markdown
    are built from — ONE shared core (CLI + endpoint, §5.2.2)."""

    as_of_date: date
    target_date: date
    horizon_days: int
    fixed_frequency: NaiveSolution  # §4.7 v4 status quo (due series only)
    sweep_all: NaiveSolution
    sweep_selected: NaiveSolution
    optimised_median: schemas.RouteResponse  # run whose distance is the median
    scenarios: list[schemas.ComparisonScenarioResponse]
    gains: schemas.ComparisonGainsResponse
    optimised_determinism: schemas.OptimisedDeterminismResponse
    fleet_budget: schemas.FleetBudgetResponse
    observed_anchor: schemas.ObservedAnchorResponse  # v4 §4.7 service anchor
    distance_provenance: str
    assumptions: list[str]


def _forecast_fills(
    dataset: Dataset, as_of: date, horizon_days: int
) -> tuple[dict[SeriesKey, float], list[SeriesKey]]:
    """Persistence fills (§2.3) for every series — mirrors the ``run_route``
    forecast step exactly (leakage-safe features at as_of); series without a
    persistence value keep fill 0.0 and are listed in ``no_forecast_keys`` so
    the simulations can label them (never fabricated)."""
    grouped = group_by_series(dataset.readings)
    target_date = as_of + timedelta(days=horizon_days)
    fills: dict[SeriesKey, float] = {}
    no_forecast_keys: list[SeriesKey] = []
    for key in sorted(grouped):
        features = build_feature_row(grouped[key], as_of)
        record: ForecastRecord | None = None
        if features is not None:
            evaluation_case = EvaluationCase(
                location_id=key[0],
                material_type=key[1],
                as_of_date=as_of,
                target_date=target_date,
                horizon_days=horizon_days,
                truth_fill_pct=None,  # inference has no truth; baselines ignore it
                truth_is_overfull=False,
                features=features,
            )
            record = forecast(evaluation_case, METHOD_PERSISTENCE)
        if record is None:
            no_forecast_keys.append(key)
            fills[key] = 0.0
        else:
            fills[key] = record.predicted_fill_pct
    return fills, no_forecast_keys


def _problem_for_keys(
    fills: dict[SeriesKey, float],
    no_forecast_keys: Sequence[SeriesKey],
    keys: Sequence[SeriesKey],
) -> tuple[RoutingProblem, list[SeriesKey]]:
    """Build the §4.6 demo routing problem over exactly ``keys`` (all series
    for ``naive_sweep_all``, policy-selected only for ``naive_sweep_selected``).
    Same demo depot/disposal/vehicle/config values and the same synthetic
    coordinate derivation as the optimised pipeline — one labelled demo
    physics across scenarios (§4.7). Returns the no-forecast keys within
    ``keys`` for the zero-fill labelling."""
    depot = demo_depot()
    disposal = demo_disposal_site()
    vehicle = demo_vehicle_type()
    config = demo_routing_config()
    coordinates = synthetic_stop_coordinates(fills.keys(), depot)
    stops = [
        Stop(
            location_id=key[0],
            material_type=key[1],
            lat=coordinates[key][0],
            lon=coordinates[key][1],
            container_volume_litres=DEMO_CONTAINER_VOLUME_LITRES,
            predicted_fill_pct=fills[key],
            service_minutes=DEMO_STOP_SERVICE_MINUTES,
        )
        for key in sorted(keys)
    ]
    travel = build_travel_matrix(depot, [disposal], stops, config)
    problem = RoutingProblem(
        depot=depot,
        disposal_sites=[disposal],
        stops=stops,
        vehicle_types=[vehicle],
        travel=travel,
        config=config,
    )
    no_forecast_set = set(no_forecast_keys)
    return problem, [key for key in sorted(keys) if key in no_forecast_set]


def run_comparison(
    dataset: Dataset,
    as_of: date,
    horizon_days: int,
    runs: int = COMPARISON_RUNS,
) -> ComparisonRun:
    """Shared comparison core (M12 CLI ``compare_demo`` and GET
    /api/comparison) per contract §4.7 v2/v4: four scenarios in fixed order
    (``naive_fixed_frequency`` status quo, ``naive_sweep_all``,
    ``naive_sweep_selected``, ``ortools``), gain decomposition over the last
    three, the §4.7 repetition protocol (``runs`` optimised solves; the
    median run is the value used in UI and docs), and the observed service
    anchor beside every cost (§4.7 v4).

    ``dataset`` must be the active store dataset (the CLI uploads it first;
    the endpoint has it loaded) because ``run_route`` reads the store.

    The ``WASTECITY_MAX_STOPS`` deployment knob does NOT apply here (full
    §4.7 basis on every scenario); ``WASTECITY_SOLVER_TIME_LIMIT_S`` does
    (stopping-criterion safety only). See ``run_route``.
    """
    if runs < 1:
        raise ValueError(f"runs must be >= 1, got {runs}")

    # Optimised scenario: the unchanged M10 ``run_route`` pipeline, solved
    # ``runs`` times for the §4.7 repetition protocol. The run whose distance
    # is the median carries the whole ``ortools`` row (self-consistent row;
    # its distance IS the §4.7 median for the odd default runs=5).
    # ``apply_hosted_cap=False``: the comparison stays on the FULL policy
    # selection (§4.7 basis) even when the ``WASTECITY_MAX_STOPS`` deployment
    # knob caps the interactive route demo — capping only this row would make
    # ``routing_gain_m`` a misleading mixed-basis number. The time-limit env
    # override stays applied (pure stopping-criterion safety, no basis
    # effect); README "Run with Docker" documents the same.
    optimised_runs = [
        run_route(
            schemas.RouteRequest(
                as_of_date=as_of,
                horizon_days=horizon_days,
                method=METHOD_PERSISTENCE,
            ),
            apply_hosted_cap=False,
        )
        for _ in range(runs)
    ]
    optimised_median = sorted(
        optimised_runs, key=lambda response: response.solution.totals.distance_m
    )[runs // 2]

    # Naive scenarios: identical simulation physics, area-sweep order (§4.7).
    fills, no_forecast_keys = _forecast_fills(dataset, as_of, horizon_days)
    all_keys = sorted(fills)
    selected_keys = sorted(
        (candidate.location_id, candidate.material_type)
        for candidate in optimised_median.selection.selected
    )
    problem_all, no_forecast_all = _problem_for_keys(fills, no_forecast_keys, all_keys)
    sweep_all = naive_sweep_simulation(problem_all, no_forecast_all)
    problem_selected, no_forecast_selected = _problem_for_keys(
        fills, no_forecast_keys, selected_keys
    )
    sweep_selected = naive_sweep_simulation(problem_selected, no_forecast_selected)

    # §4.7 v4 status quo: only series DUE under the fixed k-day cycle
    # (as_of - last_emptying_date >= frequency_days; no last date ⇒ due).
    # The last emptying date known at as_of is the latest record date <= as_of
    # (leakage rule 6: no information after the prediction date). frequency_days
    # resolves to problem_all.config.frequency_days (§4.6 default 28) — one
    # source of truth, shared with the simulation via due_series_keys.
    grouped = group_by_series(dataset.readings)
    last_emptying_dates: dict[SeriesKey, date | None] = {
        key: max((reading.date for reading in readings if reading.date <= as_of), default=None)
        for key, readings in grouped.items()
    }
    due = due_series_keys(last_emptying_dates, as_of, problem_all.config.frequency_days)
    fixed_frequency = naive_fixed_frequency_simulation(
        problem_all,
        last_emptying_dates,
        as_of,
        no_forecast_stop_keys=[key for key in no_forecast_all if key in due],
    )

    scenarios = [
        _naive_scenario_row("naive_fixed_frequency", fixed_frequency),
        _naive_scenario_row("naive_sweep_all", sweep_all),
        _naive_scenario_row("naive_sweep_selected", sweep_selected),
        _ortools_scenario_row(optimised_median),
    ]
    gains = _comparison_gains(scenarios, optimised_median)
    determinism = _optimised_determinism(optimised_runs)

    return ComparisonRun(
        as_of_date=as_of,
        target_date=as_of + timedelta(days=horizon_days),
        horizon_days=horizon_days,
        fixed_frequency=fixed_frequency,
        sweep_all=sweep_all,
        sweep_selected=sweep_selected,
        optimised_median=optimised_median,
        scenarios=scenarios,
        gains=gains,
        optimised_determinism=determinism,
        fleet_budget=_fleet_budget(optimised_median),
        observed_anchor=_observed_service_anchor(dataset),
        distance_provenance=optimised_median.solution.distance_provenance,
        assumptions=_comparison_assumptions(optimised_median, len(due)),
    )


def _fleet_budget(optimised: schemas.RouteResponse) -> schemas.FleetBudgetResponse:
    """§5.2.2 ``fleet_budget`` — the ortools scenario's fleet recommendation
    priced at the §4.6 v3 rates (decision ③): ``trucks`` =
    ``fleet_recommendation.count``; per-day = trucks x
    ``cost_per_truck_day_eur``; per-year = per-day x ``operating_days_per_year``
    (the solver's ``cost.fleet_cost`` block, which derives exactly this)."""
    solution = optimised.solution
    return schemas.FleetBudgetResponse(
        vehicle_type_id=solution.fleet_recommendation.vehicle_type_id,
        trucks=solution.fleet_recommendation.count,
        cost_eur_per_day=solution.cost.fleet_cost.cost_eur_per_day,
        cost_eur_per_year=solution.cost.fleet_cost.cost_eur_per_year,
    )


def _ratio_1dp(distance_m: int, denominator: int) -> float | None:
    """§5.2.2 per-stop/per-kg metric at 1 d.p.; ``None`` on a zero
    denominator (e.g. fleet exhausted before any stop) — never a fabricated
    0-division value."""
    if denominator == 0:
        return None
    return round(distance_m / denominator, 1)


def _cost_eur_per_day_and_year(vehicles_used: int) -> tuple[float, float]:
    """§4.6 v3 derived cost: ``vehicles_used x cost_per_truck_day_eur``, then
    ``x operating_days_per_year``. [predicted] derived, never invoiced."""
    cost_per_day = vehicles_used * DEMO_COST_PER_TRUCK_DAY_EUR
    return cost_per_day, cost_per_day * DEMO_OPERATING_DAYS_PER_YEAR


def _naive_scenario_row(
    method: schemas.ComparisonMethod, naive: NaiveSolution
) -> schemas.ComparisonScenarioResponse:
    config = demo_routing_config()  # §4.6 v3 cost rates + mode echo
    cost_per_day, cost_per_year = _cost_eur_per_day_and_year(len(naive.routes))
    return schemas.ComparisonScenarioResponse(
        method=method,
        status=naive.status,
        distance_m=naive.totals.distance_m,
        duration_min=naive.totals.duration_min,
        stops_served=naive.totals.stops_served,
        stops_total=naive.totals.stops_total,
        vehicles_available=DEMO_VEHICLE_COUNT_AVAILABLE,
        vehicles_used=len(naive.routes),
        collected_volume_litres=naive.totals.collected_volume_litres,
        collected_weight_kg=naive.totals.collected_weight_kg,
        unserved_count=len(naive.unserved),
        recommended_trucks=naive.fleet_recommendation.count,
        fleet_basis=schemas.FleetBasisResponse(
            ceil_by_volume=naive.fleet_recommendation.basis.ceil_by_volume,
            ceil_by_weight=naive.fleet_recommendation.basis.ceil_by_weight,
        ),
        distance_per_stop_m=_ratio_1dp(naive.totals.distance_m, naive.totals.stops_served),
        distance_per_kg_m=_ratio_1dp(naive.totals.distance_m, naive.totals.collected_weight_kg),
        travel_time_mode=config.travel_time_mode,
        cost_eur_per_day=cost_per_day,
        cost_eur_per_year=cost_per_year,
    )


def _ortools_scenario_row(
    optimised: schemas.RouteResponse,
) -> schemas.ComparisonScenarioResponse:
    solution = optimised.solution
    return schemas.ComparisonScenarioResponse(
        method="ortools",
        status=solution.status,
        distance_m=solution.totals.distance_m,
        duration_min=solution.totals.duration_min,
        stops_served=solution.totals.stops_served,
        stops_total=solution.totals.stops_total,
        vehicles_available=DEMO_VEHICLE_COUNT_AVAILABLE,
        vehicles_used=len(solution.routes),
        collected_volume_litres=solution.totals.collected_volume_litres,
        collected_weight_kg=solution.totals.collected_weight_kg,
        unserved_count=len(solution.unserved),
        recommended_trucks=solution.fleet_recommendation.count,
        fleet_basis=solution.fleet_recommendation.basis.model_copy(),
        distance_per_stop_m=_ratio_1dp(solution.totals.distance_m, solution.totals.stops_served),
        distance_per_kg_m=_ratio_1dp(
            solution.totals.distance_m, solution.totals.collected_weight_kg
        ),
        travel_time_mode=solution.travel_time_mode,
        cost_eur_per_day=solution.cost.cost_eur_per_day,
        cost_eur_per_year=solution.cost.cost_eur_per_year,
    )


def _comparison_gains(
    scenarios: list[schemas.ComparisonScenarioResponse], optimised: schemas.RouteResponse
) -> schemas.ComparisonGainsResponse:
    """§4.7 gain decomposition in metres over the three gain-relevant
    scenarios (fixed_frequency is the status quo and carries no gain).
    ``routing_gain_m``/``total_gain_m`` are ``None`` when the optimised
    scenario has no usable solution (infeasible/timeout): a gain against 0
    would be fabricated, §5.2.2."""
    _, sweep_all, sweep_selected, optimised_row = scenarios
    selection_gain = sweep_all.distance_m - sweep_selected.distance_m
    usable = optimised.solution.status in ("optimal", "feasible")
    routing_gain = sweep_selected.distance_m - optimised_row.distance_m if usable else None
    total_gain = selection_gain + routing_gain if routing_gain is not None else None
    return schemas.ComparisonGainsResponse(
        selection_gain_m=selection_gain,
        routing_gain_m=routing_gain,
        total_gain_m=total_gain,
    )


def _optimised_determinism(
    optimised_runs: list[schemas.RouteResponse],
) -> schemas.OptimisedDeterminismResponse:
    """§4.7 repetition protocol: ``mode`` is ``"identical"`` iff min == max
    (deterministic solution-limit stop); otherwise ``"median_of_runs"`` —
    wall-clock variance was observed, reported, never hidden."""
    distances = sorted(response.solution.totals.distance_m for response in optimised_runs)
    minimum, maximum = distances[0], distances[-1]
    return schemas.OptimisedDeterminismResponse(
        runs=len(optimised_runs),
        mode="identical" if minimum == maximum else "median_of_runs",
        distance_m_median=float(statistics.median(distances)),
        distance_m_min=minimum,
        distance_m_max=maximum,
    )


def _observed_service_anchor(dataset: Dataset) -> schemas.ObservedAnchorResponse:
    """§4.7 v4/§5.2.4 ``observed_service_anchor`` from the ACTIVE dataset
    records: numerator = numeric fill >= 100 + overfull records, denominator
    = n_rows (FillStats convention §5.2.2). Computed by
    ``src.collection.simulation.observed_anchor`` — the §2/§5 module owns the
    arithmetic (no business logic in the API layer)."""
    anchor = simulate_observed_anchor(dataset.readings)
    return schemas.ObservedAnchorResponse(
        basis=anchor.basis,
        share_full_or_overfull_pct=anchor.share_full_or_overfull_pct,
        max_fill_pct=anchor.max_fill_pct,
    )


def comparison() -> schemas.ComparisonResponse:
    """§5.2.2 v2/v4 ComparisonResponse on the active dataset with the fixed
    defaults echoed (as_of 2026-09-30, horizon 28, persistence)."""
    run = run_comparison(
        store.dataset,
        COMPARISON_AS_OF_DEFAULT,
        COMPARISON_HORIZON_DAYS_DEFAULT,
    )
    return schemas.ComparisonResponse(
        as_of_date=run.as_of_date,
        target_date=run.target_date,
        horizon_days=run.horizon_days,
        method=METHOD_PERSISTENCE,
        scenarios=run.scenarios,
        gains=run.gains,
        optimised_determinism=run.optimised_determinism,
        fleet_budget=run.fleet_budget,
        observed_service_anchor=run.observed_anchor,
        distance_provenance=run.distance_provenance,
        assumptions=run.assumptions,
    )


def _comparison_assumptions(optimised: schemas.RouteResponse, n_due: int) -> list[str]:
    """§5.2.2 assumption labels: the optimised pipeline labels plus the naive
    area-sweep order/zero-fill rules, the §4.7 v4 fixed-frequency due rule
    and the determinism protocol note."""
    return [
        *optimised.assumptions,
        f"{ASSUMPTION_LABEL} naive_fixed_frequency status quo: a series is due "
        "iff as_of - last_emptying_date >= frequency_days (no last date ⇒ "
        f"due; §4.6 default 28 d); {n_due} of the dataset series were due at "
        "as_of — the real schedule is unknown [open question Q10]",
        f"{ASSUMPTION_LABEL} naive visiting order is the §4.7 area sweep: "
        f"grid cells of SWEEP_CELL_SIZE_DEG={SWEEP_CELL_SIZE_DEG}° (~1 km), "
        "row-major, lexicographic within a cell — the data has no area field",
        f"{ASSUMPTION_LABEL} naive zero-fill rule: series without a persistence "
        "value at as_of are still visited and collect 0 L / 0 kg",
        DETERMINISM_NOTE,
    ]


# --- Scenarios + simulation (§5.2.4/§5.2.5; src/collection/simulation core) --


SIMULATION_RATES_CAVEAT = "simulation based on historical rates, not a prediction of reality"
"""§5.2.5 mandatory assumption — contract-locked VERBATIM (§6 wording)."""


def _simulation_setup(
    request: schemas.ScenarioRequest,
) -> tuple[date, date, SimulationConfig, list[SeriesDaysToFull], dict[tuple[str, str], date]]:
    """Shared §5.2.4/§5.2.5 setup, validation in contract order (§5.3): no
    dataset → 404 (``store.dataset`` raises NoDatasetError); empty dataset →
    422; overrides → RoutingConfig/PolicyConfig constructors (their messages
    surface on 422); ``travel_time_mode != "fixed_per_leg"`` → 422 (the
    replay is flat-mode, §4.4/§5.2.4); non-uniform densities → 422 (the
    fill→weight arithmetic takes one density); SimulationConfig construction
    last (SimulationConfigError → 422 via the main.py handler). Window:
    start = dataset date_min, length = ``request.simulation_days`` or the
    observed window length (inclusive end). Rates are taken VERBATIM from
    ``build_days_to_full`` §5.2.3 rows — never recomputed here.

    §5.2.5 replay initialisation (user-approved addendum): per series key the
    prior emptying date is the max record date <= start_date (leakage-safe —
    nothing after the window start informs the replay); series with no such
    record stay absent so the simulation clock starts at ``start_date``. The
    same mapping seeds BOTH strategies (one shared initialisation)."""
    dataset = store.dataset
    if not dataset.readings:
        raise ApiError(
            422,
            "dataset has no rows: the scenario/simulation replay needs at "
            "least one emptying record",
        )
    routing = _effective_routing(request.routing_config)
    if routing.config.travel_time_mode != "fixed_per_leg":
        raise ApiError(
            422,
            "scenarios/simulation replay supports only travel_time_mode="
            f"'fixed_per_leg' (flat-mode arithmetic, §4.4/§5.2.4), got "
            f"'{routing.config.travel_time_mode}'",
        )
    densities = set(routing.config.densities_kg_per_litre.values())
    if len(densities) != 1:
        raise ApiError(
            422,
            "scenarios/simulation replay supports only one uniform "
            "density_kg_per_litre (per-material densities are a routing "
            f"concept, §5.2.4), got {sorted(densities)} kg/litre",
        )
    policy = _effective_policy_config(request.policy_config)

    date_min = min(reading.date for reading in dataset.readings)
    date_max = max(reading.date for reading in dataset.readings)
    observed_window_days = (date_max - date_min).days + 1
    simulation_days = (
        request.simulation_days if request.simulation_days is not None else observed_window_days
    )
    estimates = build_days_to_full(dataset).series
    sim_config = SimulationConfig(
        frequency_days=(
            request.frequency_days
            if request.frequency_days is not None
            else routing.config.frequency_days
        ),
        select_threshold_pct=policy.select_threshold_pct,
        container_volume_litres=routing.container_volume_litres,
        containers_per_series=routing.config.containers_per_series,
        service_minutes_per_stop=routing.stop_service_minutes,
        fixed_travel_minutes=routing.config.fixed_travel_minutes,
        disposal_service_minutes=routing.disposal.service_minutes,
        max_shift_minutes=routing.config.max_shift_minutes,
        volume_capacity_litres=routing.vehicle.volume_capacity_litres,
        weight_capacity_kg=routing.vehicle.weight_capacity_kg,
        density_kg_per_litre=densities.pop(),
        cost_per_truck_day_eur=routing.config.cost_per_truck_day_eur,
        operating_days_per_year=routing.config.operating_days_per_year,
    )
    end_date = date_min + timedelta(days=simulation_days - 1)
    # §5.2.5 replay initialisation: last record <= start_date per series
    # (leakage-safe); absent keys start their clock at start_date. The
    # key type widens SeriesKey to tuple[str, str] to match
    # simulate_strategy's Mapping parameter.
    prior_emptying_dates: dict[tuple[str, str], date] = {}
    for key, readings in group_by_series(dataset.readings).items():
        prior = max(
            (reading.date for reading in readings if reading.date <= date_min),
            default=None,
        )
        if prior is not None:
            prior_emptying_dates[key] = prior
    return date_min, end_date, sim_config, estimates, prior_emptying_dates


def _simulation_config_echo(
    sim_config: SimulationConfig, simulation_days: int
) -> schemas.SimulationConfigEcho:
    """Effective simulation inputs (§5.3 echo rule)."""
    return schemas.SimulationConfigEcho(
        frequency_days=sim_config.frequency_days,
        simulation_days=simulation_days,
        select_threshold_pct=sim_config.select_threshold_pct,
        container_volume_litres=sim_config.container_volume_litres,
        containers_per_series=sim_config.containers_per_series,
        service_minutes_per_stop=sim_config.service_minutes_per_stop,
        fixed_travel_minutes=sim_config.fixed_travel_minutes,
        disposal_service_minutes=sim_config.disposal_service_minutes,
        max_shift_minutes=sim_config.max_shift_minutes,
        volume_capacity_litres=sim_config.volume_capacity_litres,
        weight_capacity_kg=sim_config.weight_capacity_kg,
        density_kg_per_litre=sim_config.density_kg_per_litre,
        cost_per_truck_day_eur=sim_config.cost_per_truck_day_eur,
        operating_days_per_year=sim_config.operating_days_per_year,
        travel_time_mode="fixed_per_leg",  # the only mode the replay supports (§5.2.4)
    )


def _simulation_assumptions(sim_config: SimulationConfig) -> list[str]:
    """§5.2.4/§5.2.5 assumption labels — per-value source tags mirroring
    ``_assumption_labels``; effective values are echoed in ``config_echo``."""
    return [
        SIMULATION_RATES_CAVEAT,  # §5.2.5 mandatory, verbatim
        "per-series fill model: rate_pct_per_day x days since last emptying "
        "(container refills from 0 after each emptying; §5.2.3/§5.2.5)",
        f"{ASSUMPTION_LABEL} frequency_days={sim_config.frequency_days} "
        "(fixed-collection-cycle length, §4.7/§5.2.4; real schedule unknown [Q10])",
        f"{ASSUMPTION_LABEL} select_threshold_pct={sim_config.select_threshold_pct:g} "
        "(demand_driven emptying trigger; §3.1 default)",
        f"{REPRESENTATIVE_LABEL} container_volume_litres={sim_config.container_volume_litres}",
        f"{ASSUMPTION_LABEL} containers_per_series={sim_config.containers_per_series} (Q11)",
        f"{REPRESENTATIVE_LABEL} service_minutes_per_stop={sim_config.service_minutes_per_stop}",
        f"{REPRESENTATIVE_LABEL} fixed_travel_minutes={sim_config.fixed_travel_minutes} "
        "on every leg (flat mode, §4.4)",
        f"{ASSUMPTION_LABEL} disposal_service_minutes={sim_config.disposal_service_minutes}",
        f"{REPRESENTATIVE_LABEL} max_shift_minutes={sim_config.max_shift_minutes}",
        f"{ASSUMPTION_LABEL} volume_capacity_litres={sim_config.volume_capacity_litres}, "
        f"weight_capacity_kg={sim_config.weight_capacity_kg}",
        f"{DEMO_DENSITY_SOURCE_LABEL} density_kg_per_litre="
        f"{sim_config.density_kg_per_litre:g} kg/litre",
        f"{REPRESENTATIVE_LABEL} cost_per_truck_day_eur="
        f"{sim_config.cost_per_truck_day_eur:g}, operating_days_per_year="
        f"{sim_config.operating_days_per_year} (cost figures are [predicted], "
        "never invoiced amounts)",
    ]


def _strategy_row(
    strategy_id: Literal["fixed_frequency", "demand_driven"],
    sim: StrategySimulation,
) -> schemas.ScenarioStrategyResponse:
    """§5.2.4 aggregates from one replay (cost [predicted] derivations)."""
    return schemas.ScenarioStrategyResponse(
        id=strategy_id,
        truck_days=sim.truck_days,
        stops_total=sim.stops_total,
        cost_eur_total=sim.cost_eur_total,
        cost_eur_per_year=sim.cost_eur_per_year,
        service=schemas.ScenarioServiceBlock(
            overflow_share_pct=sim.service.overflow_share_pct,
            share_emptyings_full_or_overfull_pct=sim.service.share_emptyings_full_or_overfull_pct,
            max_fill_pct=sim.service.max_fill_pct,
        ),
    )


def _skipped_rows(sim: StrategySimulation) -> list[schemas.SkippedSeriesResponse]:
    """The §5.2.3-reasoned skip list — identical for both strategies (same
    inputs); §4.4: never silently dropped."""
    return [
        schemas.SkippedSeriesResponse(
            location_id=skip.location_id,
            material_type=skip.material_type,
            reason=skip.reason,
        )
        for skip in sim.skipped
    ]


def run_scenarios(request: schemas.ScenarioRequest) -> schemas.ScenarioResponse:
    """§5.2.4 parameterised what-if: replay BOTH strategies over the window
    with the effective physics and report cost AND service level together
    (§6). Deterministic; no solver runs (visiting order cannot change a
    flat-mode day, §4.4)."""
    start, end, sim_config, estimates, priors = _simulation_setup(request)
    fixed = simulate_strategy(
        estimates, "fixed_frequency", sim_config, start, end, prior_emptying_dates=priors
    )
    demand = simulate_strategy(
        estimates, "demand_driven", sim_config, start, end, prior_emptying_dates=priors
    )
    anchor = simulate_observed_anchor(store.dataset.readings)
    return schemas.ScenarioResponse(
        strategies=[
            _strategy_row("fixed_frequency", fixed),
            _strategy_row("demand_driven", demand),
        ],
        skipped_series=_skipped_rows(fixed),
        observed_anchor=schemas.ObservedAnchorResponse(
            basis=anchor.basis,
            share_full_or_overfull_pct=anchor.share_full_or_overfull_pct,
            max_fill_pct=anchor.max_fill_pct,
        ),
        config_echo=_simulation_config_echo(sim_config, (end - start).days + 1),
        assumptions=_simulation_assumptions(sim_config),
    )


def run_simulation(request: schemas.SimulationRequest) -> schemas.SimulationResponse:
    """§5.2.5 deterministic daily replay of both strategies (no OR-Tools, no
    seasonality). Calibration: fixed_frequency's simulated fill-at-emptying
    median vs the observed numeric fill-at-emptying median (§5.2.5 sanity
    check for TechDetails)."""
    start, end, sim_config, estimates, priors = _simulation_setup(request)
    fixed = simulate_strategy(
        estimates, "fixed_frequency", sim_config, start, end, prior_emptying_dates=priors
    )
    demand = simulate_strategy(
        estimates, "demand_driven", sim_config, start, end, prior_emptying_dates=priors
    )
    calib = simulate_calibration(fixed.fills_at_emptying, store.dataset.readings)

    def _strategy(sim: StrategySimulation) -> schemas.SimulationStrategyResponse:
        return schemas.SimulationStrategyResponse(
            id=sim.strategy,
            days=[
                schemas.SimulationDayRecord(
                    date=record.date,
                    collections=record.collections,
                    overflow_containers=record.overflow_containers,
                    truck_days=record.truck_days,
                    cumulative_cost_eur=record.cumulative_cost_eur,
                )
                for record in sim.days
            ],
        )

    return schemas.SimulationResponse(
        start_date=start,
        end_date=end,
        data_basis=schemas.SimulationDataBasis(),
        strategies=[_strategy(fixed), _strategy(demand)],
        calibration=schemas.CalibrationResponse(
            simulated_fill_at_emptying_median_pct=calib.simulated_fill_at_emptying_median_pct,
            observed_fill_at_emptying_median_pct=calib.observed_fill_at_emptying_median_pct,
        ),
        skipped_series=_skipped_rows(fixed),
        config_echo=_simulation_config_echo(sim_config, (end - start).days + 1),
        assumptions=_simulation_assumptions(sim_config),
    )
