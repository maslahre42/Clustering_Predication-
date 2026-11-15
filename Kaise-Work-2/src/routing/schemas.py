"""Routing input schemas (M8) — docs/contracts.md §4.1/§4.2/§4.4 (v3).

Frozen stdlib dataclasses, validated at construction; invalid values raise
:class:`RoutingSchemaError` before any routing can run. Field units are
explicit per contract §4.1: litres, kilograms, metres, minutes, percent,
WGS84 degrees, km/h, kg/litre, euros.

Provenance labels: the challenge brief (§3, audited 2026-11-14) names the
variable *categories* but supplies **no values**, and the data contains no
coordinates, capacities or densities (contract §4.5). Part of the §4.6 v3
defaults (2026-11-14) are **[representative]** — verbal values from the
challenge representative; the rest are **[demo assumption]**. Every numeric
value enters through config (``src/routing/demo_config.py``), where each
default carries its source label; nothing here is presented as an observed
fact. ``TravelMatrix.provenance`` keeps the distance derivation visible —
straight-line-derived matrices are never called road distance (AGENTS
rule 9 / contract §4.2).

Deterministic: no randomness; ordering guarantees are provided by the
builders in :mod:`src.routing.geography`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, TypeAlias

from src.data.schema import MATERIALS, MaterialType

__all__ = [
    "TRAVEL_MODES",
    "TRAVEL_MODE_FIXED_PER_LEG",
    "TRAVEL_MODE_HAVERSINE_DERIVED",
    "Depot",
    "DisposalSite",
    "RoutingConfig",
    "RoutingProblem",
    "RoutingSchemaError",
    "Stop",
    "TravelMatrix",
    "TravelTimeMode",
    "VehicleType",
    "effective_collected_volume_litres",
    "effective_collected_weight_kg",
    "effective_service_minutes",
    "stop_point_id",
]

Provenance: TypeAlias = Literal["haversine_straight_line_derived", "external"]
"""Distance-matrix provenance (§4.2): straight-line-derived or externally
supplied. There is no road network source in the data [observed], so a
"road" value does not exist."""

PROVENANCE_HAVERSINE: Provenance = "haversine_straight_line_derived"
PROVENANCE_EXTERNAL: Provenance = "external"

TravelTimeMode: TypeAlias = Literal["fixed_per_leg", "haversine_derived"]
"""Duration mode (§4.2 v3): ``fixed_per_leg`` puts the configured fixed
minutes on EVERY leg incl. depot/disposal legs [representative reading of
"10 min between containers"; the depot/disposal inclusion is an open
question, surfaced in docs/open_questions.md]; ``haversine_derived`` derives
durations from straight-line-derived distance and the configured average
speed. Distances are haversine x detour in BOTH modes — never road."""

TRAVEL_MODE_FIXED_PER_LEG: TravelTimeMode = "fixed_per_leg"
TRAVEL_MODE_HAVERSINE_DERIVED: TravelTimeMode = "haversine_derived"
TRAVEL_MODES: tuple[TravelTimeMode, ...] = (
    TRAVEL_MODE_FIXED_PER_LEG,
    TRAVEL_MODE_HAVERSINE_DERIVED,
)

WGS84_LAT_MIN = -90.0  # degrees
WGS84_LAT_MAX = 90.0  # degrees
WGS84_LON_MIN = -180.0  # degrees
WGS84_LON_MAX = 180.0  # degrees
FILL_MIN = 0.0  # percent (§2.2: clipped float in [0, 100])
FILL_MAX = 100.0  # percent


class RoutingSchemaError(ValueError):
    """Raised for invalid routing input values or inconsistent structures
    (contract §4.2 validation, §4.4 invariants)."""


def _require_non_empty_str(field_name: str, value: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise RoutingSchemaError(f"{field_name} must be a non-empty string, got {value!r}")


def _require_positive_int(field_name: str, value: int) -> None:
    """True ints only (bool excluded); must be > 0."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise RoutingSchemaError(
            f"{field_name} must be an int, got {type(value).__name__} ({value!r})"
        )
    if value <= 0:
        raise RoutingSchemaError(f"{field_name} must be > 0, got {value}")


