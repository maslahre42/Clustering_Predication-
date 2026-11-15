"""Common-data validation: Kaise persistence, Zakaria median policy and bounded Gurobi check."""
import numpy as np
import pandas as pd
from .zakaria.clustering import extract_container_profiles
from .zakaria.predictor import predict_container_demands, select_collection_sites
from .zakaria.optimizer import solve_collection_routes
from .zakaria.distance_provider import ModularDistanceProvider
from .kaise.data.schema import ReadingRecord
from .kaise.forecasting.features import build_feature_row
from .kaise.forecasting.targets import EvaluationCase
from .kaise.forecasting.baseline import forecast_persistence
from fillinq.routing import plan_routes
from fillinq.simulate import _new_rec, _collect, _close_open_cycles, _kpis

BASELINE_THRESHOLD = 80.0
BASELINE_NEIGHBOUR = 60.0


def profiles(df,start):
    d = df.rename(columns={'site':'Location_id','material':'material_type'}).copy()
    d['fill_num'] = d['fill'].where(~d.overfull)
    d['is_overfull'] = d.overfull
    d['days_diff'] = d.groupby(['Location_id','material_type']).date.diff().dt.days
    d['cycle_rate_pct_per_day'] = d['fill']/d.days_diff.where(d.days_diff>0)
    d['cycle_is_censored'] = d.censored
    return extract_container_profiles(d,as_of=start,inclusive=False)


def run_median_policy(twin,profile,cfg,locs,time_limit):
    """Zakaria selects bins; Omar routes them under the identical multi-load constraints."""
    le,k = twin.initial_state()
    rec,daily = _new_rec(),[]
    lookup = {c:i for i,c in enumerate(twin.cont.container)}
    for day in pd.date_range(twin.start,twin.end):
        if day.day_of_week not in cfg.working_weekdays: continue
        current = profile.copy()
        current['last_reading_date'] = [twin.days[le[lookup[f'{r.Location_id}|{r.material_type}']]] for r in current.itertuples()]
        # The profile's fitted rates stay frozen; only actual simulated service updates its state.
        demands = predict_container_demands(current,planning_date=day,days_ahead=0,
                    container_volume_m3=cfg.container_volume_m3,glass_density_kg_m3=cfg.glass_density_t_m3*1000)
        sites,decisions = select_collection_sites(demands,BASELINE_THRESHOLD,BASELINE_NEIGHBOUR)
        if sites.empty: continue
        stops = sites.rename(columns={'Location_id':'site'}).merge(locs,on='site',how='left')
        stops['vol_l'] = stops.demand_volume_m3*1000
        stops['kg'] = stops.demand_weight_kg
        for material in ('brown','green','white'):
            volumes = decisions.loc[decisions.selected & decisions.material_type.eq(material)].groupby('Location_id').demand_volume_m3.sum()*1000
            stops[f'{material}_l'] = stops.site.map(volumes).fillna(0)
        stops['must'] = True
        # Median fill is an ordering score here, never called an overflow probability.
        stops['value'] = stops.predicted_fill_perc/100
        plan = plan_routes(stops,cfg,time_limit_s=time_limit)
        visited = {s for r in plan.routes for s,_,_ in r['stops']}
        take = decisions[decisions.selected & decisions.Location_id.isin(visited)]
        idx = np.array([lookup[f'{r.Location_id}|{r.material_type}'] for r in take.itertuples()],dtype=int)
        rec['stops'] += len(visited)
        _collect(twin,idx,twin.day_index[day],le,k,rec)
        daily.append(dict(date=day,stops=len(visited),bins=len(idx),km=plan.kpis['km'],hours=plan.kpis['hours'],trucks=plan.kpis['trucks'],dropped_mandatory=len(plan.dropped_mandatory)))
    _close_open_cycles(twin,le,k,rec,twin.day_index[twin.end])
    return dict(**_kpis(rec,len(daily)),daily=pd.DataFrame(daily))


def forecast_comparison(df,training,model,profile,start,end):
    """Frozen rate fits; all three observe the same recorded resets before each target."""
    targets = df[(df.date>=start)&(df.date<=end)&df.container.isin(set(training.container))]
    all_history = {key:rows for key,rows in df.groupby('container')}
    scored = []
    for row in targets.itertuples():
        history = all_history[row.container]
        history = history[history.date<row.date]
        if history.empty: continue
        # Unknown observations update resets, but cannot become numeric persistence features.
        records = [ReadingRecord(r.site,r.material,r.date.date(),None if r.overfull else int(r.fill),bool(r.overfull))
                   for r in history.itertuples() if r.overfull or pd.notna(r.fill)]
        kaise = None
        if records:
            feature = build_feature_row(records,history.date.max().date())
            case = EvaluationCase(row.site,row.material,history.date.max().date(),row.date.date(),
                    (row.date-history.date.max()).days,None if row.overfull or pd.isna(row.fill) else int(row.fill),bool(row.overfull),feature)
            pred = forecast_persistence(case)
            kaise = None if pred is None else pred.predicted_fill_pct
        p = profile[(profile.Location_id==row.site)&(profile.material_type==row.material)].copy()
        p['last_reading_date'] = history.date.max()
        median = predict_container_demands(p,planning_date=row.date,days_ahead=0).predicted_fill_perc.iloc[0]
        omar = model.predict([row.container],[history.date.max()],[row.date]).iloc[0].mean_fill
        scored.append(dict(truth=row.fill,censored=bool(row.censored),omar=float(omar),
                           zakaria=None if pd.isna(median) else float(median),kaise=kaise))
    common = [r for r in scored if pd.notna(r['truth']) and not r['censored'] and all(r[x] is not None for x in ('omar','zakaria','kaise'))]
    bounds = [r for r in scored if r['censored'] and all(r[x] is not None for x in ('omar','zakaria','kaise'))]
    models=[]
    for key,label in [('omar','Seasonal cycle model'),('zakaria','Frozen cycle-median model'),('kaise','Persistence reference')]:
        errors=np.array([r[key]-r['truth'] for r in common],dtype=float)
        models.append(dict(name=key,label=label,available=sum(r[key] is not None for r in scored),
            mae=None if not len(errors) else float(np.abs(errors).mean()),
            bias=None if not len(errors) else float(errors.mean()),
            lowerBoundShortfall=None if not bounds else float(np.mean([max(0,100-r[key]) for r in bounds]))))
    return dict(targets=len(targets),evaluated=len(scored),commonNumericCases=len(common),commonCensoredCases=len(bounds),
                unknownTargets=sum(pd.isna(r['truth']) for r in scored),models=models,
                note='All models use the same known bins and recorded resets strictly before each target. Seasonal and cycle-median rate fits are frozen before simulation start. Numeric 100 and overfull are lower bounds, excluded from MAE; their shortfall is reported separately. Persistence is a reference for observed readings, not a reset-aware dispatch policy. No overall winner is asserted.')


