"""Routing input schemas (M8) — docs/contracts.md §4.1/§4.2/§4.4.

Frozen stdlib dataclasses, validated at construction; invalid values raise
:class:`RoutingSchemaError` before any routing can run. Field units are
explicit per contract §4.1: litres, kilograms, metres, minutes, percent,
WGS84 degrees, km/h, kg/litre.

Provenance labels: the challenge brief (§3, audited 2026-11-14) names the
variable *categories* but supplies **no values**, and the data contains no
coordinates, capacities or densities (contract §4.5). Every numeric value
therefore enters through config (``src/routing/demo_config.py``), where each
default is labelled **[demo assumption]**; nothing here is presented as an
observed fact. ``TravelMatrix.provenance`` keeps the distance derivation
visible — straight-line-derived matrices are never called road distance
(AGENTS rule 9 / contract §4.2).

Deterministic: no randomness; ordering guarantees are provided by the
builders in :mod:`src.routing.geography`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, TypeAlias

from src.data.schema import MATERIALS, MaterialType

__all__ = [
    "Depot",
    "DisposalSite",
    "RoutingConfig",
    "RoutingProblem",
    "RoutingSchemaError",
    "Stop",
    "TravelMatrix",
    "VehicleType",
    "stop_point_id",
]

Provenance: TypeAlias = Literal["haversine_straight_line_derived", "external"]
"""Distance-matrix provenance (§4.2): straight-line-derived or externally
supplied. There is no road network source in the data [observed], so a
"road" value does not exist."""

PROVENANCE_HAVERSINE: Provenance = "haversine_straight_line_derived"
PROVENANCE_EXTERNAL: Provenance = "external"

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
    categories only)."""

    id: str
    name: str
    volume_capacity_litres: int  # litres [demo assumption]
    weight_capacity_kg: int  # kilograms [demo assumption]
    count_available: int  # vehicles of this type, int > 0 [demo assumption]

    def __post_init__(self) -> None:
        _require_non_empty_str("VehicleType.id", self.id)
        _require_non_empty_str("VehicleType.name", self.name)
        _require_positive_int("VehicleType.volume_capacity_litres", self.volume_capacity_litres)
        _require_positive_int("VehicleType.weight_capacity_kg", self.weight_capacity_kg)
        _require_positive_int("VehicleType.count_available", self.count_available)


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


@dataclass(frozen=True)
class RoutingConfig:
    """Solver/matrix configuration — contract §4.2. Every field is [demo
    assumption] (§4.6 user-agreed defaults live in
    ``src/routing/demo_config.py``); all are request-overridable at M10.

    ``densities_kg_per_litre`` must contain exactly the three observed
    materials (brown/green/white) with positive values.

    v2 determinism protocol (§4.4/§4.7, user-approved 2026-11-14):
    ``solver_solution_limit`` (int >= 1) is the **primary stopping criterion**
    — a fixed solution budget with no wall-clock dependence, so repeated
    solves that reach it return identical results. ``solver_time_limit_s``
    is a **safety cap only**: if it fires before the solution budget, the
    solve is reported as ``timeout`` (explicitly non-reproducible, §4.7).
    """

    max_shift_minutes: int  # minutes [demo assumption, brief §3 category]
    densities_kg_per_litre: dict[MaterialType, float]  # kg/litre [demo assumption]
    detour_factor: float  # dimensionless >= 1 [demo assumption]
    avg_speed_kmh: float  # km/h [demo assumption]
    # §4.6 v2 defaults (200 solutions / 30.0 s), both [demo assumption].
    solver_solution_limit: int = 200
    solver_time_limit_s: float = 30.0

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
