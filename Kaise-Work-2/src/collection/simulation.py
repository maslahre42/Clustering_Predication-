"""Strategy simulation core (v4) — docs/contracts.md §5.2.4/§5.2.5.

Deterministic daily replay of the two collection strategies over per-series
rates taken **verbatim** from :mod:`src.forecasting.days_to_full` (§5.2.3
``rate_pct_per_day``) — rates are never recomputed here. Same inputs ⇒
identical output; no OR-Tools, no randomness, no seasonality or holiday
multipliers (§5.2.5: rejected — docs/partner_prototype_review.md 4/6).

Fill model (§5.2.5): a series' simulated fill on day ``d`` is
``rate_pct_per_day x days since its last (simulated) emptying``; the day of
an emptying counts as day 0 (fill resets to 0). At the window start the
clock is seeded from the caller-supplied ``prior_emptying_dates`` mapping
(§5.2.5 v4 addendum: the series' **latest record ≤ ``start_date``**, past-only
and leakage-safe, computed by the caller from the active dataset; a series
without a mapping entry starts empty at ``start_date``). The §5.2.3
``last_emptying_date`` (the globally-latest record, at/near the window end)
never seeds the clock — it stays a §5.2.3 response field only; seeding from
it deadens the early replay (observed: ~4 dead months, status-quo cost
understated ~15x). A mapped date after ``start_date`` raises
:class:`SimulationConfigError` — honest failure, never a silent clamp.
Overflow is counted per container-day with end-of-day fill > 100. Collection
at emptying is capped at the container volume (fill beyond 100 spills —
exactly what the overflow counter reports).

Cost/truck model ([predicted] demo arithmetic, flat mode §4.4 — every leg
costs ``fixed_travel_minutes`` so visiting order cannot change a day's
time): the stops of one day are packed greedily in deterministic
``(location_id, material_type)`` order into §4.6 trucks — per-material
compartment capacity (equal thirds via
:class:`src.routing.schemas.VehicleType`), total weight, and
``max_shift_minutes``. A stop that would exceed its compartment or the
weight capacity first triggers a mid-shift disposal unload
(``2 x fixed_travel + disposal_service``) while the truck carries load; a
stop that no longer fits the remaining shift closes the truck and the next
truck continues with it ("disposal every full vehicle" is the unload above;
the yard absorbs any residual load — §4.4 [demo assumption]). A stop that
cannot fit even an empty truck is force-served on a fresh truck (cannot
occur under §4.6 defaults: 3,000 L <= 4,000 L compartment) — never dropped.

``cost_eur_total = truck_days x cost_per_truck_day_eur``;
``cost_eur_per_year = (truck_days / replay_days) x cost_per_truck_day_eur x
operating_days_per_year`` — proportional scaling of the replayed window
[predicted derivation, never an invoiced amount].

Series without a usable rate (``rate_pct_per_day`` None or <= 0 — the §5.2.3
reasons incl. ``zero_rate``) are skipped from the replay and reported with
their reason (§4.4: never silently dropped, never fabricated).

All defaults live in :class:`SimulationConfig` with §4.6/§3.1 values; each
carries its source label in the field docs ([representative] / [literature]
/ [demo assumption]).
"""

from __future__ import annotations

import statistics
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Literal, TypeAlias

from src.data.schema import MATERIALS, MaterialType, ReadingRecord
from src.forecasting.days_to_full import SeriesDaysToFull
from src.routing.demo_config import (
    DEMO_CONTAINER_VOLUME_LITRES,
    DEMO_CONTAINERS_PER_SERIES,
    DEMO_COST_PER_TRUCK_DAY_EUR,
    DEMO_DISPOSAL_SERVICE_MINUTES,
    DEMO_FIXED_TRAVEL_MINUTES,
    DEMO_FREQUENCY_DAYS,
    DEMO_MAX_SHIFT_MINUTES,
    DEMO_OPERATING_DAYS_PER_YEAR,
    DEMO_STOP_SERVICE_MINUTES,
    DEMO_VEHICLE_VOLUME_CAPACITY_LITRES,
    DEMO_VEHICLE_WEIGHT_CAPACITY_KG,
)
from src.routing.schemas import (
    RoutingConfig,
    Stop,
    VehicleType,
    effective_collected_volume_litres,
    effective_service_minutes,
)