def optimization_check(stops,cfg,limit=3):
    """Run Zakaria's original MILP on a deterministic sample, never an unequal-model benchmark."""
    if stops.empty:
        return dict(status='empty',message='No selected sites to validate.',sites=[],scope='one-load-per-truck',complete=True)
    sample=stops.sort_values(['must','value','site'],ascending=[False,False,True]).head(6).copy()
    candidate=pd.DataFrame(dict(Location_id=sample.site,demand_volume_m3=sample.vol_l/1000,
                                demand_weight_kg=sample.kg,n_bins=sample.n_bins))
    for material in getattr(cfg,'compartment_litres',{}):
        candidate[f'{material}_m3'] = sample[f'{material}_l']/1000
    coords=sample[['site','lat','lon']].rename(columns={'site':'Location_id'})
    road = getattr(cfg, 'road_network', None)
    if road is not None:
        from types import SimpleNamespace
        km, seconds, access = road.matrix([cfg.depot_lat,*sample.lat,cfg.disposal_lat], [cfg.depot_lon,*sample.lon,cfg.disposal_lon])
        if not np.isfinite(km).all() or not np.isfinite(seconds).all() or any(point[2] > road.max_snap_m for point in access):
            return dict(status='infeasible',message='Sample has no connected driving access.',sites=candidate.Location_id.tolist(),scope='one-load-per-truck',complete=False)
        provider=SimpleNamespace(location_ids=candidate.Location_id.tolist(),n_bins=len(sample),
            inter_bin_matrix=km[1:-1,1:-1],depot_dist=km[0,1:-1],disposal_dist=km[1:-1,-1],disposal_to_depot_km=float(km[-1,0]),
            distance_provenance='osrm_car_street_network',road_duration_minutes=(seconds[0,1:-1]/60,seconds[1:-1,-1]/60,seconds[1:-1,1:-1]/60,float(seconds[-1,0]/60)))
    else:
        provider=ModularDistanceProvider(candidate.Location_id.tolist(),coords,road_winding_factor=cfg.detour_factor,
                   depot_coord=(cfg.depot_lat,cfg.depot_lon),disposal_coord=(cfg.disposal_lat,cfg.disposal_lon),fixed_travel_min=cfg.fixed_travel_min)
    if road is None and cfg.fixed_travel_min:
        # Identities remain different places even if missing coordinates coincide.
        provider.depot_dist=np.ones(len(sample));provider.disposal_dist=np.ones(len(sample))
        provider.disposal_to_depot_km=1.0
        provider.inter_bin_matrix=np.ones((len(sample),len(sample)))-np.eye(len(sample))
    result=solve_collection_routes(candidate,provider,waste_density_kg_m3=cfg.glass_density_t_m3*1000,
            container_volume_m3=cfg.container_volume_m3,truck_max_volume_m3=cfg.truck_volume_m3 or cfg.truck_payload_t/cfg.glass_density_t_m3,
            truck_max_weight_kg=cfg.truck_payload_kg,max_shift_hours=cfg.shift_hours,max_fleet_vehicles=cfg.max_vehicles,
            avg_speed_kmh=cfg.avg_speed_kph,service_time_min=cfg.service_min_per_bin,service_time_per_stop_min=cfg.service_min_per_stop,
            unloading_time_min=cfg.unload_min,time_limit_sec=limit,mip_gap=0,
            compartment_capacities_m3={m:v/1000 for m,v in getattr(cfg,'compartment_litres',{}).items()})
    routes=[dict(truck=r.vehicle,sites=r.ordered_locations,volumeM3=r.total_volume_m3,weightKg=r.total_weight_kg,
                 hours=r.shift_hours,distanceKm=None if cfg.fixed_travel_min else r.total_distance_km) for r in result.routes.itertuples()]
    return dict(status=result.status,message=result.message,scope='one-load-per-truck',sites=candidate.Location_id.tolist(),
                complete=result.complete,fleetLowerBound=result.fleet_lower_bound,trucks=len(routes),routes=routes,
                unserved=result.unserved.to_dict('records'),runtimeSeconds=result.runtime_seconds,
                note='Independent MILP check: at most six highest-priority selected sites, all required, one load per truck. Uses the applied physical assumptions and travel mode. This checks the sample only; its truck count is not comparable with the city-wide multi-load plan. Missing Gurobi/license is reported explicitly.')
