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
sys.path.insert(0, str(here / 'vendor' if (here / 'vendor' / 'fillinq').exists() else here.parents[1] / 'Omar-Work'))
import numpy as np
import pandas as pd
from fillinq.config import OpsConfig
from fillinq.data import load_readings, build_intervals
from fillinq.forecast import RateModel
from fillinq.policy import assess_bins, select_stops, window_end
from fillinq.routing import plan_routes
from fillinq.simulate import Twin, run_baseline, run_policy
from integrations.dataset import source, evidence, DatasetValidationError
from integrations.comparison import profiles, run_median_policy, forecast_comparison, optimization_check


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
    cfg.working_weekdays = tuple(i for i,key in enumerate(['workMonday','workTuesday','workWednesday','workThursday','workFriday','workSaturday','workSunday']) if settings.get(key, i<5))
    if not cfg.working_weekdays:
        raise ValueError('Choose at least one working collection day.')
    return cfg


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
    missing = set(stops.site) - set(coords) if cfg.fixed_travel_min == 0 else set()
    plan = plan_routes(stops[~stops.site.isin(missing)].copy(), cfg,
                       time_limit_s=payload['settings'].get('solverTimeLimitSeconds',3))
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
    routes = [dict(truck=r['truck'], hours=r['hours'], distanceKm=None if cfg.fixed_travel_min else r['km'], bins=r['bins'],
        trips=[dict(stops=t['stops'], weightKg=t['weight_t']*1000, volumeL=t['volume_m3']*1000) for t in r['trips']]) for r in plan.routes]
    unserved = []
    for site in [*plan.dropped_mandatory,*plan.dropped_optional,*sorted(missing)]:
        row = stop_lookup.loc[site]
        reason = ('missing_coordinates' if site in missing else plan.reasons[site] if site in plan.reasons else 'exceeds_truck_capacity' if row.kg > cfg.truck_payload_kg or row.vol_l > cfg.truck_volume_l
                  else 'fleet_limit' if site in mandatory_sites else 'optional_not_scheduled')
        unserved.append(dict(locationId=site, mandatory=site in mandatory_sites, reason=reason))
    k = plan.kpis
    return dict(dataset=evidence(df,payload),asOf=payload['asOf'], planDate=iso(day), windowEnd=iso(window_end(day,cfg)),settings=payload['settings'],
        model=dict(engine='omar-python', bins=len(state), cycles=len(iv), censoredCycles=int(iv.censored.sum()),
            sigma=model.sigma if model else 0, tau=model.tau if model else 0,
            materialRatePercentPerDay=model.summary()['material_rate_pct_per_day'] if model else {},
            vacationMultiplier=float(np.exp(model.g)) if model else None,
            seasonality=model.seasonality_table().to_dict('records') if model else []), bins=bins,
        stops=[dict(locationId=r.site,mandatory=bool(r.must),risk=r.value,bins=int(r.n_bins),volumeL=r.vol_l,weightKg=r.kg,
                    latitude=coords.get(r.site,{}).get('latitude'), longitude=coords.get(r.site,{}).get('longitude'),
                    isSynthetic=coords.get(r.site,{}).get('isSynthetic',True),
                    materials=sorted(take.loc[take.site.eq(r.site),'material'].tolist())) for r in stops.itertuples()],
        plan=dict(routes=routes,unserved=unserved,totals=dict(trucks=k['trucks'],trips=k['trips'],stops=k['stops'],bins=k['bins'],
            hours=k['hours'],distanceKm=None if cfg.fixed_travel_min else k['km'], weightT=k['weight_t'],volumeM3=k['volume_m3'],
            loadsByCapacity=max(math.ceil(k['weight_t']/cfg.truck_payload_t),math.ceil(k['volume_m3']/cfg.truck_volume_m3) if cfg.truck_volume_m3 else 0))),
        assumptions=['Omar’s Python model and OR-Tools router run on this request’s history prefix only.',
          'A recorded visit empties the bin. Full/overfull cycles are censored; unknown readings reset but provide no rate.',
          'The model includes month and BW school-vacation effects; sparse histories borrow material rates.',
          'Risk and forecast bands are model estimates, not measured live occupancy or a service guarantee.',
          'Coordinates retain source provenance; anonymous UUID assignments may be synthetic.',
          'Fixed travel time reports no road distance; coordinate mode uses haversine × detour.',
          'Routing uses conservative integer loads, volume, payload, shifts and intermediate/final unloading.',
          'A time-limited heuristic gives a fleet recommendation, not a proven global optimum.'])


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
    if cfg.fixed_travel_min == 0 and not set(eligible.site).issubset({r['locationId'] for r in payload['locations']}):
        raise ValueError('Coordinate-mode simulation needs locations for every known site.')
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
    for name,label,result in [('historical','Historical visit calendar',baseline),('dynamic','Omar forecast-driven policy',dynamic),('zakaria','Zakaria median policy (80% / 60%)',median)]:
        daily = result.pop('daily')
        if daily.empty:
            daily = pd.DataFrame(columns=['date','stops','bins','hours','trucks','dropped_mandatory'])
        scenarios.append(dict(name=name,label=label,**result,
            hours=float(daily.get('hours',pd.Series(dtype=float)).sum()),truckDays=int(daily.get('trucks',pd.Series(dtype=float)).sum()),
            missedMandatory=int(daily.get('dropped_mandatory',pd.Series(dtype=float)).sum()),
            daily=[{**r,'date':iso(r['date'])} for r in daily.to_dict('records')]))
    frontier = []
    for threshold in (.35,.5,.7,.82,.9):
        result = run_policy(twin,model,cfg,route=False,must_p=threshold)
        result.pop('daily')
        frontier.append(dict(threshold=threshold,**result))
    return dict(asOf=payload['asOf'],start=iso(start),end=iso(end),seed=int(payload.get('seed',7)),settings=payload['settings'],
        forecastComparison=comparison,optimizationCheck=check,
        dataset=evidence(training,{**payload,'asOf':iso(start-pd.Timedelta(days=1))}),
        knownBins=len(known),trainingCycles=len(iv),trainingThrough=iso(start-pd.Timedelta(days=1)),scenarios=scenarios,frontier=frontier,
        effectiveSolverTimeSeconds=limit,
        assumptions=['Simulated outcomes, not measured savings or a validation of counterfactual occupancy.',
          'Omar’s digital twin uses his rate model fitted strictly before simulation start; the planner uses the same vintage.',
          'All three policies start identically and use a common seeded cycle-multiplier table.',
          'All three policies reset only bins at actually served sites; missed mandatory service remains visible.',
          'The historical scenario replays recorded visit dates, subject to the same fleet/load/shift and working-calendar limits.',
          'Historical route loads use the frozen forecast, not future simulated true fill. Capacity feasibility concerns forecast loads; realized filling can differ.',
          'Frontier runs are selection-only mandatory-site scenarios without routing/capacity limits.',
          'The seed controls demand multipliers; wall-clock-limited route searches can still vary between runs.',
          'Zakaria’s frozen median policy uses his 80% urgent / 60% same-site thresholds, with Omar’s router and the same fleet constraints.',
          'Kaise’s persistence is scored against real held-out readings, not treated as a dispatch policy.',
          'The twin shares Omar’s forecast model family and can favor it. The real-reading benchmark is separate. Repeat with other seeds and settings before drawing conclusions.'])


def clean(value):
    if isinstance(value,dict): return {str(k):clean(v) for k,v in value.items()}
    if isinstance(value,(list,tuple)): return [clean(v) for v in value]
    if isinstance(value,np.generic): value=value.item()
    return None if isinstance(value,float) and not math.isfinite(value) else value


if __name__ == '__main__':
    try:
        payload = json.load(sys.stdin)
        with contextlib.redirect_stdout(io.StringIO()):
            result = {'proposal':proposal,'forecast':forecast,'simulation':simulation}[payload['action']](payload)
        print(json.dumps(clean(result),allow_nan=False))
    except Exception as exc:
        print(json.dumps({'error':str(exc), **({'validation':{'errors':exc.errors,'warnings':exc.warnings}} if isinstance(exc,DatasetValidationError) else {})}))
        sys.exit(2)
