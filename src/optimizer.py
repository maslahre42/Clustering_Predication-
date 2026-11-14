import numpy as np
import pandas as pd
from typing import Dict, Any, Tuple
from .distance_provider import ModularDistanceProvider

def solve_gurobi_waste_vrp(
    candidates_df: pd.DataFrame,
    dist_provider: ModularDistanceProvider,
    waste_density_kg_m3: float = 380.0,
    container_volume_m3: float = 2.5,
    truck_max_volume_m3: float = 18.0,
    truck_max_weight_kg: float = 9000.0,
    max_shift_hours: float = 7.5,
    max_fleet_vehicles: int = 4,
    avg_speed_kmh: float = 28.0,
    service_time_min: float = 6.0,
    unloading_time_min: float = 20.0,
    time_limit_sec: int = 20
) -> pd.DataFrame:
    """
    Formulates and solves the Capacitated Vehicle Routing Problem (CVRP) using Gurobi.
    Node 0 = Central Yard (Start)
    Nodes 1..N = Glass Containers to empty
    Node N+1 = Disposal Depot (Unloading site before returning to Yard)
    """
    import gurobipy as gp
    from gurobipy import GRB

    df_c = candidates_df.reset_index(drop=True).copy()
    N = len(df_c)
    K = max_fleet_vehicles

    if N == 0:
        return pd.DataFrame()

    # Calculate volume (m3) and weight (kg) demand per stop
    fill_col = 'predicted_fill_perc' if 'predicted_fill_perc' in df_c.columns else 'current_fill_perc'
    fill_ratio = df_c[fill_col].values / 100.0
    vol_demand = fill_ratio * container_volume_m3
    wt_demand = vol_demand * waste_density_kg_m3

    # Build extended (N+2) x (N+2) distance matrix:
    # 0 = Central Yard, 1..N = Containers, N+1 = Disposal Site
    D = np.zeros((N + 2, N + 2))
    D[0, 1:N+1] = dist_provider.depot_dist[:N]
    D[1:N+1, 1:N+1] = dist_provider.inter_bin_matrix[:N, :N]
    D[1:N+1, N+1] = dist_provider.disposal_dist[:N]

    # ---------------- INITIALIZE GUROBI MODEL WITH SMART LICENSE FALLBACK ----------------
    import os
    local_lic = os.path.abspath("gurobi.lic")
    if os.path.exists(local_lic):
        os.environ['GRB_LICENSE_FILE'] = local_lic

    try:
        m = gp.Model("Heilbronn_Smart_Glass_VRP")
    except gp.GurobiError as e:
        if "expired" in str(e).lower() or "license" in str(e).lower():
            # Old/expired license detected on system (e.g. C:\Users\Zakaria\gurobi.lic)
            # Gracefully fallback to the valid bundled pip license inside .venv
            pip_lic = os.path.abspath(".venv/Lib/site-packages/gurobipy/gurobi.lic")
            if os.path.exists(pip_lic):
                print(f"[Notice] System license expired ({e}). Automatically switching to valid bundled license ({pip_lic}).")
                os.environ['GRB_LICENSE_FILE'] = pip_lic
                m = gp.Model("Heilbronn_Smart_Glass_VRP")
            else:
                raise e
        else:
            raise e

    m.Params.OutputFlag = 0
    m.Params.TimeLimit = time_limit_sec
    m.Params.MIPGap = 0.05

    # ---------------- DECISION VARIABLES ----------------
    valid_arcs = [(0, j, k) for j in range(1, N + 1) for k in range(K)] + \
                 [(i, j, k) for i in range(1, N + 1) for j in range(1, N + 1) if i != j for k in range(K)] + \
                 [(i, N + 1, k) for i in range(1, N + 1) for k in range(K)]
    x = m.addVars(valid_arcs, vtype=GRB.BINARY, name="x")
    y = m.addVars(range(1, N + 1), range(K), vtype=GRB.BINARY, name="y")
    u = m.addVars(range(K), vtype=GRB.BINARY, name="u")
    order_var = m.addVars(range(1, N + 1), range(K), lb=0.0, ub=N, vtype=GRB.CONTINUOUS, name="ord")

    # ---------------- OBJECTIVE FUNCTION ----------------
    fixed_truck_penalty_km = 25.0
    travel_cost = gp.quicksum(
        D[i, j] * x[i, j, k] for (i, j, k) in valid_arcs
    ) + gp.quicksum(dist_provider.disposal_to_depot_km * u[k] for k in range(K))

    fleet_cost = gp.quicksum(fixed_truck_penalty_km * u[k] for k in range(K))
    m.setObjective(travel_cost + fleet_cost, GRB.MINIMIZE)

    # ---------------- CONSTRAINTS ----------------
    # 1. Every container must be visited by exactly one truck
    for i in range(1, N + 1):
        m.addConstr(gp.quicksum(y[i, k] for k in range(K)) == 1, name=f"visit_{i}")

    for k in range(K):
        # 2. Flow conservation
        for i in range(1, N + 1):
            inflow = x[0, i, k] + gp.quicksum(x[j, i, k] for j in range(1, N + 1) if j != i)
            outflow = x[i, N + 1, k] + gp.quicksum(x[i, j, k] for j in range(1, N + 1) if j != i)
            m.addConstr(inflow == y[i, k], name=f"inflow_{i}_{k}")
            m.addConstr(outflow == y[i, k], name=f"outflow_{i}_{k}")

        # 3. Vehicle starts at Depot and ends at Disposal iff u[k] == 1
        m.addConstr(gp.quicksum(x[0, j, k] for j in range(1, N + 1)) == u[k], name=f"start_{k}")
        m.addConstr(gp.quicksum(x[i, N + 1, k] for i in range(1, N + 1)) == u[k], name=f"end_{k}")

        # 4. Volume Capacity Constraint
        m.addConstr(
            gp.quicksum(vol_demand[i - 1] * y[i, k] for i in range(1, N + 1)) <= truck_max_volume_m3 * u[k],
            name=f"vol_cap_{k}"
        )

        # 5. Weight Capacity Constraint
        m.addConstr(
            gp.quicksum(wt_demand[i - 1] * y[i, k] for i in range(1, N + 1)) <= truck_max_weight_kg * u[k],
            name=f"wt_cap_{k}"
        )

        # 6. Driver Shift Constraint
        drive_km = (
            gp.quicksum(D[0, j] * x[0, j, k] for j in range(1, N + 1)) +
            gp.quicksum(D[i, j] * x[i, j, k] for i in range(1, N + 1) for j in range(1, N + 1) if i != j) +
            gp.quicksum(D[i, N + 1] * x[i, N + 1, k] for i in range(1, N + 1)) +
            dist_provider.disposal_to_depot_km * u[k]
        )
        drive_hours = drive_km / avg_speed_kmh
        service_hours = gp.quicksum((service_time_min / 60.0) * y[i, k] for i in range(1, N + 1))
        unload_hours = (unloading_time_min / 60.0) * u[k]
        m.addConstr(drive_hours + service_hours + unload_hours <= max_shift_hours * u[k], name=f"shift_{k}")

        # 7. Subtour elimination (Miller-Tucker-Zemlin)
        for i in range(1, N + 1):
            for j in range(1, N + 1):
                if i != j:
                    m.addConstr(order_var[i, k] - order_var[j, k] + N * x[i, j, k] <= N - 1)

    m.optimize()

    # ---------------- EXTRACT ROUTES ----------------
    routes_summary = []
    if m.SolCount > 0:
        for k in range(K):
            if u[k].X > 0.5:
                curr = 0
                seq = []
                route_km = 0.0
                while True:
                    next_node = None
                    for j in range(1, N + 2):
                        if (curr, j, k) in x and x[curr, j, k].X > 0.5:
                            next_node = j
                            route_km += D[curr, j]
                            break
                    if next_node is None or next_node == N + 1:
                        break
                    seq.append(next_node - 1)
                    curr = next_node

                route_km += dist_provider.disposal_to_depot_km
                tot_vol = vol_demand[seq].sum()
                tot_wt = wt_demand[seq].sum()
                tot_hrs = (route_km / avg_speed_kmh) + len(seq) * (service_time_min / 60.0) + (unloading_time_min / 60.0)

                routes_summary.append({
                    "vehicle": f"Truck #{len(routes_summary) + 1}",
                    "num_stops": len(seq),
                    "ordered_stop_indices": seq,
                    "ordered_locations": df_c.loc[seq, "Location_id"].tolist(),
                    "total_volume_m3": round(tot_vol, 2),
                    "volume_utilization_pct": round((tot_vol / truck_max_volume_m3) * 100, 1),
                    "total_weight_kg": round(tot_wt, 1),
                    "weight_utilization_pct": round((tot_wt / truck_max_weight_kg) * 100, 1),
                    "total_distance_km": round(route_km, 2),
                    "shift_hours": round(tot_hrs, 2)
                })
    return pd.DataFrame(routes_summary)
