"""JSON/stdin adapter to Omar's real forecast, OR-Tools and digital twin modules.

No database writes, sockets, shared settings file or model singleton. Each request
receives a cutoff-bounded observation snapshot from ASP.NET.
"""
from __future__ import annotations
import contextlib
import io
import json
import math
from pathlib import Path
import sys

here = Path(__file__).resolve().parent
sys.path.insert(0,str(here))
sys.path.insert(0, str(here / 'vendor'))
import numpy as np
import pandas as pd
from fillinq.config import OpsConfig
from fillinq.data import load_readings, build_intervals
from fillinq.forecast import RateModel
from fillinq.policy import assess_bins, select_stops, window_end
from fillinq.routing import plan_routes
from fillinq.roads import RoadNetwork, RoadRoutingError
from fillinq.simulate import Twin, run_baseline, run_policy
from integrations.dataset import source, evidence, DatasetValidationError
from integrations.comparison import profiles, run_median_policy, forecast_comparison, optimization_check
from integrations.planning_insights import operating_cost, fill_timing


def config(settings):
    mapping = dict(containerVolumeM3='container_volume_m3', truckVolumeM3='truck_volume_m3',
        truckPayloadT='truck_payload_t', maxVehicles='max_vehicles', shiftHours='shift_hours',
        fixedTravelMin='fixed_travel_min', avgSpeedKph='avg_speed_kph', detourFactor='detour_factor',
        serviceMinPerBin='service_min_per_bin', serviceMinPerStop='service_min_per_stop', unloadMin='unload_min',
        depotLatitude='depot_lat', depotLongitude='depot_lon', disposalLatitude='disposal_lat', disposalLongitude='disposal_lon',
        lookaheadDays='lookahead_days', mustProbability='must_p', neighbourProbability='bin_p_collect',
        neighbourFillPercent='bin_fill_collect', optionalProbability='opt_p',
        vehicleFixedCostMin='vehicle_fixed_cost_min', optionalValueMin='opt_value_min')
    cfg = OpsConfig(**{dst: settings[src] for src, dst in mapping.items() if src in settings})
    cfg.glass_density_t_m3 = settings.get('glassDensityKgM3', 350) / 1000
    cfg.opt_value_min = settings.get('optionalValueMin', 0)
    caps = {material: settings.get(f'{material}CompartmentM3',0) for material in ('brown','green','white')}
    if any(not isinstance(value,(int,float)) or not math.isfinite(value) or value < 0 for value in caps.values()):
        raise ValueError('Compartment capacities must be finite and nonnegative.')
    cfg.compartment_litres = {}
    if any(caps.values()):
        if any(value < .001 for value in caps.values()): raise ValueError('Configure all three compartments with at least one litre each, or leave all three zero.')
        if cfg.truck_volume_m3 > 0 and sum(caps.values()) > cfg.truck_volume_m3 + 1e-9: raise ValueError('Truck volume must cover the configured compartments.')
        cfg.compartment_litres = {material:value*1000 for material,value in caps.items()}
        cfg.truck_volume_m3 = min(cfg.truck_volume_m3 or math.inf, sum(caps.values()))
    cfg.working_weekdays = tuple(i for i,key in enumerate(['workMonday','workTuesday','workWednesday','workThursday','workFriday','workSaturday','workSunday']) if settings.get(key, i<5))
    if not cfg.working_weekdays:
        raise ValueError('Choose at least one working collection day.')
    return cfg


def make_road_network():
    return RoadNetwork()


def enable_street_routing(cfg):
    cfg.fixed_travel_min = 0
    cfg.road_network = make_road_network()
    return cfg.road_network


