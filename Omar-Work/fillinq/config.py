"""Central configuration. Every value here is a *setting*, not a fact.

Values marked PREZERO were given by PreZero at the hackathon (14 Nov 2026).
Values marked PLACEHOLDER are still our own assumptions.
"""
from __future__ import annotations
import json
import os
from dataclasses import dataclass, asdict, fields


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


# ---------------------------------------------------------------- settings file
SETTINGS_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "settings.json")

# What the Settings page shows. source: "PreZero" = given by PreZero on 14 Nov 2026,
# "Assumption" = our own value until PreZero provides one, "Planner" = tuning of the planning logic.
# (key, label, unit, min, max, step, source, explanation)
PARAMS = [
    ("Containers and glass", [
        ("container_volume_m3", "Container volume", "m3", 0.5, 10.0, 0.5, "PreZero",
         "All containers are the same size."),
        ("glass_density_t_m3", "Glass density", "t per m3", 0.1, 1.5, 0.05, "Assumption",
         "Turns fill level into weight. A full container weighs volume x density, so this decides how many containers fit in one load."),
    ]),
    ("Trucks", [
        ("truck_payload_t", "Truck payload per load", "t", 2.0, 30.0, 0.5, "PreZero",
         "Weight limit of one load. One truck takes all three glass colours."),
        ("truck_volume_m3", "Truck volume per load", "m3", 0.0, 60.0, 1.0, "Assumption",
         "0 means no volume limit, so only the weight limit counts. Set it when the truck volume is known."),
        ("max_vehicles", "Trucks available", "trucks", 1, 30, 1, "PreZero",
         "Upper bound only. The planner recommends the fewest trucks that do the job."),
    ]),
    ("Working time", [
        ("shift_hours", "Shift length", "hours", 4.0, 12.0, 0.5, "PreZero",
         "Maximum working time of one truck per day, including the last unloading and the return."),
        ("fixed_travel_min", "Driving time between containers", "minutes", 0.0, 60.0, 1.0, "PreZero",
         "Used for every drive, also to the depot and the unloading site. 0 means: use the coordinates of an uploaded location file."),
        ("service_min_per_bin", "Time to empty one container", "minutes", 0.0, 20.0, 0.5, "PreZero", ""),
        ("service_min_per_stop", "Extra time per stop", "minutes", 0.0, 20.0, 0.5, "Assumption",
         "Parking and setup on top of driving and emptying."),
        ("unload_min", "Time for one unloading", "minutes", 0.0, 60.0, 1.0, "Assumption",
         "At the unloading site, each time a truck is full and at the end of the day."),
        ("avg_speed_kph", "Average speed", "km/h", 10.0, 60.0, 1.0, "Assumption",
         "Only used to show kilometres, or with real coordinates."),
    ]),
    ("Planning rules", [
        ("lookahead_days", "Look-ahead", "collection days", 1, 7, 1, "Planner",
         "1 = empty today what would overflow before the next collection day."),
        ("must_p", "Overflow risk that makes a stop mandatory", "0 to 1", 0.1, 0.95, 0.01, "Planner",
         "Lower = more cautious: more visits, less overflow."),
        ("bin_fill_collect", "Also empty neighbours at the same site from this fill level", "%", 0.0, 100.0, 5.0, "Planner",
         "When a truck is at a site anyway, other containers there are emptied if they are at least this full."),
        ("vehicle_fixed_cost_min", "Preference for fewer trucks", "minutes per extra truck", 0.0, 1000.0, 30.0, "Planner",
         "Higher = the planner tries harder to use fewer trucks."),
    ]),
]
WEEKDAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def config_from_dict(d: dict) -> OpsConfig:
    """Build a config from a dict, ignoring unknown keys and keeping defaults for missing ones."""
    cfg = OpsConfig()
    for f in fields(OpsConfig):
        if f.name not in d or d[f.name] is None:
            continue
        v = d[f.name]
        if f.name == "working_weekdays":
            v = tuple(sorted(int(x) for x in v)) or (0, 1, 2, 3, 4)
        elif isinstance(getattr(cfg, f.name), int):
            v = int(v)
        else:
            v = float(v)
        setattr(cfg, f.name, v)
    return cfg


def load_settings(path: str = SETTINGS_PATH) -> OpsConfig:
    """Saved settings if settings.json exists, otherwise the defaults."""
    try:
        with open(path) as fh:
            return config_from_dict(json.load(fh))
    except (OSError, ValueError, TypeError):
        return OpsConfig()


def save_settings(cfg: OpsConfig, path: str = SETTINGS_PATH) -> None:
    d = cfg.to_dict()
    d["working_weekdays"] = list(cfg.working_weekdays)
    with open(path, "w") as fh:
        json.dump(d, fh, indent=2)