def _require_positive_number(field_name: str, value: float) -> None:
    """Accept int or float (bool excluded); must be > 0."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise RoutingSchemaError(
            f"{field_name} must be a number, got {type(value).__name__} ({value!r})"
        )
    if value <= 0:
        raise RoutingSchemaError(f"{field_name} must be > 0, got {value}")


def _require_in_range(
    field_name: str,
    value: float,
    minimum: float,
    maximum: float,
) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise RoutingSchemaError(
            f"{field_name} must be a number, got {type(value).__name__} ({value!r})"
        )
    if not minimum <= value <= maximum:
        raise RoutingSchemaError(f"{field_name} must be in [{minimum}, {maximum}], got {value}")


def _require_latitude(field_name: str, value: float) -> None:
    _require_in_range(field_name, value, WGS84_LAT_MIN, WGS84_LAT_MAX)


def _require_longitude(field_name: str, value: float) -> None:
    _require_in_range(field_name, value, WGS84_LON_MIN, WGS84_LON_MAX)


def stop_point_id(stop: Stop) -> str:
    """Deterministic matrix point id for a stop — ``"<location_id>:<material>"``.

    location_ids are UUID-format strings without ':' [observed, profile §5]
    and material is one of brown/green/white, so the separator is
    unambiguous. Depot and disposal sites carry their own explicit ids.
    """
    return f"{stop.location_id}:{stop.material_type}"


@dataclass(frozen=True)
class Depot:
    """Central yard — contract §4.2. Coordinates are [demo assumption]
    synthetic until the host supplies a real depot (§4.5)."""

    id: str
    name: str
    lat: float  # WGS84 degrees
    lon: float  # WGS84 degrees

    def __post_init__(self) -> None:
        _require_non_empty_str("Depot.id", self.id)
        _require_non_empty_str("Depot.name", self.name)
        _require_latitude("Depot.lat", self.lat)
        _require_longitude("Depot.lon", self.lon)


@dataclass(frozen=True)
class DisposalSite:
    """Unloading point — contract §4.2. At least one is required on every
    :class:`RoutingProblem`. Coordinates and service time are [demo
    assumption] synthetic until host data exists (§4.5)."""

    id: str
    name: str
    lat: float  # WGS84 degrees
    lon: float  # WGS84 degrees
    service_minutes: int  # minutes [demo assumption]

    def __post_init__(self) -> None:
        _require_non_empty_str("DisposalSite.id", self.id)
        _require_non_empty_str("DisposalSite.name", self.name)
        _require_latitude("DisposalSite.lat", self.lat)
        _require_longitude("DisposalSite.lon", self.lon)
        _require_positive_int("DisposalSite.service_minutes", self.service_minutes)


@dataclass(frozen=True)
class VehicleType:
    """Fleet type with volume and weight capacity — contract §4.2. All
    capacities and the count are [demo assumption] (brief names vehicle
    categories only). One truck serves ALL materials, collected separated
    [representative]; ``compartment_volume_litres`` pins the per-material
    compartment layout: ``None`` ⇒ equal thirds of ``volume_capacity_litres``
    [demo assumption — layout unknown]; explicit values must cover exactly
    the three observed materials, each > 0, and sum to the volume capacity
    (§4.2). Use :meth:`compartment_capacities` for the resolved layout."""

    id: str
    name: str
    volume_capacity_litres: int  # litres [demo assumption]
    weight_capacity_kg: int  # kilograms [demo assumption]
    count_available: int  # vehicles of this type, int > 0 [demo assumption]
    compartment_volume_litres: dict[MaterialType, int] | None = None  # litres per material

    def __post_init__(self) -> None:
        _require_non_empty_str("VehicleType.id", self.id)
        _require_non_empty_str("VehicleType.name", self.name)
        _require_positive_int("VehicleType.volume_capacity_litres", self.volume_capacity_litres)
        _require_positive_int("VehicleType.weight_capacity_kg", self.weight_capacity_kg)
        _require_positive_int("VehicleType.count_available", self.count_available)
        if self.compartment_volume_litres is None:
            return
        compartments = self.compartment_volume_litres
        if set(compartments) != set(MATERIALS):
            raise RoutingSchemaError(
                "compartment_volume_litres must contain exactly the observed materials "
                f"{sorted(MATERIALS)}, got {sorted(compartments)}"
            )
        for material, litres in compartments.items():
            _require_positive_int(f"compartment_volume_litres[{material}]", litres)
        if sum(compartments.values()) != self.volume_capacity_litres:
            raise RoutingSchemaError(
                "compartment volumes must sum to volume_capacity_litres: "
                f"{sorted(compartments.values())} sums to {sum(compartments.values())}, "
                f"expected {self.volume_capacity_litres}"
            )

    def compartment_capacities(self) -> dict[MaterialType, int]:
        """Resolved per-material compartment capacities in litres.

        Explicit layout echoes the validated dict (fresh dict per call —
        frozen dataclass, the input dict stays mutable). ``None`` resolves to
        equal thirds of ``volume_capacity_litres`` [demo assumption — layout
        unknown]: ``capacity // 3`` per material with the remainder litres
        added to the first materials in observed MATERIALS order, so the
        compartments always sum exactly to the volume capacity (e.g.
        12,000 L → 4,000/4,000/4,000; 1,000 L → 334/333/333)."""
        if self.compartment_volume_litres is not None:
            return dict(self.compartment_volume_litres)
        base = self.volume_capacity_litres // 3
        remainder = self.volume_capacity_litres % 3
        return {
            material: base + (1 if position < remainder else 0)
            for position, material in enumerate(MATERIALS)
        }


@dataclass(frozen=True)
class Stop:
    """One candidate collection stop — contract §4.2 (key into §3 candidates).

    Derived quantities for M9 load progression (deterministic rounding, pinned
    by tests): ``collected_volume_litres`` = round(container_volume_litres x
    predicted_fill_pct / 100) and ``collected_weight_kg(density)`` =
    round(collected_volume_litres x density); Python ``round`` (nearest,
    ties-to-even) in both cases.
    """

    location_id: str
    material_type: MaterialType
    lat: float  # WGS84 degrees [demo assumption: synthetic until host data]
    lon: float  # WGS84 degrees [demo assumption: synthetic until host data]
    container_volume_litres: int  # litres [demo assumption §4.6]
    predicted_fill_pct: float  # percent, from forecast §2.2
    service_minutes: int  # minutes [demo assumption §4.6]

    def __post_init__(self) -> None:
        _require_non_empty_str("Stop.location_id", self.location_id)
        _require_latitude("Stop.lat", self.lat)
        _require_longitude("Stop.lon", self.lon)
        _require_positive_int("Stop.container_volume_litres", self.container_volume_litres)
        _require_in_range("Stop.predicted_fill_pct", self.predicted_fill_pct, FILL_MIN, FILL_MAX)
        _require_positive_int("Stop.service_minutes", self.service_minutes)

    @property
    def collected_volume_litres(self) -> int:
        """Expected collected volume in litres (nearest litre, ties-to-even)."""
        return round(self.container_volume_litres * self.predicted_fill_pct / 100.0)

    def collected_weight_kg(self, density_kg_per_litre: float) -> int:
        """Expected collected weight in kilograms for the given material
        density (nearest kilogram, ties-to-even). Density comes from
        :attr:`RoutingConfig.densities_kg_per_litre` — never hardcoded."""
        _require_positive_number("density_kg_per_litre", density_kg_per_litre)
        return round(self.collected_volume_litres * density_kg_per_litre)


def effective_service_minutes(stop: Stop, config: RoutingConfig) -> int:
    """Stop service minutes actually paid — §4.2 v4: ``containers_per_series``
    (int >= 1 [demo assumption — Q11]) stands for N same-colour containers at
    one site, and EVERY container pays its own emptying minutes, so the stop's
    service time scales with N (``stop.service_minutes x N``). The predicted
    fill % is the series aggregate and does NOT change (the data cannot see
    same-colour duplicates at one site)."""
    return stop.service_minutes * config.containers_per_series


def effective_collected_volume_litres(stop: Stop, config: RoutingConfig) -> int:
    """Litres actually collected at the stop — §4.2 v4: the per-container
    collected volume (:attr:`Stop.collected_volume_litres`, fill % unchanged)
    times ``containers_per_series``."""
    return stop.collected_volume_litres * config.containers_per_series


def effective_collected_weight_kg(stop: Stop, config: RoutingConfig) -> int:
    """Kilograms actually collected at the stop — density x effective litres
    (nearest kilogram, ties-to-even). Densities come from
    :attr:`RoutingConfig.densities_kg_per_litre` — never hardcoded."""
    density = config.densities_kg_per_litre[stop.material_type]
    return round(effective_collected_volume_litres(stop, config) * density)


@dataclass(frozen=True)
class RoutingConfig:
    """Solver/matrix configuration — contract §4.2 (v3). Field sources are
    labelled per value (§4.6 v3: [representative] vs [demo assumption]);
    §4.6 defaults live in ``src/routing/demo_config.py``; all are
    request-overridable at M10.

    ``densities_kg_per_litre`` must contain exactly the three observed
    materials (brown/green/white) with positive values.

    ``travel_time_mode`` selects the matrix duration derivation (§4.2 v3):
    ``fixed_per_leg`` (default) puts ``fixed_travel_minutes`` on EVERY leg
    incl. depot/disposal legs; ``haversine_derived`` keeps the previous
    distance/speed derivation. Distances are haversine x detour in both
    modes — never road. ``avg_speed_kmh``/``detour_factor`` matter only in
    ``haversine_derived`` mode.

    v2 determinism protocol (§4.4/§4.7, user-approved 2026-11-14):
    ``solver_solution_limit`` (int >= 1) is the **primary stopping criterion**
    — a fixed solution budget with no wall-clock dependence, so repeated
    solves that reach it return identical results. ``solver_time_limit_s``
    is a **safety cap only**: if it fires before the solution budget, the
    solve is reported as ``timeout`` (explicitly non-reproducible, §4.7).

    Cost/operating fields (``cost_per_truck_day_eur``,
    ``operating_days_per_week``, ``operating_days_per_year``) are echo/
    display parameters for the derived §4.3 cost block — never invoiced
    amounts (§4.4). Calendar range bounds ([1, 7] / [1, 366]) are physical
    facts, not invented thresholds.
    """

    max_shift_minutes: int  # minutes [representative: 480 = 8 h, §4.6 v3]
    densities_kg_per_litre: dict[MaterialType, float]  # kg/litre [demo assumption]
    detour_factor: float  # dimensionless >= 1 [demo assumption]
    avg_speed_kmh: float  # km/h [demo assumption]; haversine_derived mode only
    # §4.6 v2 defaults (200 solutions / 30.0 s), both [demo assumption].
    solver_solution_limit: int = 200
    solver_time_limit_s: float = 30.0
    # §4.6 v3 defaults (2026-11-14): travel/cost/operating values are
    # [representative] (verbal, challenge representative); geography knobs
    # are [demo assumption] sensitivity knobs — seed 0 / spread 6.0 reproduce
    # the current synthetic layout exactly (regression-tested, §4.6).
    travel_time_mode: TravelTimeMode = TRAVEL_MODE_FIXED_PER_LEG  # [representative]
    fixed_travel_minutes: int = 10  # minutes per leg [representative]; fixed_per_leg only
    cost_per_truck_day_eur: float = 500.0  # euros [representative]
    operating_days_per_week: int = 5  # days/week [representative] (echo/display)
    operating_days_per_year: int = 200  # days/year [representative] (echo/display)
    geography_seed: int = 0  # int >= 0; 0 = current SHA-256 layout [demo assumption knob]
    geography_spread_km: float = (
        6.0  # km; outer radius of the 1..spread band [demo assumption knob]
    )
    # §4.2/§4.6 v4 (2026-11-14): containers_per_series multiplies the litres
    # collected AND the stop service minutes (N same-colour containers per
    # site); the predicted fill % is the series aggregate and does NOT change
    # [demo assumption — Q11]. frequency_days is the §4.7/§5.2.4
    # naive_fixed_frequency cycle length (§4.6 default 28, observed median
    # gap) [demo assumption].
    containers_per_series: int = 1  # int >= 1 [demo assumption — Q11]
    frequency_days: int = 28  # days, int >= 1 [demo assumption]

    def __post_init__(self) -> None:
        _require_positive_int("RoutingConfig.max_shift_minutes", self.max_shift_minutes)
        if set(self.densities_kg_per_litre) != set(MATERIALS):
            raise RoutingSchemaError(
                "densities_kg_per_litre must contain exactly the observed materials "
                f"{sorted(MATERIALS)}, got {sorted(self.densities_kg_per_litre)}"
            )
        for material, density in self.densities_kg_per_litre.items():
            _require_positive_number(f"densities_kg_per_litre[{material}]", density)
        if (
            isinstance(self.detour_factor, bool)
            or not isinstance(self.detour_factor, (int, float))
            or self.detour_factor < 1.0
        ):
            raise RoutingSchemaError(
                f"detour_factor must be a number >= 1, got {self.detour_factor!r}"
            )
        _require_positive_number("RoutingConfig.avg_speed_kmh", self.avg_speed_kmh)
        _require_positive_int("RoutingConfig.solver_solution_limit", self.solver_solution_limit)
        _require_positive_number("RoutingConfig.solver_time_limit_s", self.solver_time_limit_s)
        if self.travel_time_mode not in TRAVEL_MODES:
            raise RoutingSchemaError(
                f"travel_time_mode must be one of {list(TRAVEL_MODES)}, "
                f"got {self.travel_time_mode!r}"
            )
        _require_positive_int("RoutingConfig.fixed_travel_minutes", self.fixed_travel_minutes)
        _require_positive_number(
            "RoutingConfig.cost_per_truck_day_eur", self.cost_per_truck_day_eur
        )
        if (
            isinstance(self.operating_days_per_week, bool)
            or not isinstance(self.operating_days_per_week, int)
            or not 1 <= self.operating_days_per_week <= 7
        ):
            raise RoutingSchemaError(
                "operating_days_per_week must be an int in [1, 7] (calendar bound), "
                f"got {self.operating_days_per_week!r}"
            )
        if (
            isinstance(self.operating_days_per_year, bool)
            or not isinstance(self.operating_days_per_year, int)
            or not 1 <= self.operating_days_per_year <= 366
        ):
            raise RoutingSchemaError(
                "operating_days_per_year must be an int in [1, 366] (calendar bound), "
                f"got {self.operating_days_per_year!r}"
            )
        if isinstance(self.geography_seed, bool) or not isinstance(self.geography_seed, int):
            raise RoutingSchemaError(
                f"geography_seed must be an int >= 0, got {type(self.geography_seed).__name__} "
                f"({self.geography_seed!r})"
            )
        if self.geography_seed < 0:
            raise RoutingSchemaError(f"geography_seed must be >= 0, got {self.geography_seed}")
        _require_positive_number("RoutingConfig.geography_spread_km", self.geography_spread_km)
        _require_positive_int("RoutingConfig.containers_per_series", self.containers_per_series)
        _require_positive_int("RoutingConfig.frequency_days", self.frequency_days)


@dataclass(frozen=True)
class TravelMatrix:
    """Distance/duration matrices over depot + disposal + stop ids — §4.2.

    ``distance_m[i][j]``/``duration_min[i][j]`` are ints in metres/minutes.
    Invariants enforced here: square and consistent with ``point_ids`` (which
    must be unique non-empty strings), zero diagonal, symmetric (§4.2).
    ``provenance`` records how distances were derived; straight-line-derived
    matrices must keep ``"haversine_straight_line_derived"`` visible in all
    downstream outputs — never presented as road distance.
    """

    point_ids: list[str]
    distance_m: list[list[int]]
    duration_min: list[list[int]]
    provenance: Provenance

    def __post_init__(self) -> None:
        n = len(self.point_ids)
        if n == 0:
            raise RoutingSchemaError("point_ids must contain at least the depot id")
        if len(set(self.point_ids)) != n:
            raise RoutingSchemaError("point_ids must be unique")
        for point_id in self.point_ids:
            _require_non_empty_str("TravelMatrix.point_ids entry", point_id)
        self._require_square_matrix("distance_m", self.distance_m, n)
        self._require_square_matrix("duration_min", self.duration_min, n)
        for i in range(n):
            if self.distance_m[i][i] != 0 or self.duration_min[i][i] != 0:
                raise RoutingSchemaError(
                    f"diagonal must be zero at index {i} "
                    f"(distance_m={self.distance_m[i][i]}, duration_min={self.duration_min[i][i]})"
                )
            for j in range(i + 1, n):
                if self.distance_m[i][j] != self.distance_m[j][i]:
                    raise RoutingSchemaError(
                        f"distance_m must be symmetric at ({i}, {j}): "
                        f"{self.distance_m[i][j]} != {self.distance_m[j][i]}"
                    )
                if self.duration_min[i][j] != self.duration_min[j][i]:
                    raise RoutingSchemaError(
                        f"duration_min must be symmetric at ({i}, {j}): "
                        f"{self.duration_min[i][j]} != {self.duration_min[j][i]}"
                    )
        if self.provenance not in (PROVENANCE_HAVERSINE, PROVENANCE_EXTERNAL):
            raise RoutingSchemaError(
                f"provenance must be {PROVENANCE_HAVERSINE!r} or {PROVENANCE_EXTERNAL!r}, "
                f"got {self.provenance!r} (a 'road' value does not exist: no road data)"
            )

    @staticmethod
    def _require_square_matrix(field_name: str, matrix: list[list[int]], n: int) -> None:
        if len(matrix) != n:
            raise RoutingSchemaError(
                f"{field_name} must have {n} rows to match point_ids, got {len(matrix)}"
            )
        for row_index, row in enumerate(matrix):
            if len(row) != n:
                raise RoutingSchemaError(
                    f"{field_name} row {row_index} must have {n} entries, got {len(row)}"
                )
            for col_index, value in enumerate(row):
                if isinstance(value, bool) or not isinstance(value, int):
                    raise RoutingSchemaError(
                        f"{field_name}[{row_index}][{col_index}] must be an int, "
                        f"got {type(value).__name__} ({value!r})"
                    )
                if value < 0:
                    raise RoutingSchemaError(
                        f"{field_name}[{row_index}][{col_index}] must be >= 0, got {value}"
                    )


@dataclass(frozen=True)
class RoutingProblem:
    """Complete solver input — contract §4.2.

    Invariants enforced at construction: at least one disposal site (§4.2),
    at least one vehicle type (a fleet-less problem is invalid input;
    infeasibility of a *valid* problem is surfaced at M9, never hidden),
    unique disposal/vehicle ids, unique stop keys, and the travel matrix must
    cover exactly the point ids of depot + disposal sites + stops.
    """

    depot: Depot
    disposal_sites: list[DisposalSite]
    stops: list[Stop]
    vehicle_types: list[VehicleType]
    travel: TravelMatrix
    config: RoutingConfig

    def __post_init__(self) -> None:
        if len(self.disposal_sites) < 1:
            raise RoutingSchemaError("at least one disposal site is required (contract §4.2)")
        if len(self.vehicle_types) < 1:
            raise RoutingSchemaError("at least one vehicle type is required")
        disposal_ids = [site.id for site in self.disposal_sites]
        if len(set(disposal_ids)) != len(disposal_ids):
            raise RoutingSchemaError(f"disposal site ids must be unique, got {disposal_ids}")
        vehicle_ids = [vehicle.id for vehicle in self.vehicle_types]
        if len(set(vehicle_ids)) != len(vehicle_ids):
            raise RoutingSchemaError(f"vehicle type ids must be unique, got {vehicle_ids}")
        stop_keys = [(stop.location_id, stop.material_type) for stop in self.stops]
        if len(set(stop_keys)) != len(stop_keys):
            raise RoutingSchemaError("stop keys (location_id, material) must be unique")
        expected_point_ids = {self.depot.id}
        expected_point_ids.update(disposal_ids)
        expected_point_ids.update(stop_point_id(stop) for stop in self.stops)
        if set(self.travel.point_ids) != expected_point_ids:
            missing = sorted(expected_point_ids - set(self.travel.point_ids))
            extra = sorted(set(self.travel.point_ids) - expected_point_ids)
            raise RoutingSchemaError(
                "travel.point_ids must cover exactly depot + disposal + stop ids; "
                f"missing={missing}, extra={extra}"
            )