def street_route_shapes(plan, cfg, stops):
    """One request per truck, then split the returned road legs at unloading visits."""
    roads = cfg.road_network
    positions = {row.site: (row.lat, row.lon) for row in stops.itertuples()}
    for route in plan.routes:
        points = [(cfg.depot_lat, cfg.depot_lon)]
        counts = []
        for trip in route['trips']:
            points.extend(positions[site] for site in trip['stops'])
            points.append((cfg.disposal_lat, cfg.disposal_lon))
            counts.append(len(trip['stops']) + 1)
        points.append((cfg.depot_lat, cfg.depot_lon))
        legs = roads.route(points)
        shapes, offset = [], 0
        for load, count in enumerate(counts, 1):
            group = legs[offset:offset + count]
            shapes.append(dict(load=load,returning=False,points=[point for leg in group for point in leg['points']],
                distanceKm=sum(leg['distanceKm'] for leg in group),drivingSeconds=sum(leg['drivingSeconds'] for leg in group)))
            offset += count
        shapes.append(dict(load=len(counts),returning=True,**legs[-1]))
        distance = sum(leg['distanceKm'] for leg in legs)
        driving = sum(leg['drivingSeconds'] for leg in legs)
        service = route['bins'] * cfg.service_min_per_bin + len(route['stops']) * cfg.service_min_per_stop + len(route['trips']) * cfg.unload_min
        hours = driving / 3600 + service / 60
        if hours > cfg.shift_hours + 1e-6:
            raise RoadRoutingError('Street-route verification exceeds the shift. Retry with fresh routing data or a longer shift; no infeasible route was accepted.')
        route.update(roadPaths=shapes, km=distance, hours=hours, drivingHours=driving / 3600)
    plan.kpis['km'] = sum(route['km'] for route in plan.routes)
    plan.kpis['hours'] = sum(route['hours'] for route in plan.routes)


def readings(payload):
    observations, _, _ = source(payload)
    rows = pd.DataFrame(observations, columns=['locationId', 'material', 'date', 'fillLevel'])
    if rows.empty:
        return pd.DataFrame(columns=['site','material','date','fill','overfull','censored','container']).astype({'date':'datetime64[ns]','fill':'float64','overfull':'bool','censored':'bool'})
    # Preserve unknown observations: they reset the bin even when they provide no model rate.
    rows = rows.rename(columns={'locationId':'site', 'fillLevel':'fill_raw'})
    rows['date'] = pd.to_datetime(rows['date'])
    rows = rows[rows['date'] <= pd.Timestamp(payload['asOf'])]
    raw = rows.fill_raw.astype(str).str.strip().str.lower()
    rows['overfull'] = raw.eq('overfull')
    rows['fill'] = pd.to_numeric(raw.where(~rows.overfull, '100'), errors='coerce')
    rows.loc[~rows['fill'].between(0,100), 'fill'] = np.nan
    rows['censored'] = rows['overfull'] | rows['fill'].eq(100)
    rows['container'] = rows['site'] + '|' + rows['material']
    return rows.drop(columns='fill_raw').drop_duplicates(['container','date'],keep='last').sort_values(['container','date']).reset_index(drop=True)


def fit(df):
    if df.empty:
        return None, pd.DataFrame(columns=['censored','rate'])
    iv = build_intervals(df)
    iv = iv[iv['rate'].notna()]
    return (RateModel().fit(iv) if len(iv) else None), iv


def places(payload, sites, cfg):
    table = {r['locationId']: r for r in payload['locations']}
    return pd.DataFrame([dict(site=s, lat=table.get(s,{}).get('latitude', cfg.depot_lat),
        lon=table.get(s,{}).get('longitude', cfg.depot_lon)) for s in sites], columns=['site','lat','lon'])


def next_day(day, cfg):
    day = pd.Timestamp(day) + pd.Timedelta(days=1)
    while day.day_of_week not in cfg.working_weekdays:
        day += pd.Timedelta(days=1)
    return day


def iso(day):
    return pd.Timestamp(day).date().isoformat()


