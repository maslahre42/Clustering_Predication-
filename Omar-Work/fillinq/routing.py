"""Route engine: choose which sites to visit and route the trucks (OR-Tools).

One planning day:
  * Every candidate site is a stop with a volume (litres) and a weight (kg)
    derived from the bins that will be emptied there.
  * Mandatory stops (about to overflow) must be served; optional stops are
    served only if the detour is cheaper than their value (prize-collecting VRP).
  * Trucks have a volume AND a weight limit and a shift length. When a truck
    is full it drives to the disposal site, unloads, and continues (multi-trip),
    which is modelled with optional "reload" copies of the disposal node.
  * Each route ends with a final unload and the drive back to the depot, which
    is subtracted from the shift budget.
  * The solver minimises driving + service time plus a fixed cost per truck,
    so the number of trucks used is the fleet recommendation.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from ortools.constraint_solver import pywrapcp, routing_enums_pb2

from .config import OpsConfig
from .geo import road_km_matrix

MUST_PENALTY = 10_000_000


@dataclass
class Plan:
    routes: list            # list of dicts, one per truck
    dropped_optional: list  # site ids not visited (optional)
    dropped_mandatory: list  # site ids that could not be scheduled (infeasible)
    kpis: dict
    reasons: dict = field(default_factory=dict)


def site_demand(bins: pd.DataFrame, cfg: OpsConfig):
    """bins: columns site, fill (expected % at collection). Returns litres, kg per site."""
    vol_l = bins["fill"].clip(0, 100) / 100.0 * cfg.container_volume_m3 * 1000.0
    kg = vol_l / 1000.0 * cfg.glass_density_t_m3 * 1000.0
    out = pd.DataFrame({"site": bins["site"], "vol_l": vol_l, "kg": kg})
    return out.groupby("site").sum()


def _solve(stops: pd.DataFrame, cfg: OpsConfig, V: int, time_limit_s: int) -> Plan:
    stops = stops.reset_index(drop=True)
    n = len(stops)
    empty_kpis = dict(trucks=0, trips=0, stops=0, bins=0, km=0.0, hours=0.0, volume_m3=0.0, weight_t=0.0)
    if n == 0:
        return Plan([], [], [], empty_kpis)

    cap_v, cap_w = int(math.floor(cfg.truck_volume_l)), int(math.floor(cfg.truck_payload_kg))
    # Round demand upward and capacity downward: never understate load feasibility.
    vol = np.ceil(stops["vol_l"].to_numpy()).astype(int)
    wgt = np.ceil(stops["kg"].to_numpy()).astype(int)

    # number of reload (disposal) copies we allow
    trips_needed = max(math.ceil(vol.sum() / cap_v), math.ceil(wgt.sum() / cap_w), 1)
    n_reload = int(min(trips_needed + V, 30))

    # nodes: 0 depot | 1..n stops | n+1..n+R reload | n+R+1 end (disposal)
    R = n_reload
    N = 1 + n + R + 1
    lat = np.concatenate([[cfg.depot_lat], stops["lat"], np.full(R, cfg.disposal_lat), [cfg.disposal_lat]])
    lon = np.concatenate([[cfg.depot_lon], stops["lon"], np.full(R, cfg.disposal_lon), [cfg.disposal_lon]])
    if cfg.fixed_travel_min > 0:
        # PreZero: no coordinates, every drive between two different places takes a fixed time
        place = np.concatenate([[0], np.arange(1, n + 1), np.full(R + 1, n + 1)])
        travel_s = np.where(place[:, None] != place[None, :], cfg.fixed_travel_min * 60.0, 0.0)
        km = travel_s / 3600.0 * cfg.avg_speed_kph
    else:
        km = road_km_matrix(lat, lon, cfg)
        travel_s = km / cfg.avg_speed_kph * 3600.0

    service = np.zeros(N)
    nb = stops["n_bins"].to_numpy()
    service[1:1 + n] = (cfg.service_min_per_stop + cfg.service_min_per_bin * nb) * 60
    service[1 + n:1 + n + R] = cfg.unload_min * 60

    ret_s = travel_s[N - 1, 0]                       # disposal -> depot
    shift_s = int(cfg.shift_hours * 3600 - cfg.unload_min * 60 - ret_s)
    if shift_s < 0:
        raise ValueError("Shift too short for the distance depot -> disposal -> depot.")

    manager = pywrapcp.RoutingIndexManager(N, V, [0] * V, [N - 1] * V)
    routing = pywrapcp.RoutingModel(manager)

    def time_cb(i, j):
        a, b = manager.IndexToNode(i), manager.IndexToNode(j)
        return int(travel_s[a, b] + service[a])
    t_idx = routing.RegisterTransitCallback(time_cb)
    routing.SetArcCostEvaluatorOfAllVehicles(t_idx)
    routing.SetFixedCostOfAllVehicles(int(cfg.vehicle_fixed_cost_min * 60))
    routing.AddDimension(t_idx, 0, shift_s, True, "Time")

    reload_nodes = set(range(1 + n, 1 + n + R))

    def add_cap_dim(name, demand, cap):
        def cb(i):
            a = manager.IndexToNode(i)
            return -int(demand[a - 1]) if 1 <= a <= n else 0
        idx = routing.RegisterUnaryTransitCallback(cb)
        routing.AddDimension(idx, cap, cap, False, name)   # "remaining capacity"
        dim = routing.GetDimensionOrDie(name)
        for v in range(V):
            dim.CumulVar(routing.Start(v)).SetValue(cap)
        for node in range(N):
            if node in reload_nodes:
                continue
            if node in (0, N - 1):
                continue
            dim.SlackVar(manager.NodeToIndex(node)).SetRange(0, 0)
        dim.SlackVar(routing.Start(0))  # touch to keep API happy
        return dim
    add_cap_dim("Vol", vol, cap_v)
    add_cap_dim("Wgt", wgt, cap_w)
    # start/end nodes never take slack either
    for name in ("Vol", "Wgt"):
        dim = routing.GetDimensionOrDie(name)
        for v in range(V):
            dim.SlackVar(routing.Start(v)).SetRange(0, 0)

    must = stops["must"].to_numpy()
    value = stops["value"].to_numpy()
    for i in range(n):
        node = 1 + i
        if must[i]:
            pen = int(MUST_PENALTY * (1 + float(np.clip(value[i], 0, 1))))
        else:
            pen = int(service[node] + max(value[i], 0.0) * cfg.opt_value_min * 60)
        routing.AddDisjunction([manager.NodeToIndex(node)], pen)
    for node in reload_nodes:
        routing.AddDisjunction([manager.NodeToIndex(node)], 0)

    sp = pywrapcp.DefaultRoutingSearchParameters()
    sp.first_solution_strategy = routing_enums_pb2.FirstSolutionStrategy.PARALLEL_CHEAPEST_INSERTION
    sp.local_search_metaheuristic = routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
    sp.time_limit.FromSeconds(max(int(time_limit_s), 1))
    sol = routing.SolveWithParameters(sp)
    if sol is None:
        return Plan([], stops.loc[~stops["must"].astype(bool), "site"].tolist(),
                    stops.loc[stops["must"].astype(bool), "site"].tolist(), empty_kpis,
                    {site:'solver_no_solution' for site in stops['site']})

    sites = stops["site"].tolist()
    routes, visited = [], set()
    tot_km = tot_h = tot_vol = tot_w = 0.0
    trips_total = bins_total = 0
    for v in range(V):
        index = routing.Start(v)
        seq = []
        while not routing.IsEnd(index):
            seq.append(manager.IndexToNode(index))
            index = sol.Value(routing.NextVar(index))
        seq.append(manager.IndexToNode(index))
        if not any(1 <= x <= n for x in seq):
            continue
        # distance/time of the route incl. final unload and return to depot
        r_km = sum(km[a, b] for a, b in zip(seq[:-1], seq[1:])) + km[N - 1, 0]
        r_s = sum(travel_s[a, b] + service[a] for a, b in zip(seq[:-1], seq[1:])) + cfg.unload_min * 60 + ret_s
        trips, cur, cur_v, cur_w = [], [], 0.0, 0.0
        for node in seq:
            if 1 <= node <= n:
                cur.append(sites[node - 1]); cur_v += vol[node - 1]; cur_w += wgt[node - 1]
                visited.add(sites[node - 1])
            elif node in reload_nodes or node == N - 1:
                if cur:
                    trips.append({"stops": cur, "volume_m3": cur_v / 1000, "weight_t": cur_w / 1000})
                cur, cur_v, cur_w = [], 0.0, 0.0
        r_stops = [(sites[x - 1], float(lat[x]), float(lon[x])) for x in seq if 1 <= x <= n]
        route_bins = int(sum(nb[x - 1] for x in seq if 1 <= x <= n))
        routes.append({
            "truck": len(routes) + 1,
            "stops": r_stops,
            "path": [(float(lat[x]), float(lon[x]), "depot" if x == 0 else ("disposal" if x >= 1 + n else sites[x - 1])) for x in seq] + [(cfg.depot_lat, cfg.depot_lon, "depot")],
            "trips": trips,
            "km": float(r_km), "hours": float(r_s / 3600),
            "bins": route_bins,
        })
        tot_km += r_km; tot_h += r_s / 3600
        tot_vol += sum(t["volume_m3"] for t in trips); tot_w += sum(t["weight_t"] for t in trips)
        trips_total += len(trips); bins_total += route_bins
    dropped = [s for s in sites if s not in visited]
    must_set = set(stops.loc[stops["must"], "site"])
    kp = dict(trucks=len(routes), trips=trips_total, stops=len(visited), bins=bins_total,
              km=float(tot_km), hours=float(tot_h), volume_m3=float(tot_vol), weight_t=float(tot_w))
    return Plan(routes, [s for s in dropped if s not in must_set], [s for s in dropped if s in must_set], kp)


def _lower_bound_trucks(stops: pd.DataFrame, cfg: OpsConfig) -> int:
    """Rough minimum number of trucks: total work time (service, unloading, depot-disposal legs)
    divided by the shift, with a margin for driving between stops."""
    from .geo import haversine_km
    vol, kg = stops["vol_l"].clip(upper=cfg.truck_volume_l), stops["kg"].clip(upper=cfg.truck_payload_kg)
    trips = max(math.ceil(vol.sum() / cfg.truck_volume_l), math.ceil(kg.sum() / cfg.truck_payload_kg), 1)
    if cfg.fixed_travel_min > 0:
        t_dd = cfg.fixed_travel_min * 60
        drive = len(stops) * cfg.fixed_travel_min * 60
    else:
        t_dd = haversine_km(cfg.depot_lat, cfg.depot_lon, cfg.disposal_lat, cfg.disposal_lon) * cfg.detour_factor / cfg.avg_speed_kph * 3600
        drive = 0.0
    service = ((cfg.service_min_per_stop + cfg.service_min_per_bin * stops["n_bins"]) * 60).sum()
    work = service + drive + trips * (cfg.unload_min * 60 + t_dd) + (0.0 if drive else 0.15 * service)
    return max(1, math.ceil(work / (cfg.shift_hours * 3600)))


def plan_routes(stops: pd.DataFrame, cfg: OpsConfig, time_limit_s: int = 3, seed: int = 0) -> Plan:
    """stops columns: site, lat, lon, vol_l, kg, n_bins, must(bool), value(0..1).
    Starts with a small fleet (so the solver packs routes) and adds trucks only if
    mandatory stops can not be scheduled. Empty input gives an empty plan."""
    stops = stops.reset_index(drop=True)
    if len(stops) == 0:
        return Plan([], [], [], dict(trucks=0, trips=0, stops=0, bins=0, km=0.0, hours=0.0, volume_m3=0.0, weight_t=0.0))
    from .geo import haversine_km
    solo_drive = (3 * cfg.fixed_travel_min if cfg.fixed_travel_min > 0 else
        (haversine_km(cfg.depot_lat,cfg.depot_lon,stops['lat'],stops['lon']) +
         haversine_km(stops['lat'],stops['lon'],cfg.disposal_lat,cfg.disposal_lon) +
         haversine_km(cfg.disposal_lat,cfg.disposal_lon,cfg.depot_lat,cfg.depot_lon)) * cfg.detour_factor / cfg.avg_speed_kph * 60)
    impossible = ((stops["vol_l"] > cfg.truck_volume_l) | (stops["kg"] > cfg.truck_payload_kg) |
        (solo_drive + cfg.service_min_per_stop + stops['n_bins'] * cfg.service_min_per_bin + cfg.unload_min > cfg.shift_hours*60))
    if impossible.any():
        eligible = stops.loc[~impossible].reset_index(drop=True)
        result = plan_routes(eligible, cfg, time_limit_s, seed)
        rejected = stops.loc[impossible]
        result.dropped_mandatory.extend(rejected.loc[rejected["must"].astype(bool), "site"].tolist())
        result.dropped_optional.extend(rejected.loc[~rejected["must"].astype(bool), "site"].tolist())
        for row in rejected.itertuples():
            result.reasons[row.site] = ('exceeds_truck_capacity' if row.kg > cfg.truck_payload_kg or row.vol_l > cfg.truck_volume_l else 'exceeds_shift')
        return result
    must = stops[stops["must"].astype(bool)]
    lb = _lower_bound_trucks(must if len(must) else stops, cfg)
    tries = []
    for v in (lb, lb + 1, lb + 2, lb + 4, cfg.max_vehicles):
        v = int(min(max(v, 1), cfg.max_vehicles))
        if v not in tries:
            tries.append(v)
    plan = None
    for v in tries:
        plan = _solve(stops, cfg, v, time_limit_s)
        if not plan.dropped_mandatory:
            break
    return plan