__all__ = [
    "STRATEGY_DEMAND_DRIVEN",
    "STRATEGY_FIXED_FREQUENCY",
    "Calibration",
    "DailyRecord",
    "ObservedAnchor",
    "ServiceMetrics",
    "SimulationConfig",
    "SimulationConfigError",
    "SkippedSeries",
    "Strategy",
    "StrategySimulation",
    "calibration",
    "observed_anchor",
    "simulate_strategy",
]

STRATEGY_FIXED_FREQUENCY: Literal["fixed_frequency"] = "fixed_frequency"
STRATEGY_DEMAND_DRIVEN: Literal["demand_driven"] = "demand_driven"

Strategy: TypeAlias = Literal["fixed_frequency", "demand_driven"]

FULL_FILL_PCT = 100.0  # percent; the §5.2.5 overflow threshold (fill > 100)

_POLICY_DEFAULT_THRESHOLD_PCT = 80.0  # percent — §3.1 PolicyConfig default
# [demo assumption, user-agreed §3.4]; kept in sync with PolicyConfig.


class SimulationConfigError(ValueError):
    """Raised for invalid simulation parameter values (validated at
    construction, mirroring the §3.1/§4.2 validation style)."""


@dataclass(frozen=True)
class SimulationConfig:
    """§4.6/§3.1 physics for the simulation core — one place, labelled.

    The truck parameters mirror the §4.6 ``demo_truck`` (compartments
    resolve to equal thirds via :class:`VehicleType`);
    ``density_kg_per_litre`` is the §4.6 v4 default [literature AVV 20 01
    02]. All fields are request-overridable at the API boundary (the backend
    maps overrides onto this constructor and echoes the effective values).
    """

    frequency_days: int = DEMO_FREQUENCY_DAYS  # days >= 1 [demo assumption §4.6]
    select_threshold_pct: float = _POLICY_DEFAULT_THRESHOLD_PCT  # §3.1 default, [0, 100]
    container_volume_litres: int = DEMO_CONTAINER_VOLUME_LITRES  # litres [representative]
    containers_per_series: int = DEMO_CONTAINERS_PER_SERIES  # int >= 1 [demo assumption Q11]
    service_minutes_per_stop: int = DEMO_STOP_SERVICE_MINUTES  # minutes [representative]
    fixed_travel_minutes: int = DEMO_FIXED_TRAVEL_MINUTES  # minutes per leg [representative]
    disposal_service_minutes: int = DEMO_DISPOSAL_SERVICE_MINUTES  # minutes [demo assumption]
    max_shift_minutes: int = DEMO_MAX_SHIFT_MINUTES  # minutes [representative]
    volume_capacity_litres: int = DEMO_VEHICLE_VOLUME_CAPACITY_LITRES  # litres [demo assumption]
    weight_capacity_kg: int = DEMO_VEHICLE_WEIGHT_CAPACITY_KG  # kilograms [demo assumption]
    density_kg_per_litre: float = 0.4  # kg/litre [literature — §4.6 v4, AVV 20 01 02]
    cost_per_truck_day_eur: float = DEMO_COST_PER_TRUCK_DAY_EUR  # euros [representative]
    operating_days_per_year: int = DEMO_OPERATING_DAYS_PER_YEAR  # days [representative]

    def __post_init__(self) -> None:
        for field_name in (
            "frequency_days",
            "container_volume_litres",
            "containers_per_series",
            "service_minutes_per_stop",
            "fixed_travel_minutes",
            "disposal_service_minutes",
            "max_shift_minutes",
            "volume_capacity_litres",
            "weight_capacity_kg",
        ):
            value = getattr(self, field_name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                raise SimulationConfigError(f"{field_name} must be an int >= 1, got {value!r}")
        for field_name in (
            "density_kg_per_litre",
            "cost_per_truck_day_eur",
        ):
            value = getattr(self, field_name)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
                raise SimulationConfigError(f"{field_name} must be a number > 0, got {value!r}")
        # §3.1 percent bounds: the threshold MAY be 0 (empty everything).
        threshold = self.select_threshold_pct
        if (
            isinstance(threshold, bool)
            or not isinstance(threshold, (int, float))
            or not 0 <= threshold <= 100
        ):
            raise SimulationConfigError(
                f"select_threshold_pct must be a number in [0, 100], got {threshold!r}"
            )
        days_per_year = self.operating_days_per_year
        if (
            isinstance(days_per_year, bool)
            or not isinstance(days_per_year, int)
            or not 1 <= days_per_year <= 366
        ):
            raise SimulationConfigError(
                f"operating_days_per_year must be an int in [1, 366], got {days_per_year!r}"
            )

    def _routing_config(self) -> RoutingConfig:
        """A :class:`RoutingConfig` carrying the SAME multiplier/density
        semantics so the routing ``effective_*`` helpers are reused verbatim
        (§4.2 v4). Travel/detour values are inert here — the simulation uses
        flat-mode minutes only — and are set to the §4.6 defaults to keep one
        source of truth."""
        return RoutingConfig(
            max_shift_minutes=self.max_shift_minutes,
            densities_kg_per_litre={material: self.density_kg_per_litre for material in MATERIALS},
            detour_factor=1.4,  # §4.6 default [demo assumption]; unused in flat mode
            avg_speed_kmh=30.0,  # §4.6 default [demo assumption]; unused in flat mode
            containers_per_series=self.containers_per_series,
        )

    def _compartments(self) -> dict[MaterialType, int]:
        """Per-material compartment capacities — equal thirds of
        ``volume_capacity_litres`` via the §4.2 rule (:class:`VehicleType`),
        so simulation and router share one layout derivation."""
        vehicle_type = VehicleType(
            id="simulation_truck",
            name="Simulation Truck (arithmetic only)",
            volume_capacity_litres=self.volume_capacity_litres,
            weight_capacity_kg=self.weight_capacity_kg,
            count_available=1,
        )
        return vehicle_type.compartment_capacities()


@dataclass(frozen=True)
class DailyRecord:
    """One replayed day — contract §5.2.5 ``days`` entries."""

    date: date
    collections: int  # emptying events this day
    overflow_containers: int  # container-days with end-of-day fill > 100
    truck_days: int  # trucks needed for this day's stops (flat-mode packing)
    cumulative_cost_eur: float  # running truck_days x cost_per_truck_day_eur


@dataclass(frozen=True)
class ServiceMetrics:
    """Simulated service level — contract §5.2.4 ``service`` (basis
    ``"simulated"``; §6: always reported beside cost). ``None`` values: no
    active series (all shares/max) or no emptying events
    (``share_emptyings_full_or_overfull_pct``)."""

    basis: Literal["simulated"] = "simulated"
    overflow_share_pct: float | None = None  # % container-days with fill > 100, 1 d.p.
    share_emptyings_full_or_overfull_pct: float | None = None  # 1 d.p.; None iff no emptyings
    max_fill_pct: float | None = None  # max end-of-day fill, 1 d.p.; None iff no active series


@dataclass(frozen=True)
class SkippedSeries:
    """A series excluded from the replay with its §5.2.3 reason (never
    silently dropped, never fabricated)."""

    location_id: str
    material_type: MaterialType
    reason: str


@dataclass(frozen=True)
class StrategySimulation:
    """One strategy's replay — contract §5.2.4 aggregates + §5.2.5 daily
    records. Cost figures are [predicted] derivations, never invoiced
    amounts."""

    strategy: Strategy
    days: list[DailyRecord]
    truck_days: int
    stops_total: int  # = total emptying events replayed
    cost_eur_total: float
    cost_eur_per_year: float  # [predicted]: (truck_days/replay_days) x rate x operating days
    service: ServiceMetrics
    skipped: list[SkippedSeries]
    fills_at_emptying: list[float]  # raw simulated fill % at each emptying (§5.2.5 calibration)


@dataclass(frozen=True)
class ObservedAnchor:
    """§5.2.4 ``observed_anchor`` — the status-quo service level from the
    observed emptying records (§1.5: every record is an emptying record
    [representative-stated]). ``None`` values iff ``records`` is empty."""

    basis: Literal["observed_emptying_records"] = "observed_emptying_records"
    share_full_or_overfull_pct: float | None = None
    max_fill_pct: float | None = None


@dataclass(frozen=True)
class Calibration:
    """§5.2.5 ``calibration`` — the sanity-check medians pair for
    TechDetails. Either side is ``None`` iff that side has no values."""

    simulated_fill_at_emptying_median_pct: float | None = None
    observed_fill_at_emptying_median_pct: float | None = None


def _active_estimates(
    series_estimates: Sequence[SeriesDaysToFull],
) -> tuple[list[SeriesDaysToFull], list[SkippedSeries]]:
    """Split estimates into simutable series and counted skips. A series is
    skipped iff it has no usable rate (``rate_pct_per_day`` None or <= 0,
    e.g. reason ``zero_rate``); the reason string is the §5.2.3 reason when
    present, else ``"zero_rate"``. Both lists are sorted deterministically."""
    active: list[SeriesDaysToFull] = []
    skipped: list[SkippedSeries] = []
    for estimate in series_estimates:
        rate = estimate.rate_pct_per_day
        if rate is None or rate <= 0:
            skipped.append(
                SkippedSeries(
                    location_id=estimate.location_id,
                    material_type=estimate.material_type,
                    reason=estimate.reason or "zero_rate",
                )
            )
        else:
            active.append(estimate)
    active.sort(key=lambda estimate: (estimate.location_id, estimate.material_type))
    skipped.sort(key=lambda skip: (skip.location_id, skip.material_type))
    return active, skipped


def _packing_trucks(
    day_stops: Sequence[Stop],
    compartments: dict[MaterialType, int],
    config: SimulationConfig,
    routing_config: RoutingConfig,
) -> int:
    """Number of §4.6 trucks needed for one day's stops (flat mode §4.4).

    Deterministic greedy packing in ``(location_id, material_type)`` order:
    a stop that would exceed its compartment or the weight capacity first
    triggers a mid-shift disposal unload (``2 x fixed_travel_minutes +
    disposal_service_minutes``) while the truck carries load; a stop that no
    longer fits the remaining shift closes the truck and the next truck
    continues with it. On a fresh truck (nothing loaded, minutes == 0) a
    stop is force-served — capacity/shift-infeasible stops cannot occur
    under §4.6 defaults, and the simulation never drops a stop (§4.4). Each
    outer iteration consumes at least one stop, so the loop terminates."""
    trucks = 0
    remaining = sorted(day_stops, key=lambda stop: (stop.location_id, stop.material_type))
    index = 0
    while index < len(remaining):
        trucks += 1
        load_by_material: dict[MaterialType, int] = {material: 0 for material in MATERIALS}
        weight = 0
        minutes = 0
        while index < len(remaining):
            stop = remaining[index]
            volume = effective_collected_volume_litres(stop, routing_config)
            kg = round(volume * config.density_kg_per_litre)
            service = effective_service_minutes(stop, routing_config)
            leg = config.fixed_travel_minutes
            fits_capacity = (
                load_by_material[stop.material_type] + volume <= compartments[stop.material_type]
                and weight + kg <= config.weight_capacity_kg
            )
            if not fits_capacity and sum(load_by_material.values()) > 0:
                # "Disposal every full vehicle": unload mid-shift, then retry.
                minutes += 2 * leg + config.disposal_service_minutes
                load_by_material = {material: 0 for material in MATERIALS}
                weight = 0
                fits_capacity = (
                    volume <= compartments[stop.material_type] and kg <= config.weight_capacity_kg
                )
            shift_ok = minutes + leg + service <= config.max_shift_minutes
            if (fits_capacity and shift_ok) or minutes == 0:
                minutes += leg + service  # serve (force-served on a fresh truck if infeasible)
                load_by_material[stop.material_type] += volume
                weight += kg
                index += 1
            else:
                break  # shift exhausted; the next truck continues with this stop
    return trucks


def simulate_strategy(
    series_estimates: Sequence[SeriesDaysToFull],
    strategy: Strategy,
    config: SimulationConfig,
    start_date: date,
    end_date: date,
    *,
    prior_emptying_dates: Mapping[tuple[str, str], date],
) -> StrategySimulation:
    """Daily replay of one strategy over ``[start_date, end_date]``
    (§5.2.4/§5.2.5). Fill = ``rate_pct_per_day x days since last (simulated)
    emptying`` (the emptying day is day 0); ``fixed_frequency`` empties iff
    ``days_since >= frequency_days``, ``demand_driven`` iff the fill at the
    visit is >= ``select_threshold_pct`` (§3.1). Deterministic: same inputs
    ⇒ identical :class:`StrategySimulation`.

    ``prior_emptying_dates`` (required, §5.2.5 v4 addendum) maps each series
    key ``(location_id, material_type)`` to its pre-window emptying date —
    the latest record ≤ ``start_date`` computed by the caller from the active
    dataset. Each active series' clock starts at that date when present, else
    at ``start_date`` with fill 0. The §5.2.3 ``last_emptying_date`` is never
    used here (response field only). Any mapped date > ``start_date`` raises
    :class:`SimulationConfigError`; a date exactly == ``start_date`` is valid
    (series emptied on day 0 → due again at ``start_date + frequency_days``).
    """
    if end_date < start_date:
        raise ValueError(f"end_date {end_date} is before start_date {start_date}")
    if strategy not in (STRATEGY_FIXED_FREQUENCY, STRATEGY_DEMAND_DRIVEN):
        raise ValueError(f"strategy must be 'fixed_frequency' or 'demand_driven', got {strategy!r}")
    for key, prior_date in prior_emptying_dates.items():
        if prior_date > start_date:
            raise SimulationConfigError(
                f"prior_emptying_dates must be ≤ start_date {start_date}: {key} -> {prior_date}"
            )

    active, skipped = _active_estimates(series_estimates)
    compartments = config._compartments()
    routing_config = config._routing_config()

    # Simulated state: last emptying per series — §5.2.5 v4 addendum: the
    # clock starts at the caller-supplied pre-window date when the series has
    # a mapping entry, else at start_date (series starts empty). The §5.2.3
    # estimate.last_emptying_date (globally-latest record, near the window
    # end) never seeds the clock — response field only.
    last_emptying: dict[tuple[str, MaterialType], date] = {
        (estimate.location_id, estimate.material_type): prior_emptying_dates.get(
            (estimate.location_id, estimate.material_type), start_date
        )
        for estimate in active
    }

    def series_stop(estimate: SeriesDaysToFull, fill_pct: float) -> Stop:
        """The §4.2 Stop-shaped input for the routing effective helpers. The
        fill is the simulated value clamped to [0, 100] — beyond 100 the
        container is full and the excess is the counted overflow (collection
        caps at the container volume). Coordinates are inert in flat mode."""
        clamped = min(FULL_FILL_PCT, max(0.0, fill_pct))
        return Stop(
            location_id=estimate.location_id,
            material_type=estimate.material_type,
            lat=0.0,
            lon=0.0,
            container_volume_litres=config.container_volume_litres,
            predicted_fill_pct=clamped,
            service_minutes=config.service_minutes_per_stop,
        )

    days: list[DailyRecord] = []
    cumulative_cost = 0.0
    total_truck_days = 0
    total_stops = 0
    fills_at_emptying: list[float] = []
    container_days = 0
    overflow_container_days = 0
    full_emptyings = 0
    max_fill: float | None = None

    day = start_date
    while day <= end_date:
        emptied_today: list[Stop] = []
        overflow_today = 0
        for estimate in active:
            key = (estimate.location_id, estimate.material_type)
            assert estimate.rate_pct_per_day is not None  # _active_estimates guarantees
            days_since = (day - last_emptying[key]).days
            fill_pct = max(0.0, estimate.rate_pct_per_day * days_since)
            due = (
                days_since >= config.frequency_days
                if strategy == STRATEGY_FIXED_FREQUENCY
                else fill_pct >= config.select_threshold_pct
            )
            if due:
                fills_at_emptying.append(fill_pct)
                if fill_pct >= FULL_FILL_PCT:
                    full_emptyings += 1
                emptied_today.append(series_stop(estimate, fill_pct))
                last_emptying[key] = day
            end_of_day_fill = max(0.0, estimate.rate_pct_per_day * (day - last_emptying[key]).days)
            container_days += 1
            if end_of_day_fill > FULL_FILL_PCT:
                overflow_today += 1
                overflow_container_days += 1
            if max_fill is None or end_of_day_fill > max_fill:
                max_fill = end_of_day_fill

        truck_days_today = (
            _packing_trucks(emptied_today, compartments, config, routing_config)
            if emptied_today
            else 0
        )
        total_truck_days += truck_days_today
        total_stops += len(emptied_today)
        cumulative_cost = round(
            cumulative_cost + truck_days_today * config.cost_per_truck_day_eur, 2
        )
        days.append(
            DailyRecord(
                date=day,
                collections=len(emptied_today),
                overflow_containers=overflow_today,
                truck_days=truck_days_today,
                cumulative_cost_eur=cumulative_cost,
            )
        )
        day = day + timedelta(days=1)

    total_cost = round(total_truck_days * config.cost_per_truck_day_eur, 2)
    replay_days = (end_date - start_date).days + 1
    cost_eur_per_year = round(total_cost / replay_days * config.operating_days_per_year, 2)
    service = ServiceMetrics(
        overflow_share_pct=round(100.0 * overflow_container_days / container_days, 1)
        if container_days
        else None,
        share_emptyings_full_or_overfull_pct=(
            round(100.0 * full_emptyings / len(fills_at_emptying), 1) if fills_at_emptying else None
        ),
        max_fill_pct=round(max_fill, 1) if max_fill is not None else None,
    )
    return StrategySimulation(
        strategy=strategy,
        days=days,
        truck_days=total_truck_days,
        stops_total=total_stops,
        cost_eur_total=total_cost,
        cost_eur_per_year=cost_eur_per_year,
        service=service,
        skipped=skipped,
        fills_at_emptying=fills_at_emptying,
    )


def observed_anchor(records: Sequence[ReadingRecord]) -> ObservedAnchor:
    """§5.2.4 ``observed_anchor``: share of emptying records that carry the
    overfull token or a numeric fill >= 100, plus the numeric max fill. Both
    values are ``None`` iff ``records`` is empty."""
    if not records:
        return ObservedAnchor()
    full_or_overfull = sum(
        1 for record in records if record.is_overfull or (record.fill_level_pct or 0) >= 100
    )
    numeric = [record.fill_level_pct for record in records if record.fill_level_pct is not None]
    return ObservedAnchor(
        share_full_or_overfull_pct=round(100.0 * full_or_overfull / len(records), 1),
        max_fill_pct=float(max(numeric)) if numeric else None,
    )


def calibration(
    simulated_fills_at_emptying: Sequence[float],
    records: Sequence[ReadingRecord],
) -> Calibration:
    """§5.2.5 ``calibration`` medians pair for TechDetails: median simulated
    fill at emptying vs median observed numeric fill at emptying (overfull
    tokens carry no numeric value and are excluded)."""
    observed_numeric = [
        float(record.fill_level_pct) for record in records if record.fill_level_pct is not None
    ]
    return Calibration(
        simulated_fill_at_emptying_median_pct=(
            statistics.median(simulated_fills_at_emptying) if simulated_fills_at_emptying else None
        ),
        observed_fill_at_emptying_median_pct=(
            statistics.median(observed_numeric) if observed_numeric else None
        ),
    )