def proposal(payload):
    df, cfg = readings(payload), config(payload['settings'])
    model, iv = fit(df)
    day = next_day(payload['asOf'], cfg)
    last = df.groupby('container', sort=True).tail(1).copy()
    if df.empty:
        last['date'] = pd.to_datetime(last['date'])
    state = last[['container','site','material','date']].rename(columns={'date':'last_empty'})
    if model:
        assessed = assess_bins(model, state, day, cfg)
        stops, take = select_stops(assessed, places(payload, df.site.unique(), cfg), cfg)
    else:
        assessed = state.assign(fill_now=np.nan, p_over_window=np.nan, days_since_empty=(day-state.last_empty).dt.days)
        stops = pd.DataFrame(columns=['site','lat','lon','vol_l','kg','n_bins','must','value'])
        take = pd.DataFrame(columns=['container','site'])
    selected = set(take.container)
    mandatory_sites = set(stops.loc[stops['must'].astype(bool), 'site'])
    coords = {r['locationId']:r for r in payload['locations']}
    roads = enable_street_routing(cfg)
    missing = set(stops.site) - set(coords)
    plan = plan_routes(stops[~stops.site.isin(missing)].copy(), cfg,
                       time_limit_s=payload['settings'].get('solverTimeLimitSeconds',3))
    street_route_shapes(plan, cfg, stops)
    stop_lookup = stops.set_index('site')
    bins = []
    for r in assessed.itertuples():
        decision = ('no_forecast' if pd.isna(r.fill_now) else 'due' if r.p_over_window >= cfg.must_p else
                    'neighbour' if r.container in selected and r.site in mandatory_sites else
                    'optional' if r.container in selected else 'skipped')
        volume = r.fill_now/100*cfg.container_volume_m3*1000 if r.container in selected else 0
        bins.append(dict(locationId=r.site, material=r.material, lastEmptied=iso(r.last_empty),
            daysSinceEmptied=int(r.days_since_empty), expectedFillPercent=r.fill_now, overflowProbability=r.p_over_window,
            decision=decision, volumeL=volume, weightKg=volume*cfg.glass_density_t_m3))
    routes = [dict(truck=r['truck'], hours=r['hours'], distanceKm=r['km'], bins=r['bins'],
        territory=r['territory'],roadPaths=r['roadPaths'],drivingHours=r['drivingHours'],
        trips=[dict(stops=t['stops'], weightKg=t['weight_t']*1000, volumeL=t['volume_m3']*1000,
                    volumeByMaterialL=t.get('volume_by_material_l')) for t in r['trips']]) for r in plan.routes]
    unserved = []
    for site in [*plan.dropped_mandatory,*plan.dropped_optional,*sorted(missing)]:
        row = stop_lookup.loc[site]
        reason = ('missing_coordinates' if site in missing else plan.reasons[site] if site in plan.reasons else 'exceeds_truck_capacity' if row.kg > cfg.truck_payload_kg or row.vol_l > cfg.truck_volume_l
                  else 'sector_limit' if site in mandatory_sites else 'optional_not_scheduled')
        unserved.append(dict(locationId=site, mandatory=site in mandatory_sites, reason=reason))
    k = plan.kpis
    routing = dict(roads.describe(),yard=roads.access(cfg.depot_lat,cfg.depot_lon),disposal=roads.access(cfg.disposal_lat,cfg.disposal_lon))
    return dict(costs=operating_cost(k['km'],k['trucks'],payload['settings']),fillTiming=fill_timing(df,model,iv,payload['asOf']),
        routing=routing,dataset=evidence(df,payload),asOf=payload['asOf'], planDate=iso(day), windowEnd=iso(window_end(day,cfg)),settings=payload['settings'],
        model=dict(engine='omar-python', bins=len(state), cycles=len(iv), censoredCycles=int(iv.censored.sum()),
            sigma=model.sigma if model else 0, tau=model.tau if model else 0,
            materialRatePercentPerDay=model.summary()['material_rate_pct_per_day'] if model else {},
            vacationMultiplier=float(np.exp(model.g)) if model else None,
            seasonality=model.seasonality_table().to_dict('records') if model else []), bins=bins,
        stops=[dict(locationId=r.site,mandatory=bool(r.must),risk=r.value,bins=int(r.n_bins),volumeL=r.vol_l,weightKg=r.kg,
                    latitude=coords.get(r.site,{}).get('latitude'), longitude=coords.get(r.site,{}).get('longitude'),
                    isSynthetic=coords.get(r.site,{}).get('isSynthetic',True),
                    **roads.access(coords.get(r.site,{}).get('latitude'),coords.get(r.site,{}).get('longitude')),
                    materials=sorted(take.loc[take.site.eq(r.site),'material'].tolist())) for r in stops.itertuples()],
        plan=dict(routes=routes,unserved=unserved,totals=dict(trucks=k['trucks'],trips=k['trips'],stops=k['stops'],bins=k['bins'],
            hours=k['hours'],distanceKm=None if cfg.fixed_travel_min else k['km'], weightT=k['weight_t'],volumeM3=k['volume_m3'],
            loadsByCapacity=max(math.ceil(k['weight_t']/cfg.truck_payload_t),math.ceil(k['volume_m3']/cfg.truck_volume_m3) if cfg.truck_volume_m3 else 0))),
        assumptions=['The seasonal cycle model and route optimizer run on this request’s history prefix only.',
          'A recorded visit empties the bin. Full/overfull cycles are censored; unknown readings reset but provide no rate.',
          'The model includes month and BW school-vacation effects; sparse histories borrow material rates.',
          'Risk and forecast bands are model estimates, not measured live occupancy or a service guarantee.',
          'Coordinates retain source provenance; anonymous UUID assignments may be synthetic.',
          'OSRM supplies car-street distances, driving times and road geometry. No aerial-distance or fixed-time fallback is used.',
          'Each truck serves a compact angular sector across its loads; kilometers are minimized within fleet, sector, payload and shift constraints.',
          'Car profiles do not establish truck-specific height, weight or access permissions.',
          'Routing uses conservative integer loads, volume, payload, shifts and intermediate/final unloading.',
          'A time-limited heuristic gives a fleet recommendation, not a proven global optimum.'])



