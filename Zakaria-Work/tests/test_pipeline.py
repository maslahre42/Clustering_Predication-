import itertools
import json
import math

import numpy as np
import pandas as pd
import pytest

from src.clustering import cluster_containers, extract_container_profiles
from src.data_loader import get_latest_readings, load_and_clean_data
from src.distance_provider import ModularDistanceProvider
from src.evaluation import evaluate_forecasts
from src.optimizer import solve_collection_routes, solve_gurobi_waste_vrp
from src.predictor import predict_container_demands, select_collection_sites
from src.visualizer import plot_interactive_routes
from run_pipeline import run_pipeline


def readings(tmp_path, rows):
    path = tmp_path / 'readings.csv'
    path.write_text('Location_id,material_type,date,fill_level_perc\n' + '\n'.join(rows) + '\n', encoding='utf-8-sig')
    return load_and_clean_data(path)


def test_overfull_preserves_last_row_and_is_not_a_percentage(tmp_path):
    df = readings(tmp_path, ['a,white,2026-01-01,40', 'a,white,2026-01-11,overfull'])
    last = get_latest_readings(df).iloc[0]
    assert last.is_overfull and pd.isna(last.fill_num)
    assert df.iloc[1].cycle_rate_pct_per_day == 10
    assert df.iloc[1].cycle_is_censored
    assert pd.isna(df.iloc[0].cycle_rate_pct_per_day)


@pytest.mark.parametrize('row', [
    'a,blue,2026-01-01,40', 'a,white,2026-1-1,40', 'a,white,2026-02-30,40',
    'a,white,2026-01-01,110', 'a,white,2026-01-01,-1', 'a,white,2026-01-01,nan',
    ',white,2026-01-01,50', 'a,white,2026-01-01,inf',
])
def test_invalid_data_is_rejected(tmp_path, row):
    with pytest.raises(ValueError, match='Invalid'):
        readings(tmp_path, [row])


def test_duplicate_keys_rejected(tmp_path):
    with pytest.raises(ValueError, match='Duplicate'):
        readings(tmp_path, ['a,white,2026-01-01,40'] * 2)


def test_material_identity_and_reset_aware_rate(tmp_path):
    df = readings(tmp_path, ['a,white,2026-01-01,90', 'a,white,2026-01-11,20',
                             'a,brown,2026-01-01,10', 'a,brown,2026-01-11,50'])
    p = extract_container_profiles(df, as_of='2026-01-12', inclusive=False)
    assert len(p) == 2
    assert p.set_index('material_type').loc['white', 'daily_fill_velocity'] == 2
    prediction = predict_container_demands(p, planning_date='2026-01-12', days_ahead=2)
    assert prediction.set_index('material_type').loc['white', 'predicted_fill_perc'] == 6
    assert prediction.set_index('material_type').loc['brown', 'predicted_fill_perc'] == 15


def test_future_rows_do_not_change_historical_profiles_or_forecast(tmp_path):
    df = readings(tmp_path, ['a,white,2026-01-01,90', 'a,white,2026-01-11,20'])
    future = readings(tmp_path, ['a,white,2026-01-01,90', 'a,white,2026-01-11,20',
        'a,white,2026-01-12,100', 'b,white,2026-01-20,100'])
    a = extract_container_profiles(df, as_of='2026-01-12', inclusive=False)
    b = extract_container_profiles(future, as_of='2026-01-12', inclusive=False)
    pd.testing.assert_frame_equal(a, b)
    pd.testing.assert_frame_equal(predict_container_demands(a, planning_date='2026-01-12'),
                                  predict_container_demands(b, planning_date='2026-01-12'))


def test_same_day_inclusive_profiles_cannot_be_used_for_morning_dispatch(tmp_path):
    df = readings(tmp_path, ['a,white,2026-01-01,90', 'a,white,2026-01-11,20'])
    with pytest.raises(ValueError, match='strictly before'):
        predict_container_demands(extract_container_profiles(df, as_of='2026-01-11'), planning_date='2026-01-11')


