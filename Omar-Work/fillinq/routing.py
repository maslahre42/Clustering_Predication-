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
from .territories import compact_sectors
from .roads import RoadRoutingError

MUST_PENALTY = 10_000_000
MATERIALS = ('brown', 'green', 'white')


def compartment_capacities(cfg):
    caps = getattr(cfg, 'compartment_litres', {})
    if caps and (set(caps) != set(MATERIALS) or any(not math.isfinite(v) or v < 1 for v in caps.values())):
        raise ValueError('Configure all three glass compartments with at least one litre each, or leave the layout unknown.')
    return caps


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
    if 'material' in bins:
        for material in MATERIALS:
            out[f'{material}_l'] = vol_l.where(bins['material'].eq(material), 0)
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
    compartments = compartment_capacities(cfg)
    material_volumes = {material: np.ceil(stops[f'{material}_l'].to_numpy()).astype(int)
                        for material in MATERIALS if f'{material}_l' in stops}

    # number of reload (disposal) copies we allow
    trips_needed = max(math.ceil(vol.sum() / cap_v), math.ceil(wgt.sum() / cap_w), 1)
    if compartments:
        trips_needed = max(trips_needed, *(math.ceil(material_volumes[m].sum() / math.floor(cap)) for m, cap in compartments.items()))
    n_reload = int(min(trips_needed + V, 30))

    # nodes: 0 depot | 1..n stops | n+1..n+R reload | n+R+1 end (disposal)
    R = n_reload
    N = 1 + n + R + 1
    lat = np.concatenate([[cfg.depot_lat], stops["lat"], np.full(R, cfg.disposal_lat), [cfg.disposal_lat]])
    lon = np.concatenate([[cfg.depot_lon], stops["lon"], np.full(R, cfg.disposal_lon), [cfg.disposal_lon]])
    road = getattr(cfg, 'road_network', None)
    if road is not None:
        km, travel_s, _ = road.matrix(lat, lon)
        if not np.isfinite(km).all() or not np.isfinite(travel_s).all():
            raise RoadRoutingError('Some selected locations are not connected by driveable streets.')
    elif cfg.fixed_travel_min > 0:
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
        # Fractional travel seconds must never make an over-length route appear feasible.
        return int(math.ceil(travel_s[a, b] + service[a]))
    t_idx = routing.RegisterTransitCallback(time_cb)
    if road is not None:
        # Money spent on kilometers: distance is the objective; actual driving time is a hard shift constraint.
        distance_idx = routing.RegisterTransitCallback(lambda i, j: int(math.ceil(km[manager.IndexToNode(i), manager.IndexToNode(j)] * 1000)))
        routing.SetArcCostEvaluatorOfAllVehicles(distance_idx)
        routing.SetFixedCostOfAllVehicles(int(math.ceil(km[N - 1, 0] * 1000)))
        sectors = compact_sectors(stops, V, cfg, travel_s, km)
        for i, sector in enumerate(sectors):
            # Keep -1 for a genuinely unserved stop; one truck owns the sector across all its loads.
            routing.VehicleVar(manager.NodeToIndex(i + 1)).SetValues([-1, int(sector)])
    else:
        routing.SetArcCostEvaluatorOfAllVehicles(t_idx)
        routing.SetFixedCostOfAllVehicles(int(math.ceil(cfg.vehicle_fixed_cost_min * 60 + cfg.unload_min * 60 + ret_s)))
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
    capacity_names = ['Vol', 'Wgt']
    for material, cap in compartments.items():
        name = f'Glass_{material}'
        add_cap_dim(name, material_volumes[material], int(math.floor(cap)))
        capacity_names.append(name)
    # start/end nodes never take slack either
    for name in capacity_names:
        dim = routing.GetDimensionOrDie(name)
        for v in range(V):
            dim.SlackVar(routing.Start(v)).SetRange(0, 0)

    must = stops["must"].to_numpy()
    value = stops["value"].to_numpy()
    for i in range(n):
        node = 1 + i
        if must[i]:
            pen = int(MUST_PENALTY * (1000 if road is not None else 1) * (1 + float(np.clip(value[i], 0, 1))))
        else:
            pen = int(service[node] + max(value[i], 0.0) * cfg.opt_value_min * 60)
            if road is not None:
                # Optional service value remains a time budget, converted using this road matrix's average speed.
                moving = travel_s > 0
                pen = int(max(value[i], 0.0) * cfg.opt_value_min * 60 * (km[moving].sum() * 1000 / max(1, travel_s[moving].sum())))
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
        cur_material = {material: 0.0 for material in material_volumes}
        for node in seq:
            if 1 <= node <= n:
                cur.append(sites[node - 1]); cur_v += vol[node - 1]; cur_w += wgt[node - 1]
                visited.add(sites[node - 1])
                for material, amounts in material_volumes.items(): cur_material[material] += float(amounts[node - 1])
            elif node in reload_nodes or node == N - 1:
                if cur:
                    trips.append({"stops": cur, "volume_m3": cur_v / 1000, "weight_t": cur_w / 1000,
                                  'volume_by_material_l': dict(cur_material) if len(cur_material) == 3 else None})
                cur, cur_v, cur_w = [], 0.0, 0.0
                cur_material = {material: 0.0 for material in material_volumes}
        r_stops = [(sites[x - 1], float(lat[x]), float(lon[x])) for x in seq if 1 <= x <= n]
        route_bins = int(sum(nb[x - 1] for x in seq if 1 <= x <= n))
        territory = None
        if road is not None:
            group = stops.loc[sectors == v]
            bearing = (math.degrees(math.atan2((group['lon'].mean() - cfg.disposal_lon) * math.cos(math.radians(cfg.disposal_lat)),
                                               group['lat'].mean() - cfg.disposal_lat)) + 360) % 360
            direction = ['North', 'North-east', 'East', 'South-east', 'South', 'South-west', 'West', 'North-west'][int((bearing + 22.5) // 45) % 8]
            territory = f'{direction} · Sector {v + 1}'
        routes.append({
            "truck": len(routes) + 1,
            "stops": r_stops,
            "path": [(float(lat[x]), float(lon[x]), "depot" if x == 0 else ("disposal" if x >= 1 + n else sites[x - 1])) for x in seq] + [(cfg.depot_lat, cfg.depot_lon, "depot")],
            "trips": trips,
            "km": float(r_km), "hours": float(r_s / 3600),
            "bins": route_bins,
            **({'territory': territory} if road is not None else {}),
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
    road = getattr(cfg, 'road_network', None)
    if road is not None:
        lat = [cfg.depot_lat, *stops['lat'], cfg.disposal_lat]
        lon = [cfg.depot_lon, *stops['lon'], cfg.disposal_lon]
        _, seconds, _ = road.matrix(lat, lon)
        t_dd = seconds[-1, 0]
        between = seconds[1:-1, 1:-1].copy()
        np.fill_diagonal(between, np.inf)
        drive = float(np.min(between, axis=1).sum()) if len(stops) > 1 else 0.0
    elif cfg.fixed_travel_min > 0:
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
    compartments = compartment_capacities(cfg)
    material_unknown = np.zeros(len(stops), dtype=bool)
    material_oversize = np.zeros(len(stops), dtype=bool)
    if compartments:
        if not all(f'{m}_l' in stops for m in MATERIALS):
            material_unknown[:] = True
        else:
            amounts = stops[[f'{m}_l' for m in MATERIALS]].to_numpy(dtype=float)
            material_unknown = (~np.isfinite(amounts).all(axis=1) | (amounts < 0).any(axis=1)
                                | ~np.isclose(amounts.sum(axis=1), stops['vol_l'].to_numpy(), atol=.001, rtol=1e-8))
            material_oversize = (np.ceil(amounts) > np.array([math.floor(compartments[m]) for m in MATERIALS])).any(axis=1)
    from .geo import haversine_km
    road = getattr(cfg, 'road_network', None)
    unavailable = np.zeros(len(stops), dtype=bool)
    if road is not None:
        _, seconds, access = road.matrix([cfg.depot_lat, *stops['lat'], cfg.disposal_lat], [cfg.depot_lon, *stops['lon'], cfg.disposal_lon])
        if access[0][2] > road.max_snap_m or access[-1][2] > road.max_snap_m or not np.isfinite(seconds[-1, 0]):
            raise RoadRoutingError('The yard or unloading site has no nearby connected driving access. Check their coordinates.')
        solo_drive = (seconds[0, 1:-1] + seconds[1:-1, -1] + seconds[-1, 0]) / 60
        unavailable = np.array([point[2] > road.max_snap_m for point in access[1:-1]]) | ~np.isfinite(solo_drive)
    else:
        solo_drive = (3 * cfg.fixed_travel_min if cfg.fixed_travel_min > 0 else
        (haversine_km(cfg.depot_lat,cfg.depot_lon,stops['lat'],stops['lon']) +
         haversine_km(stops['lat'],stops['lon'],cfg.disposal_lat,cfg.disposal_lon) +
         haversine_km(cfg.disposal_lat,cfg.disposal_lon,cfg.depot_lat,cfg.depot_lon)) * cfg.detour_factor / cfg.avg_speed_kph * 60)
    impossible = (material_unknown | material_oversize | unavailable | (stops["vol_l"] > cfg.truck_volume_l) | (stops["kg"] > cfg.truck_payload_kg) |
        (solo_drive + cfg.service_min_per_stop + stops['n_bins'] * cfg.service_min_per_bin + cfg.unload_min > cfg.shift_hours*60))
    if impossible.any():
        eligible = stops.loc[~impossible].reset_index(drop=True)
        result = plan_routes(eligible, cfg, time_limit_s, seed)
        rejected = stops.loc[impossible]
        result.dropped_mandatory.extend(rejected.loc[rejected["must"].astype(bool), "site"].tolist())
        result.dropped_optional.extend(rejected.loc[~rejected["must"].astype(bool), "site"].tolist())
        for row in rejected.itertuples():
            result.reasons[row.site] = ('material_demand_unknown' if material_unknown[row.Index] else 'exceeds_compartment_capacity' if material_oversize[row.Index]
                else 'road_unreachable' if unavailable[row.Index] else 'exceeds_truck_capacity' if row.kg > cfg.truck_payload_kg or row.vol_l > cfg.truck_volume_l else 'exceeds_shift')
        return result
    must = stops[stops["must"].astype(bool)]
    lb = _lower_bound_trucks(must if len(must) else stops, cfg)
    tries = []
    for v in (lb, lb + 1, lb + 2, lb + 4, cfg.max_vehicles):
        v = int(min(max(v, 1), cfg.max_vehicles))
        if v not in tries:
            tries.append(v)
    plan, best, best_score = None, None, None
    for v in tries:
        plan = _solve(stops, cfg, v, time_limit_s)
        score = (len(plan.dropped_mandatory), plan.kpis['km'] if road is not None else plan.kpis['hours'], len(plan.dropped_optional))
        if best_score is None or score < best_score:
            best, best_score = plan, score
        if not plan.dropped_mandatory:
            break
    return best
