"""Rebuild corrected artifacts without overwriting the original notebook exports."""
import argparse
import hashlib
import json
from pathlib import Path

import pandas as pd

from src.clustering import cluster_containers, extract_container_profiles
from src.data_loader import PROJECT_ROOT, collection_summary, load_and_clean_data, planning_day
from src.distance_provider import ModularDistanceProvider
from src.evaluation import evaluate_forecasts
from src.optimizer import solve_collection_routes
from src.predictor import predict_container_demands, select_collection_sites
from src.visualizer import plot_interactive_routes


def run_pipeline(csv_path=None, output_dir=None, planning_date=None, days_ahead=0,
                 max_sites=None, max_fleet_vehicles=12, fixed_travel_min=10.0,
                 time_limit_sec=20, evaluate=False, route=True):
    source = Path(csv_path) if csv_path else PROJECT_ROOT / 'glass_fill_levels_anonymized_f.csv'
    source = source.resolve()
    out = Path(output_dir) if output_dir else PROJECT_ROOT / 'data' / 'corrected'
    out.mkdir(parents=True, exist_ok=True)
    df = load_and_clean_data(source)
    if df.empty:
        raise ValueError('Dataset has no observations.')
    day = planning_day(planning_date) if planning_date else df['date'].max() + pd.Timedelta(days=1)
    profiles = extract_container_profiles(df, as_of=day, inclusive=False)
    profiles, _ = cluster_containers(profiles)
    grouping = dict(profiles.attrs)
    # Forecast at dispatch by default. Future target plans assume no intervening pickup.
    demands = predict_container_demands(profiles, planning_date=day, days_ahead=days_ahead)
    sites, decisions = select_collection_sites(demands)
    if max_sites is not None and (isinstance(max_sites, bool) or not isinstance(max_sites, int) or max_sites < 1):
        raise ValueError('max_sites must be a positive integer or None.')
    candidates = sites if max_sites is None else sites.head(max_sites).copy()
    deferred = sites.iloc[len(candidates):].copy()
    deferred['reason'] = 'deferred_by_explicit_demo_limit'
    provider = ModularDistanceProvider(candidates['Location_id'].tolist(), fixed_travel_min=fixed_travel_min)
    result = solve_collection_routes(candidates, provider, max_fleet_vehicles=max_fleet_vehicles,
                                    time_limit_sec=time_limit_sec) if route else None
    summary = collection_summary(df)
    artifacts = {'cleaned_fill_levels': df, 'container_clusters': profiles,
                 'predicted_demands': demands, 'bin_decisions': decisions, 'selected_sites': sites,
                 'deferred_sites': deferred, 'collection_summary': summary}
    if result:
        artifacts.update(routes=result.routes, unserved_sites=result.unserved)
        plot_interactive_routes(result.routes, candidates, provider, str(out / 'route_proposal.html'))
    if evaluate:
        metrics, cases = evaluate_forecasts(df)
        artifacts.update(forecast_metrics=metrics, forecast_cases=cases)
    for name, frame in artifacts.items():
        frame.to_csv(out / f'{name}.csv', index=False)
    manifest = dict(schema_version=2, source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
        planning_date=day.date().isoformat(), forecast_target_date=(day+pd.Timedelta(days=days_ahead)).date().isoformat(),
        observation_cutoff='strictly before planning_date', source_rows=len(df), known_bins=len(profiles),
        selected_bins=int(decisions['selected'].sum()), selected_sites=len(sites), solver_sites=len(candidates),
        deferred_sites=len(deferred), grouping=grouping, synthetic_coordinates=True,
        route_status=result.status if result else 'not_requested',
        routing_message=result.message if result else 'Routing not requested.',
        model_stats=result.model_stats if result else {},
        served_sites=int(result.routes['num_stops'].sum()) if result else 0,
        unserved_solver_sites=len(result.unserved) if result else len(candidates),
        routing_seconds=result.runtime_seconds if result else None,
        configuration=dict(container_volume_m3=3.0, density_kg_m3=350.0, truck_volume_m3=18.0,
            truck_payload_kg=12000.0, shift_hours=8.0, service_min_per_bin=5.0, unloading_min=15.0,
            max_fleet_vehicles=max_fleet_vehicles, fixed_travel_min=fixed_travel_min,
            avg_speed_kmh=28.0, road_winding_factor=1.3, holiday_multiplier=1.0,
            select_threshold_pct=80.0, opportunistic_threshold_pct=60.0),
        assumptions=['Every observation precedes emptying.', 'Cycle medians use censored lower bounds, not calibrated probabilities.',
            'Container volume and payload follow project mentor notes; density, truck volume, depot and disposal are assumptions.',
            'Synthetic coordinates; haversine/detour distances are not road navigation.',
            'One load and final unloading per vehicle; no mid-route unload or color-chamber constraints.'])
    manifest['artifacts'] = [f'{name}.csv' for name in artifacts] + (['route_proposal.html'] if result else [])
    manifest['evaluation'] = ({'test_start': '2026-04-01', 'protocol': 'rolling_strict_before_target_day',
                               'numeric_comparison': 'common_numeric_cases_excluding_overfull_truths'} if evaluate else None)
    (out / 'manifest.json').write_text(json.dumps(manifest, indent=2, default=lambda x: x.item() if hasattr(x, 'item') else str(x)) + '\n')
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--csv', type=Path)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--planning-date')
    parser.add_argument('--days-ahead', type=int, default=0)
    parser.add_argument('--max-sites', type=int, help='Explicit demo subset; all remaining sites are exported as deferred.')
    parser.add_argument('--max-vehicles', type=int, default=12)
    parser.add_argument('--fixed-travel-min', type=float, default=10)
    parser.add_argument('--time-limit', type=float, default=20)
    parser.add_argument('--evaluate', action='store_true')
    parser.add_argument('--no-route', action='store_true')
    args = parser.parse_args()
    manifest = run_pipeline(args.csv, args.output, args.planning_date, args.days_ahead, args.max_sites,
        args.max_vehicles, args.fixed_travel_min, args.time_limit, args.evaluate, not args.no_route)
    print(json.dumps(manifest, indent=2, default=str))
    return 0 if manifest['route_status'] in ('optimal', 'feasible', 'empty', 'not_requested') else 2


if __name__ == '__main__':
    raise SystemExit(main())