def test_sparse_and_overfull_only_profiles_are_explicit(tmp_path):
    df = readings(tmp_path, ['a,white,2026-01-01,overfull'])
    p = extract_container_profiles(df, as_of='2026-01-02', inclusive=False)
    clustered, model = cluster_containers(p)
    assert model is None and clustered.iloc[0].tier == 'Insufficient numeric history'
    pred = predict_container_demands(p, planning_date='2026-01-02')
    assert not pred.iloc[0].forecast_available and pd.isna(pred.iloc[0].predicted_fill_perc)
    sites, decisions = select_collection_sites(pred)
    assert sites.empty and decisions.iloc[0].selection_reason == 'no_forecast'


def test_material_fallback_uses_only_completed_known_cycles(tmp_path):
    df = readings(tmp_path, ['a,white,2026-01-01,90', 'a,white,2026-01-11,20', 'b,white,2026-01-11,overfull'])
    p = extract_container_profiles(df, as_of='2026-01-12', inclusive=False).set_index('Location_id')
    assert p.loc['b', 'daily_fill_velocity'] == 2
    assert p.loc['b', 'rate_source'] == 'material_cycles'


def test_cluster_adapts_to_identical_small_samples_and_keeps_all_bins(tmp_path):
    rows = [f'{site},white,2026-01-{day:02d},20' for site in ('a','b') for day in (1,11,21)]
    p = extract_container_profiles(readings(tmp_path, rows), as_of='2026-01-22', inclusive=False)
    result, model = cluster_containers(p)
    assert len(result) == 2 and model.n_clusters == 1
    assert result.cluster.notna().all()


def test_selection_groups_materials_without_inventing_missing_forecasts():
    demands = pd.DataFrame({'Location_id':['a','a','b','c'], 'material_type':['white','brown','green','white'],
        'predicted_fill_perc':[90,65,50,np.nan], 'forecast_available':[True,True,True,False],
        'demand_volume_m3':[2.7,1.95,1.5,np.nan], 'demand_weight_kg':[945,682.5,525,np.nan]})
    sites, decisions = select_collection_sites(demands)
    assert len(sites) == 1 and sites.iloc[0].n_bins == 2
    assert sites.iloc[0].demand_volume_m3 == pytest.approx(4.65)
    assert decisions.selection_reason.tolist() == ['at_or_above_threshold','same_site_opportunistic','below_threshold','no_forecast']


def test_coordinates_are_stable_between_subsets_and_orders():
    a, b = ModularDistanceProvider(['a','b']), ModularDistanceProvider(['b','c','a'])
    np.testing.assert_allclose(a.coords[0], b.coords[2])
    np.testing.assert_allclose(a.coords[1], b.coords[0])
    np.testing.assert_allclose(a.depot_dist[0], b.depot_dist[2])
    assert a.distance_provenance.startswith('synthetic_')


@pytest.mark.parametrize('table', [
    pd.DataFrame({'Location_id':['a'],'lat':[np.nan],'lon':[9]}),
    pd.DataFrame({'Location_id':['b'],'lat':[49],'lon':[9]}),
    pd.DataFrame({'Location_id':['a'],'lat':[91],'lon':[9]}),
    pd.DataFrame({'Location_id':['a','a'],'lat':[49,49],'lon':[9,9]}),
])
def test_invalid_coordinate_tables_rejected(table):
    with pytest.raises(ValueError):
        ModularDistanceProvider(['a'], table)


def route_problem(n=4, volume=2.0):
    sites = pd.DataFrame({'Location_id':[f's{i}' for i in range(n)], 'demand_volume_m3':[volume]*n,
                          'demand_weight_kg':[volume*350]*n, 'n_bins':[1]*n,
                          'predicted_fill_perc':[80.0]*n})
    return sites, ModularDistanceProvider(sites.Location_id.tolist())