def selected_day_state(payload):
    """End-of-selected-day fill after recorded visits, never a stale pre-emptying reading."""
    df = readings(payload)
    model, _ = fit(df)
    last = df.groupby('container', sort=True).tail(1)
    target = pd.Timestamp(payload['asOf'])
    if model is not None and not last.empty:
        targets = [target] * len(last)
        predictions = model.predict(last.container, last.date, targets, thresholds=(100,))
        lower = model.fill_quantile(last.container, last.date, targets, .1)
        upper = model.fill_quantile(last.container, last.date, targets, .9)
    bins = []
    for index, row in enumerate(last.itertuples()):
        days = int((target-row.date).days)
        value = low = high = None
        status = 'unknown'
        if days == 0:
            # The visit confirms a reset even when its pre-emptying reading was unknown.
            value = low = high = 0.0
            status = 'emptied'
        elif model is not None and row.material in model.midx:
            candidate = float(predictions.iloc[index].mean_fill)
            lo, hi = float(lower[index]), float(upper[index])
            if all(math.isfinite(v) and 0 <= v <= 100 for v in (candidate,lo,hi)) and lo <= hi:
                value, low, high, status = candidate, lo, hi, 'estimated'
        bins.append(dict(locationId=row.site,material=row.material,lastEmptied=iso(row.date),daysSinceEmptied=days,
            expectedFillPercent=value,lower=low,upper=high,status=status))
    return dict(asOf=payload['asOf'],semantics='after-recorded-emptyings',
        lastObservationDate=None if df.empty else iso(df.date.max()),bins=bins,
        note='Selected-day estimates assume recorded visits emptied the container. Subsequent fill uses the seasonal cycle model, with material-rate borrowing where available. Model bands are uncalibrated. Only recorded collections reset a bin; a proposal or date change does not record a collection.')


