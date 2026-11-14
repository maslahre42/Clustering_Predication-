"""Central configuration. Every value here is a *setting*, not a fact.

Values marked PREZERO were given by PreZero at the hackathon (14 Nov 2026).
Values marked PLACEHOLDER are still our own assumptions.
"""
from __future__ import annotations
from dataclasses import dataclass, asdict


@dataclass
class OpsConfig:
    # --- waste stream and containers ----------------------------------
    container_volume_m3: float = 3.0      # PREZERO: all containers are the same size, 3 m3
    glass_density_t_m3: float = 0.35      # PLACEHOLDER: bulk density of collected glass

    # --- fleet ----------------------------------------------------------
    truck_volume_m3: float = 0.0          # PREZERO: volume unknown, only the 12 t limit counts; 0 = no volume limit
    truck_payload_t: float = 12.0         # PREZERO: up to 12 t; one truck takes all three glass colours
    max_vehicles: int = 12                # PREZERO: enough trucks are available, so this is only an upper bound
    vehicle_fixed_cost_min: float = 480.0 # fleet-size priority: one extra truck "costs" this many minutes of driving

    # --- shift and driving --------------------------------------------
    shift_hours: float = 8.0              # PREZERO: 8 hour shift (maybe 9)
    fixed_travel_min: float = 10.0        # PREZERO: no coordinates, assume 10 minutes between containers; 0 = use coordinates
    working_weekdays: tuple = (0, 1, 2, 3, 4)   # PREZERO: Monday to Friday, no collection on Saturday and Sunday
    avg_speed_kph: float = 25.0
    detour_factor: float = 1.3            # road distance = straight line * factor
    service_min_per_stop: float = 0.0     # extra time per stop on top of driving (parking, setup)
    service_min_per_bin: float = 5.0      # PREZERO: emptying one container into the truck takes about 5 minutes
    unload_min: float = 15.0              # unloading at the disposal site

    # --- locations (PLACEHOLDER, Heilbronn area) -----------------------
    depot_lat: float = 49.1280
    depot_lon: float = 9.2030
    disposal_lat: float = 49.1650
    disposal_lon: float = 9.2350

    # --- selection policy ---------------------------------------------
    lookahead_days: int = 1               # "must be emptied before it overflows within N days"
    must_p: float = 0.70                  # P(overflow within lookahead) that makes a visit mandatory
    bin_p_collect: float = 0.12           # empty a bin at a visited site if P(overflow) >= this ...
    bin_fill_collect: float = 40.0        # ... or its expected fill is >= this (%)
    opt_p: float = 0.40                   # site becomes an optional stop if P(overflow) >= this
    opt_value_min: float = 15.0           # minutes of detour we accept for a "sure" optional stop

    def to_dict(self):
        return asdict(self)

    @property
    def truck_volume_l(self):
        return self.truck_volume_m3 * 1000.0 if self.truck_volume_m3 > 0 else 1e9

    @property
    def truck_payload_kg(self):
        return self.truck_payload_t * 1000.0


MATERIALS = ["white", "green", "brown"]