@pytest.fixture
def gurobi_available():
    pytest.importorskip('gurobipy')
    sites, provider = route_problem(1)
    result = solve_collection_routes(sites, provider)
    if result.status == 'solver_unavailable':
        pytest.skip(result.message)
    assert result.complete


def test_oversize_is_not_clipped_and_all_required_sites_remain_unserved():
    sites, provider = route_problem(2, volume=20)
    result = solve_collection_routes(sites, provider, truck_max_volume_m3=18)
    assert result.status == 'infeasible' and len(result.unserved) == 2
    assert sites.demand_volume_m3.tolist() == [20,20]


def test_fleet_shortage_and_impossible_shift_have_explicit_failure():
    sites, provider = route_problem(4)
    assert solve_collection_routes(sites, provider, truck_max_volume_m3=2, max_fleet_vehicles=1).status == 'infeasible'
    result = solve_collection_routes(sites, provider, max_shift_hours=.01)
    assert result.status == 'infeasible' and len(result.unserved) == 4


def test_empty_problem_requires_no_solver():
    result = solve_collection_routes(pd.DataFrame(columns=['Location_id']), ModularDistanceProvider([]))
    assert result.status == 'empty' and result.complete


def test_provider_order_mismatch_and_config_density_rejected():
    sites, provider = route_problem(2)
    with pytest.raises(ValueError, match='order'):
        solve_collection_routes(sites.iloc[::-1], provider)
    with pytest.raises(ValueError, match='density'):
        solve_collection_routes(sites, provider, waste_density_kg_m3=380)


def test_compact_solver_matches_exhaustive_small_case(gurobi_available):
    sites, p = route_problem(4)
    result = solve_collection_routes(sites, p, truck_max_volume_m3=4, max_fleet_vehicles=4, mip_gap=0)
    # Independently enumerate all visit orders and contiguous route partitions.
    best = (math.inf, math.inf)
    for perm in itertools.permutations(range(4)):
        for mask in range(1 << 3):
            breaks = [0] + [i+1 for i in range(3) if mask & (1 << i)] + [4]
            routes = [perm[a:b] for a,b in zip(breaks,breaks[1:])]
            if any(len(route)*2 > 4 for route in routes):
                continue
            distance = sum(p.depot_dist[r[0]] + sum(p.inter_bin_matrix[a,b] for a,b in zip(r,r[1:]))
                           + p.disposal_dist[r[-1]] + p.disposal_to_depot_km for r in routes)
            best = min(best, (len(routes), distance))
    assert result.complete and len(result.routes) == best[0]
    assert result.routes.total_distance_km.sum() == pytest.approx(best[1], abs=1e-6)
    assert sorted(i for seq in result.routes.ordered_stop_indices for i in seq) == list(range(4))
    assert result.routes.total_volume_m3.le(4+1e-6).all()
    assert result.routes.shift_hours.le(8+1e-6).all()
    assert result.model_stats['arcs'] < result.model_stats['legacy_arc_upper_bound']


def test_zero_demand_zero_travel_cannot_form_disconnected_cycles(gurobi_available):
    sites, _ = route_problem(3, volume=0)
    coords = pd.DataFrame({'Location_id':sites.Location_id, 'lat':[49]*3,'lon':[9]*3})
    p = ModularDistanceProvider(sites.Location_id, coords, depot_coord=(49,9), disposal_coord=(49,9))
    result = solve_collection_routes(sites,p,service_time_min=0,unloading_time_min=0,mip_gap=0)
    assert result.complete and result.routes.num_stops.sum() == 3


def test_fixed_travel_includes_service_final_unload_and_return(gurobi_available):
    sites, _ = route_problem(2)
    p = ModularDistanceProvider(sites.Location_id, fixed_travel_min=10)
    result = solve_collection_routes(sites,p,service_time_min=5,unloading_time_min=15)
    assert result.complete and len(result.routes) == 1
    assert result.routes.iloc[0].shift_hours == pytest.approx((4*10+2*5+15)/60)
    wrapper = solve_gurobi_waste_vrp(sites,p)
    assert wrapper.attrs['status'] in ('optimal','feasible')


