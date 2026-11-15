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
from datetime import date, timedelta
from pathlib import Path

from src.api import hosted, schemas
from src.api.errors import DemoDatasetMissingError
from src.api.state import store
from src.collection.policy import (
    Candidate,
    PolicyConfig,
    SelectionResult,
    Skip,
    select_candidates,
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
from src.forecasting.features import SeriesKey, build_feature_row, group_by_series
from src.forecasting.targets import EvaluationCase
from src.routing.demo_config import (
    DEMO_CONTAINER_VOLUME_LITRES,
    DEMO_DEPOT_ID,
    DEMO_DISPOSAL_ID,
    DEMO_DISPOSAL_SERVICE_MINUTES,
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


def config_defaults() -> schemas.ConfigDefaultsResponse:
    """§4.6/§3.1 demo defaults plus every demo-assumption field name."""
    policy = PolicyConfig()
    routing = demo_routing_config()
    vehicle = demo_vehicle_type()
    defaults = schemas.ConfigDefaultsResponse(
        policy=schemas.PolicyDefaults(
            select_threshold_pct=policy.select_threshold_pct,
            uncertainty_buffer_pct=policy.uncertainty_buffer_pct,
            overfull_always_selected=policy.overfull_always_selected,
        ),
        routing=schemas.RoutingDefaults(
            container_volume_litres=DEMO_CONTAINER_VOLUME_LITRES,  # litres [demo assumption §4.6]
            densities_kg_per_litre=dict(routing.densities_kg_per_litre),
            vehicle_volume_capacity_litres=vehicle.volume_capacity_litres,
            vehicle_weight_capacity_kg=vehicle.weight_capacity_kg,
            vehicle_count_available=vehicle.count_available,
            stop_service_minutes=DEMO_STOP_SERVICE_MINUTES,
            disposal_service_minutes=DEMO_DISPOSAL_SERVICE_MINUTES,
            max_shift_minutes=routing.max_shift_minutes,
            avg_speed_kmh=routing.avg_speed_kmh,
            detour_factor=routing.detour_factor,
            solver_solution_limit=routing.solver_solution_limit,
            solver_time_limit_s=routing.solver_time_limit_s,
        ),
        assumption_fields=[
            "select_threshold_pct",
            "uncertainty_buffer_pct",
            "overfull_always_selected",
            "horizon_days",
            *list(schemas.RoutingDefaults.model_fields),
        ],
    )
    return defaults


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
    """Merge §4.6 defaults with overrides and validate by constructing the
    domain schemas (RoutingConfig/VehicleType/DisposalSite; §5.3 — their
    validation messages surface on 422).

    The Pydantic override model already coerced each field to its declared
    type at the boundary (``int | None``/``float | None``/``dict[MaterialType,
    float] | None``), so only typed values reach the constructors here.

    Deployment knob ``WASTECITY_SOLVER_TIME_LIMIT_S`` (``src.api.hosted``)
    supplies the default ``solver_time_limit_s`` when the request does not
    override it; unset/invalid → the §4.6 default (byte-identical behaviour).
    """
    base_config = demo_routing_config()
    base_vehicle = demo_vehicle_type()
    base_disposal = demo_disposal_site()
    env_time_limit = hosted.hosted_solver_time_limit_s()

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
            base_config = RoutingConfig(
                max_shift_minutes=base_config.max_shift_minutes,
                densities_kg_per_litre=dict(base_config.densities_kg_per_litre),
                detour_factor=base_config.detour_factor,
                avg_speed_kmh=base_config.avg_speed_kmh,
                solver_solution_limit=base_config.solver_solution_limit,
                solver_time_limit_s=time_limit_s,
            )
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
        max_shift_minutes=(
            overrides.max_shift_minutes
            if overrides.max_shift_minutes is not None
            else base_config.max_shift_minutes
        ),
        densities_kg_per_litre=(
            overrides.densities_kg_per_litre
            if overrides.densities_kg_per_litre is not None
            else dict(base_config.densities_kg_per_litre)
        ),
        detour_factor=(
            overrides.detour_factor
            if overrides.detour_factor is not None
            else base_config.detour_factor
        ),
        avg_speed_kmh=(
            overrides.avg_speed_kmh
            if overrides.avg_speed_kmh is not None
            else base_config.avg_speed_kmh
        ),
        solver_solution_limit=(
            overrides.solver_solution_limit
            if overrides.solver_solution_limit is not None
            else base_config.solver_solution_limit
        ),
        solver_time_limit_s=time_limit_s,
    )
    vehicle = VehicleType(
        id=base_vehicle.id,
        name=base_vehicle.name,
        volume_capacity_litres=(
            overrides.vehicle_volume_capacity_litres
            if overrides.vehicle_volume_capacity_litres is not None
            else base_vehicle.volume_capacity_litres
        ),
        weight_capacity_kg=(
            overrides.vehicle_weight_capacity_kg
            if overrides.vehicle_weight_capacity_kg is not None
            else base_vehicle.weight_capacity_kg
        ),
        count_available=(
            overrides.vehicle_count_available
            if overrides.vehicle_count_available is not None
            else base_vehicle.count_available
        ),
    )
    disposal = DisposalSite(
        id=base_disposal.id,
        name=base_disposal.name,
        lat=base_disposal.lat,
        lon=base_disposal.lon,
        service_minutes=(
            overrides.disposal_service_minutes
            if overrides.disposal_service_minutes is not None
            else base_disposal.service_minutes
        ),
    )
    return _EffectiveRouting(
        config=config,
        vehicle=vehicle,
        disposal=disposal,
        container_volume_litres=(
            overrides.container_volume_litres
            if overrides.container_volume_litres is not None
            else DEMO_CONTAINER_VOLUME_LITRES
        ),
        stop_service_minutes=(
            overrides.stop_service_minutes
            if overrides.stop_service_minutes is not None
            else DEMO_STOP_SERVICE_MINUTES
        ),
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
            collected_weight_kg=solution.totals.collected_weight_kg,
            stops_served=solution.totals.stops_served,
            stops_total=solution.totals.stops_total,
        ),
        fleet_recommendation=schemas.FleetRecommendationResponse(
            vehicle_type_id=solution.fleet_recommendation.vehicle_type_id,
            count=solution.fleet_recommendation.count,
            basis=schemas.FleetBasisResponse(
                ceil_by_volume=solution.fleet_recommendation.basis.ceil_by_volume,
                ceil_by_weight=solution.fleet_recommendation.basis.ceil_by_weight,
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
    """Labelled assumption strings for the §5.2 RouteResponse (§5.3).

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
        f"{ASSUMPTION_LABEL} container_volume_litres={routing.container_volume_litres}",
        f"{ASSUMPTION_LABEL} densities_kg_per_litre="
        + ", ".join(
            f"{material}={density}" for material, density in config.densities_kg_per_litre.items()
        )
        + " kg/litre",
        f"{ASSUMPTION_LABEL} vehicle '{routing.vehicle.id}': "
        f"{routing.vehicle.volume_capacity_litres} L / "
        f"{routing.vehicle.weight_capacity_kg} kg x "
        f"{routing.vehicle.count_available} available",
        f"{ASSUMPTION_LABEL} stop_service_minutes={routing.stop_service_minutes}, "
        f"disposal_service_minutes={routing.disposal.service_minutes}",
        f"{ASSUMPTION_LABEL} max_shift_minutes={config.max_shift_minutes}",
        f"{ASSUMPTION_LABEL} avg_speed_kmh={config.avg_speed_kmh}, "
        f"detour_factor={config.detour_factor} (matrix derivation)",
        f"{ASSUMPTION_LABEL} solver_solution_limit={config.solver_solution_limit} "
        "(primary stopping criterion, deterministic; §4.7)",
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


# --- Comparison (§5.1 GET /api/comparison; §5.2.2; shared with the M12 CLI) --


@dataclass(frozen=True)
class ComparisonRun:
    """Everything the §5.2.2 v2 ComparisonResponse and the M12 CLI markdown
    are built from — ONE shared core (CLI + endpoint, §5.2.2)."""

    as_of_date: date
    target_date: date
    horizon_days: int
    sweep_all: NaiveSolution
    sweep_selected: NaiveSolution
    optimised_median: schemas.RouteResponse  # run whose distance is the median
    scenarios: list[schemas.ComparisonScenarioResponse]
    gains: schemas.ComparisonGainsResponse
    optimised_determinism: schemas.OptimisedDeterminismResponse
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
    /api/comparison) per contract §4.7 v2: three scenarios in fixed order
    (``naive_sweep_all``, ``naive_sweep_selected``, ``ortools``), gain
    decomposition, and the §4.7 repetition protocol (``runs`` optimised
    solves; the median run is the value used in UI and docs).

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

    scenarios = [
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
        sweep_all=sweep_all,
        sweep_selected=sweep_selected,
        optimised_median=optimised_median,
        scenarios=scenarios,
        gains=gains,
        optimised_determinism=determinism,
        distance_provenance=optimised_median.solution.distance_provenance,
        assumptions=_comparison_assumptions(optimised_median),
    )


def _ratio_1dp(distance_m: int, denominator: int) -> float | None:
    """§5.2.2 per-stop/per-kg metric at 1 d.p.; ``None`` on a zero
    denominator (e.g. fleet exhausted before any stop) — never a fabricated
    0-division value."""
    if denominator == 0:
        return None
    return round(distance_m / denominator, 1)


def _naive_scenario_row(
    method: schemas.ComparisonMethod, naive: NaiveSolution
) -> schemas.ComparisonScenarioResponse:
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
    )


def _comparison_gains(
    scenarios: list[schemas.ComparisonScenarioResponse], optimised: schemas.RouteResponse
) -> schemas.ComparisonGainsResponse:
    """§4.7 gain decomposition in metres. ``routing_gain_m``/``total_gain_m``
    are ``None`` when the optimised scenario has no usable solution
    (infeasible/timeout): a gain against 0 would be fabricated, §5.2.2."""
    sweep_all, sweep_selected, optimised_row = scenarios
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


def comparison() -> schemas.ComparisonResponse:
    """§5.2.2 v2 ComparisonResponse on the active dataset with the fixed
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
        distance_provenance=run.distance_provenance,
        assumptions=run.assumptions,
    )


def _comparison_assumptions(optimised: schemas.RouteResponse) -> list[str]:
    """§5.2.2 assumption labels: the optimised pipeline labels plus the naive
    area-sweep order/zero-fill rules and the §4.7 determinism protocol note."""
    return [
        *optimised.assumptions,
        f"{ASSUMPTION_LABEL} naive visiting order is the §4.7 area sweep: "
        f"grid cells of SWEEP_CELL_SIZE_DEG={SWEEP_CELL_SIZE_DEG}° (~1 km), "
        "row-major, lexicographic within a cell — the data has no area field",
        f"{ASSUMPTION_LABEL} naive zero-fill rule: series without a persistence "
        "value at as_of are still visited and collect 0 L / 0 kg",
        DETERMINISM_NOTE,
    ]