def forecast(payload):
    df, cfg = readings(payload), config(payload['settings'])
    model, _ = fit(df)
    key = payload['locationId']+'|'+payload['material']
    history = df[df.container.eq(key)]
    if history.empty or model is None:
        raise ValueError('No eligible history or completed cycles for this forecast.')
    last = history.date.max()
    day = next_day(payload['asOf'],cfg)
    targets = pd.date_range(day, periods=int(payload.get('horizonDays',60))+1)
    containers, starts = [key]*len(targets), [last]*len(targets)
    pr = model.predict(containers, starts, targets, thresholds=(100,))
    lo, hi = model.fill_quantile(containers,starts,targets,.1),model.fill_quantile(containers,starts,targets,.9)
    return dict(asOf=payload['asOf'],locationId=payload['locationId'],material=payload['material'],lastEmptied=iso(last),
        history=[dict(date=iso(r.date),fill=None if r.overfull else r.fill,isOverfull=bool(r.overfull)) for r in history.itertuples()],
        points=[dict(date=iso(t),expectedFill=float(pr.iloc[i].mean_fill),lower=float(lo[i]),upper=float(hi[i]),risk=float(pr.iloc[i].p_ge_100)) for i,t in enumerate(targets)],
        medianDaysToFull=float(model.days_to_full([key],[last])[0]),
        note='Projected if not emptied again. The 10–90% model band is not a calibrated service guarantee.')


def simulation(payload):
    df, cfg = readings(payload), config(payload['settings'])
    start,end = pd.Timestamp(payload['start']),pd.Timestamp(payload['end'])
    if not (start <= end <= pd.Timestamp(payload['asOf'])) or (end-start).days > 30:
        raise ValueError('Simulation must contain 1–31 days and end on or before the history cutoff.')
    training = df[df.date < start]
    model, iv = fit(training)
    if model is None:
        raise ValueError('Choose a later simulation start: no completed training cycles exist before it.')
    known = set(training.container)
    eligible = df[df.container.isin(known) & (df.date <= end)]
    locs = places(payload,eligible.site.unique(),cfg)
    if not set(eligible.site).issubset({r['locationId'] for r in payload['locations']}):
        raise ValueError('Street-route simulation needs coordinates for every known site. Upload location coordinates with the readings.')
    roads = enable_street_routing(cfg)
    twin = Twin(model,eligible,start=iso(start),end=iso(end),seed=int(payload.get('seed',7)))
    limit = min(int(payload['settings'].get('solverTimeLimitSeconds',3)),2)
    baseline = run_baseline(twin,locs,cfg,route=True,time_limit=limit)
    dynamic = run_policy(twin,model,cfg,locs,route=True,time_limit=limit)
    median_profiles = profiles(training,start)
    median = run_median_policy(twin,median_profiles,cfg,locs,limit)
    comparison = forecast_comparison(eligible,training,model,median_profiles,start,end)
    state = training.groupby('container',sort=True).tail(1)[['container','site','material','date']].rename(columns={'date':'last_empty'})
    check_day = start
    while check_day.day_of_week not in cfg.working_weekdays:
        check_day += pd.Timedelta(days=1)
    check_stops,_ = select_stops(assess_bins(model,state,check_day,cfg),locs,cfg)
    check = optimization_check(check_stops,cfg)
    check['date'] = iso(check_day)
    scenarios = []
    for name,label,result in [('historical','Historical visit calendar',baseline),('dynamic','Forecast-driven policy',dynamic),('zakaria','Cycle-median policy (80% / 60%)',median)]:
        daily = result.pop('daily')
        if daily.empty:
            daily = pd.DataFrame(columns=['date','stops','bins','hours','trucks','dropped_mandatory'])
        scenarios.append(dict(name=name,label=label,**result,
            costs=operating_cost(float(daily.get('km',pd.Series(dtype=float)).sum()),int(daily.get('trucks',pd.Series(dtype=float)).sum()),payload['settings']),
            distanceKm=float(daily.get('km',pd.Series(dtype=float)).sum()),
            hours=float(daily.get('hours',pd.Series(dtype=float)).sum()),truckDays=int(daily.get('trucks',pd.Series(dtype=float)).sum()),
            missedMandatory=int(daily.get('dropped_mandatory',pd.Series(dtype=float)).sum()),
            daily=[{**r,'date':iso(r['date'])} for r in daily.to_dict('records')]))
    frontier = []
    for threshold in (.35,.5,.7,.82,.9):
        result = run_policy(twin,model,cfg,route=False,must_p=threshold)
        result.pop('daily')
        frontier.append(dict(threshold=threshold,**result))
    return dict(routing=roads.describe(),asOf=payload['asOf'],start=iso(start),end=iso(end),seed=int(payload.get('seed',7)),settings=payload['settings'],
        forecastComparison=comparison,optimizationCheck=check,
        dataset=evidence(training,{**payload,'asOf':iso(start-pd.Timedelta(days=1))}),
        knownBins=len(known),trainingCycles=len(iv),trainingThrough=iso(start-pd.Timedelta(days=1)),scenarios=scenarios,frontier=frontier,
        effectiveSolverTimeSeconds=limit,
        assumptions=['Simulated outcomes, not measured savings or a validation of counterfactual occupancy.',
          'The simulation uses a cycle-rate model fitted strictly before simulation start; the planner uses the same vintage.',
          'All three policies start identically and use a common seeded cycle-multiplier table.',
          'All three policies reset only bins at actually served sites; missed mandatory service remains visible.',
          'The historical scenario replays recorded visit dates, subject to the same fleet/load/shift and working-calendar limits.',
          'Historical route loads use the frozen forecast, not future simulated true fill. Capacity feasibility concerns forecast loads; realized filling can differ.',
          'Frontier runs are selection-only mandatory-site scenarios without routing/capacity limits.',
          'The seed controls demand multipliers; wall-clock-limited route searches can still vary between runs.',
          'The frozen cycle-median policy uses 80% urgent / 60% same-site thresholds, with the common route optimizer and the same fleet constraints.',
          'Persistence is scored against real held-out readings, not treated as a dispatch policy.',
          'The twin shares the seasonal forecast model family and can favor it. The real-reading benchmark is separate. Repeat with other seeds and settings before drawing conclusions.'])