def test_shift_can_require_more_trucks_than_capacity(gurobi_available):
    sites, _ = route_problem(2)
    provider = ModularDistanceProvider(sites.Location_id, fixed_travel_min=10)
    result = solve_collection_routes(sites, provider, max_shift_hours=4,
                                    service_time_min=150, max_fleet_vehicles=2)
    assert result.fleet_lower_bound == 1
    assert result.complete and len(result.routes) == 2
    assert result.routes.shift_hours.le(4).all()


def test_weight_limit_is_binding_even_with_spare_truck_volume(gurobi_available):
    sites, provider = route_problem(3)
    result = solve_collection_routes(sites, provider, truck_max_volume_m3=18,
                                    truck_max_weight_kg=1000, max_fleet_vehicles=3)
    assert result.complete and len(result.routes) == 3
    assert result.routes.total_weight_kg.le(1000).all()


def test_solver_infeasible_preserves_all_sites_when_aggregate_bound_is_insufficient(gurobi_available):
    # Three 6 m³ indivisible stops need three 10 m³ trucks, although ceil(18/10)=2.
    sites, provider = route_problem(3, volume=6)
    result = solve_collection_routes(sites, provider, truck_max_volume_m3=10,
                                    max_fleet_vehicles=2)
    assert result.fleet_lower_bound == 2
    assert result.status == 'infeasible' and len(result.unserved) == 3
    assert result.routes.empty


def test_date_before_first_observation_has_no_invented_inventory(tmp_path):
    df = readings(tmp_path, ['a,white,2026-01-01,90'])
    profiles = extract_container_profiles(df, as_of='2025-12-31', inclusive=False)
    assert profiles.empty
    predictions = predict_container_demands(profiles, planning_date='2025-12-31')
    sites, decisions = select_collection_sites(predictions)
    assert sites.empty and decisions.empty


def test_map_uses_same_disposal_and_discloses_synthetic_distance(tmp_path, gurobi_available):
    sites, p = route_problem(1)
    result = solve_collection_routes(sites,p)
    path = tmp_path/'route.html'
    plot_interactive_routes(result.routes, sites, p, path)
    html = path.read_text()
    assert 'Synthetic site assignments' in html and 'not road navigation' in html
    assert str(p.disposal_coord[0]) in html


def test_rolling_evaluation_does_not_train_on_target_day(tmp_path):
    df = readings(tmp_path, ['a,white,2026-01-01,90','a,white,2026-01-11,20','a,white,2026-01-21,80',
                            'a,white,2026-01-31,overfull'])
    metrics, cases = evaluate_forecasts(df, test_start='2026-01-21')
    assert cases.iloc[0].predicted_fill_perc == 20
    assert metrics.overfull_truths.tolist() == [1,1]
    assert metrics.common_numeric_cases.tolist() == [1,1]
    assert metrics.iloc[0].mae_pp == 60


def test_pipeline_reconciles_explicit_demo_cap_and_preserves_source(tmp_path, gurobi_available):
    rows = [f'{site},white,2026-01-{day:02d},100' for site in ('a','b','c') for day in (1,11,21)]
    df = readings(tmp_path, rows)
    source = tmp_path/'readings.csv'
    before = source.read_bytes()
    manifest = run_pipeline(source, tmp_path/'out', '2026-02-01', max_sites=2)
    assert source.read_bytes() == before
    assert manifest['selected_sites'] == 3 and manifest['deferred_sites'] == 1
    assert manifest['served_sites'] + manifest['unserved_solver_sites'] + manifest['deferred_sites'] == 3
    saved = json.loads((tmp_path/'out'/'manifest.json').read_text())
    assert saved['observation_cutoff'] == 'strictly before planning_date'
