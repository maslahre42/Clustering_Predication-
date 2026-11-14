"""Central configuration. Every value here is a *setting*, not a fact.

Values marked PLACEHOLDER must be replaced with real PreZero numbers
(truck data, container sizes, depot and disposal-site locations).
"""
from __future__ import annotations
from dataclasses import dataclass, asdict


@dataclass
class OpsConfig:
    # --- waste stream and containers (PLACEHOLDER values) -------------
    container_volume_m3: float = 3.0      # volume of one glass container
    glass_density_t_m3: float = 0.35      # bulk density of collected glass

    # --- fleet (PLACEHOLDER values) -----------------------------------
    truck_volume_m3: float = 20.0         # loading volume per trip
    truck_payload_t: float = 12.0         # weight limit per trip
    max_vehicles: int = 8
    vehicle_fixed_cost_min: float = 480.0 # fleet-size priority: one extra truck "costs" this many minutes of driving

    # --- shift and driving --------------------------------------------
    shift_hours: float = 8.0              # max working time per driver
    avg_speed_kph: float = 25.0
    detour_factor: float = 1.3            # road distance = straight line * factor
    service_min_per_stop: float = 4.0     # parking, setup
    service_min_per_bin: float = 3.0      # emptying one container
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
        return self.truck_volume_m3 * 1000.0

    @property
    def truck_payload_kg(self):
        return self.truck_payload_t * 1000.0


MATERIALS = ["white", "green", "brown"]
