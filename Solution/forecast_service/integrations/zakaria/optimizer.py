"""Compact two-index Gurobi CVRP: yard -> sites -> disposal -> yard.

All supplied sites are required. One load per truck; no silent site clipping,
subset selection or mid-route unloading. Fleet size has objective priority over distance.
"""
from dataclasses import dataclass, field
import math
import numpy as np
import pandas as pd


ROUTE_COLUMNS = ['vehicle', 'num_stops', 'num_bins', 'ordered_stop_indices', 'ordered_locations',
                 'total_volume_m3', 'volume_utilization_pct', 'total_weight_kg',
                 'weight_utilization_pct', 'total_distance_km', 'shift_hours']


@dataclass
class RoutingResult:
    status: str
    message: str
    routes: pd.DataFrame = field(default_factory=lambda: pd.DataFrame(columns=ROUTE_COLUMNS))
    unserved: pd.DataFrame = field(default_factory=lambda: pd.DataFrame(columns=['Location_id', 'reason']))
    model_stats: dict = field(default_factory=dict)
    distance_provenance: str = ''
    fleet_lower_bound: int = 0
    runtime_seconds: float = 0.0

    @property
    def complete(self):
        return self.status in ('optimal', 'feasible', 'empty') and self.unserved.empty


def solve_collection_routes(candidates_df, dist_provider, waste_density_kg_m3=350.0,
                           container_volume_m3=3.0, truck_max_volume_m3=18.0,
                           truck_max_weight_kg=12000.0, max_shift_hours=8.0,
                           max_fleet_vehicles=4, avg_speed_kmh=28.0,
                           service_time_min=5.0, unloading_time_min=15.0,
                           time_limit_sec=20, mip_gap=0.02, service_time_per_stop_min=0.0, compartment_capacities_m3=None):
    for name, value in [('density', waste_density_kg_m3), ('container_volume', container_volume_m3),
                        ('truck_volume', truck_max_volume_m3), ('truck_payload', truck_max_weight_kg),
                        ('shift', max_shift_hours), ('speed', avg_speed_kmh), ('time_limit', time_limit_sec)]:
        if isinstance(value, bool) or not np.isfinite(value) or value <= 0:
            raise ValueError(f'{name} must be positive and finite.')
    if isinstance(max_fleet_vehicles, bool) or not isinstance(max_fleet_vehicles, int) or max_fleet_vehicles < 1:
        raise ValueError('max_fleet_vehicles must be a positive integer.')
    if not all(np.isfinite(v) and v >= 0 for v in (service_time_min, service_time_per_stop_min, unloading_time_min, mip_gap)) or mip_gap > 1:
        raise ValueError('Service/unloading must be nonnegative; mip_gap must be in [0,1].')
    df = candidates_df.reset_index(drop=True).copy()
    if 'Location_id' not in df or df['Location_id'].duplicated().any():
        raise ValueError('Candidates need one unique row per physical site.')
    if df['Location_id'].tolist() != dist_provider.location_ids:
        raise ValueError('Distance-provider IDs/order must exactly match candidates.')
    n = len(df)
    provenance = dist_provider.distance_provenance
    if not n:
        return RoutingResult('empty', 'No selected sites.', distance_provenance=provenance)
    if 'demand_volume_m3' in df:
        vol = df['demand_volume_m3'].to_numpy(dtype=float)
        wt = df['demand_weight_kg'].to_numpy(dtype=float)
    else:
        fill = df['predicted_fill_perc'].to_numpy(dtype=float)
        if not np.isfinite(fill).all() or ((fill < 0) | (fill > 100)).any():
            raise ValueError('Predicted fill must be finite within 0..100.')
        vol = fill / 100 * container_volume_m3
        wt = vol * waste_density_kg_m3
    if not np.isfinite(vol).all() or not np.isfinite(wt).all() or (vol < 0).any() or (wt < 0).any():
        raise ValueError('Demand must be finite and nonnegative; unknown bins cannot be routed.')
    if not np.allclose(wt, vol*waste_density_kg_m3, rtol=1e-7, atol=1e-7):
        raise ValueError('Demand weight/density differs from routing configuration.')
    nb = df['n_bins'].to_numpy(dtype=float) if 'n_bins' in df else np.ones(n)
    if not np.isfinite(nb).all() or (nb < 1).any() or (nb != np.floor(nb)).any():
        raise ValueError('n_bins must be positive integers.')
    caps = compartment_capacities_m3 or {}
    materials = ('brown','green','white')
    demands = {}
    if caps:
        if set(caps) != set(materials) or any(not np.isfinite(v) or v < .001 for v in caps.values()):
            raise ValueError('Configure all three material compartments with positive capacities.')
        for material in materials:
            if f'{material}_m3' not in df:
                raise ValueError('Material demand is required for configured compartments.')
            demands[material] = df[f'{material}_m3'].to_numpy(dtype=float)
            if not np.isfinite(demands[material]).all() or (demands[material] < 0).any():
                raise ValueError('Material demand must be finite and nonnegative.')
        if not np.allclose(sum(demands.values()), vol, atol=1e-7, rtol=1e-7):
            raise ValueError('Material demand must sum to total volume.')
    service = nb * service_time_min + service_time_per_stop_min
    shift = max_shift_hours * 60
    if hasattr(dist_provider, 'road_duration_minutes'):
        depot_t, disposal_t, between_t, back = dist_provider.road_duration_minutes
    else:
        back = float(dist_provider.travel_minutes(dist_provider.disposal_to_depot_km, avg_speed_kmh))
        depot_t = dist_provider.travel_minutes(dist_provider.depot_dist, avg_speed_kmh)
        disposal_t = dist_provider.travel_minutes(dist_provider.disposal_dist, avg_speed_kmh)
        between_t = dist_provider.travel_minutes(dist_provider.inter_bin_matrix, avg_speed_kmh)
    effective_volume = min(truck_max_volume_m3, truck_max_weight_kg / waste_density_kg_m3)
    lower = max(math.ceil(vol.sum()/truck_max_volume_m3-1e-10),
                math.ceil(wt.sum()/truck_max_weight_kg-1e-10), 1)

    lower = max([lower, *[math.ceil(demands[m].sum()/caps[m]-1e-10) for m in caps]])

    def failure(status, reason, **kwargs):
        return RoutingResult(status, reason, unserved=pd.DataFrame({'Location_id': df['Location_id'], 'reason': reason}),
                             distance_provenance=provenance, fleet_lower_bound=lower, **kwargs)

    oversize = (vol > truck_max_volume_m3+1e-8) | (wt > truck_max_weight_kg+1e-8)
    for material in caps:
        oversize |= demands[material] > caps[material]+1e-8
    if oversize.any():
        return failure('infeasible', f'Unsplittable sites exceed one truck capacity: {df.loc[oversize, "Location_id"].tolist()}')
    if (depot_t + service + disposal_t + unloading_time_min + back > shift+1e-8).any():
        return failure('infeasible', 'At least one required site cannot fit a complete depot/disposal round trip within the shift.')
    if lower > max_fleet_vehicles:
        return failure('infeasible', f'At least {lower} one-load trucks required; {max_fleet_vehicles} available.')

    # Compact x[i,j], not x[i,j,k]: eliminates the fleet multiplier from arcs and MTZ constraints.
    end = n+1
    nodes = range(1, n+1)
    arcs = [(0, j) for j in nodes] + [(i, end) for i in nodes]
    arcs += [(i, j) for i in nodes for j in nodes if i != j and
             depot_t[i-1] + service[i-1] + between_t[i-1,j-1] + service[j-1]
             + disposal_t[j-1] + unloading_time_min + back <= shift+1e-8]
    cost = {(i,j): (dist_provider.depot_dist[j-1] if i == 0 else
                    dist_provider.disposal_dist[i-1] if j == end else
                    dist_provider.inter_bin_matrix[i-1,j-1]) for i,j in arcs}
    stats = {'sites': n, 'arcs': len(arcs), 'legacy_arc_upper_bound': max_fleet_vehicles*(n*n+n),
             'formulation': 'two_index_cvrp', 'effective_volume_capacity_m3': effective_volume}
    try:
        import gurobipy as gp
        from gurobipy import GRB
    except ImportError:
        return failure('solver_unavailable', 'Install gurobipy and configure a valid Gurobi license.', model_stats=stats)
    try:
        with gp.Env(empty=True) as env:
            env.setParam('OutputFlag', 0)
            env.start()
            with gp.Model('Heilbronn_Smart_Glass_VRP', env=env) as model:
                model.Params.TimeLimit = time_limit_sec
                model.Params.MIPGap = mip_gap
                model.Params.Seed = 42
                model.Params.Threads = 1
                x = model.addVars(arcs, vtype=GRB.BINARY, name='arc')
                load = model.addVars(nodes, lb=0, ub=effective_volume, name='volume_load')
                material_loads = {m:model.addVars(nodes, lb=0, ub=caps[m], name=f'{m}_load') for m in caps}
                arrival = model.addVars(nodes, lb=0, ub=shift, name='arrival_min')
                order = model.addVars(nodes, lb=1, ub=n, name='order')
                departures = gp.quicksum(x[0,j] for j in nodes)
                model.addConstr(departures == gp.quicksum(x[i,end] for i in nodes))
                model.addConstr(departures <= max_fleet_vehicles)
                model.addConstr(departures >= lower)
                for i in nodes:
                    model.addConstr(x.sum('*', i) == 1)
                    model.addConstr(x.sum(i, '*') == 1)
                    model.addConstr(load[i] >= vol[i-1])
                    for material in caps:
                        model.addConstr(material_loads[material][i] >= demands[material][i-1])
                    model.addConstr(arrival[i] >= depot_t[i-1])
                    model.addConstr(arrival[i] + service[i-1] + disposal_t[i-1] + unloading_time_min + back <= shift)
                for i,j in arcs:
                    if i == 0 or j == end:
                        continue
                    model.addConstr(load[j] >= load[i] + vol[j-1] - effective_volume*(1-x[i,j]))
                    for material in caps:
                        model.addConstr(material_loads[material][j] >= material_loads[material][i] + demands[material][j-1] - caps[material]*(1-x[i,j]))
                    model.addConstr(order[j] >= order[i] + 1 - n*(1-x[i,j]))
                    travel_service = service[i-1] + between_t[i-1,j-1]
                    model.addConstr(arrival[j] >= arrival[i] + travel_service - (shift+travel_service)*(1-x[i,j]))
                model.ModelSense = GRB.MINIMIZE
                model.setObjectiveN(departures, 0, priority=2, abstol=0, reltol=0, name='fleet_first')
                model.setObjectiveN(gp.quicksum(cost[a,b]*x[a,b] for a,b in arcs) + dist_provider.disposal_to_depot_km*departures,
                                    1, priority=1, abstol=0, reltol=0, name='distance_second')
                model.optimize()
                stats.update(variables=model.NumVars, constraints=model.NumConstrs, raw_status=model.Status,
                             requested_mip_gap=mip_gap)
                runtime = model.Runtime
                if model.SolCount == 0:
                    status = 'infeasible' if model.Status == GRB.INFEASIBLE else 'time_limit' if model.Status == GRB.TIME_LIMIT else 'solver_error'
                    return failure(status, 'No feasible incumbent; all supplied sites remain unserved.', model_stats=stats, runtime_seconds=runtime)
                used = [(i,j) for i,j in arcs if x[i,j].X > 0.5]
                successor = {i:j for i,j in used if i != 0}
                starts = sorted(j for i,j in used if i == 0)
                records, seen = [], set()
                for first in starts:
                    sequence, current = [], first
                    while current != end:
                        if current in seen:
                            raise RuntimeError('Invalid repeated node in solver incumbent.')
                        seen.add(current)
                        sequence.append(current-1)
                        current = successor[current]
                    first_i, last_i = sequence[0], sequence[-1]
                    km = float(dist_provider.depot_dist[first_i] + sum(dist_provider.inter_bin_matrix[a,b] for a,b in zip(sequence,sequence[1:]))
                               + dist_provider.disposal_dist[last_i] + dist_provider.disposal_to_depot_km)
                    minutes = float(depot_t[first_i] + sum(between_t[a,b] for a,b in zip(sequence,sequence[1:]))
                                    + service[sequence].sum() + disposal_t[last_i] + unloading_time_min + back)
                    v, w = float(vol[sequence].sum()), float(wt[sequence].sum())
                    if v > truck_max_volume_m3+1e-6 or w > truck_max_weight_kg+1e-6 or minutes > shift+1e-6:
                        raise RuntimeError('Extracted route violates capacity/shift; refusing to export.')
                    if any(demands[m][sequence].sum() > caps[m]+1e-6 for m in caps):
                        raise RuntimeError('Extracted route exceeds a material compartment.')
                    records.append(dict(vehicle=f'Truck #{len(records)+1}', num_stops=len(sequence), num_bins=int(nb[sequence].sum()),
                        ordered_stop_indices=sequence, ordered_locations=df.loc[sequence,'Location_id'].tolist(),
                        total_volume_m3=v, volume_utilization_pct=v/truck_max_volume_m3*100,
                        total_weight_kg=w, weight_utilization_pct=w/truck_max_weight_kg*100,
                        total_distance_km=km, shift_hours=minutes/60))
                if len(seen) != n:
                    raise RuntimeError('Solver incumbent omitted required sites.')
                status = 'optimal' if model.Status == GRB.OPTIMAL else 'feasible'
                return RoutingResult(status, 'All supplied sites served; optimality is subject to configured tolerances and termination.',
                    routes=pd.DataFrame(records, columns=ROUTE_COLUMNS), model_stats=stats,
                    distance_provenance=provenance, fleet_lower_bound=lower, runtime_seconds=runtime)
    except gp.GurobiError as exc:
        return failure('solver_unavailable', f'Gurobi license/solver error {exc.errno}: {exc}', model_stats=stats)


def solve_gurobi_waste_vrp(candidates_df, dist_provider, **kwargs):
    """DataFrame compatibility wrapper. Explicit status/unserved are in attrs."""
    result = solve_collection_routes(candidates_df, dist_provider, **kwargs)
    result.routes.attrs.update(status=result.status, message=result.message,
                               unserved=result.unserved.to_dict('records'), model_stats=result.model_stats)
    return result.routes