def dataset_validation(payload):
    """Validate the whole upload and summarize it without fitting or routing."""
    import hashlib
    observations, warnings, kind = source(payload)
    if not observations:
        raise DatasetValidationError([dict(rule_id='empty',row_number=0,message='The CSV has no collection records. Add at least one data row.')])
    dates = [r['date'] for r in observations]
    return dict(source=kind,fingerprint=hashlib.sha256(payload['csv'].encode('utf-8')).hexdigest(),
        rows=len(observations),locations=len({r['locationId'] for r in observations}),
        bins=len({(r['locationId'],r['material']) for r in observations}),
        firstDate=min(dates) if dates else None,lastDate=max(dates) if dates else None,
        materials={m:sum(r['material']==m for r in observations) for m in ('brown','green','white')},warnings=warnings)


def capacity_scenario(payload):
    from integrations.capacity_planning import compare, validate
    df = readings(payload)
    cfg = config(payload['settings'])
    enable_street_routing(cfg)
    try:
        validate(payload['capacityScenario'])
        if payload['capacityScenario'].get('optimize'):
            from integrations.joint_planning import optimize
            return optimize(df, payload, cfg, street_route_shapes)
        return compare(df, payload, cfg)
    except ValueError as error:
        raise DatasetValidationError([dict(rule_id='capacity_scenario', row_number=0, message=str(error))]) from error


def clean(value):
    if isinstance(value,dict): return {str(k):clean(v) for k,v in value.items()}
    if isinstance(value,(list,tuple)): return [clean(v) for v in value]
    if isinstance(value,np.generic): value=value.item()
    return None if isinstance(value,float) and not math.isfinite(value) else value


if __name__ == '__main__':
    try:
        payload = json.load(sys.stdin)
        with contextlib.redirect_stdout(io.StringIO()):
            result = {'proposal':proposal,'forecast':forecast,'simulation':simulation,'state':selected_day_state,'capacity':capacity_scenario,'dataset':dataset_validation}[payload['action']](payload)
        print(json.dumps(clean(result),allow_nan=False))
    except Exception as exc:
        print(json.dumps({'error':str(exc), **({'validation':{'errors':exc.errors,'warnings':exc.warnings}} if isinstance(exc,DatasetValidationError) else {})}))
        sys.exit(2)
