"""Constant-demand, capacity/cadence counterfactuals with actual street routing."""
from copy import deepcopy
from decimal import Decimal, ROUND_HALF_UP
import math

import numpy as np
import pandas as pd
from fillinq.routing import plan_routes

MATERIALS = ('brown', 'green', 'white')
MONTH_DAYS = 365.25 / 12


def validate(request):
    def number(key, minimum, maximum, integer=False, value=None):
        v = request.get(key) if value is None else value
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or not minimum <= v <= maximum or (integer and int(v) != v):
            raise ValueError(f'{key} must be {"an integer " if integer else ""}between {minimum} and {maximum}.')
    number('days', 7, 31, True)
    for key in ('baselineIntervalDays', 'alternativeIntervalDays'):
        number(key, 1, 28, True)
    number('containerCostPerMonthEuro', 0, 10000)
    for key in ('baselineContainers', 'alternativeContainers'):
        counts = request.get(key, {})
        if not isinstance(counts, dict) or set(counts) != set(MATERIALS):
            raise ValueError(f'{key} must specify brown, green and white counts.')
        for material in MATERIALS:
            number(f'{key}.{material}', 1, 20, True, counts[material])
    if request.get('optimize'):
        number('optimizationWeeks',1,8,True)
        number('targetFillPercent',50,100)
        number('maxContainersPerType',1,20,True)
        number('maxContainersPerSite',1,60,True)
        number('minIntervalDays',1,56,True)
        number('maxIntervalDays',1,56,True)
        if request['minIntervalDays']>min(request['maxIntervalDays'],request['optimizationWeeks']*7):
            raise ValueError('Minimum interval must fit the repeating cycle and maximum interval.')
        seen_sites=set()
        for row in request.get('siteLimits',[]):
            if not row.get('locationId') or row['locationId'] in seen_sites:raise ValueError('Site limits must be valid and unique.')
            seen_sites.add(row['locationId'])
            number('site maximum',1,60,True,row.get('maxContainers'))
    overrides = request.get('overrides', [])
    if not isinstance(overrides, list) or len(overrides) > 1500:
        raise ValueError('At most 1500 site/material overrides are supported.')
    seen = set()
    for row in overrides:
        key = (row.get('locationId'), row.get('material'))
        if not key[0] or key[1] not in MATERIALS or key in seen:
            raise ValueError('Site/material overrides must be valid and unique.')
        seen.add(key)
        for name in ('baselineCount', 'alternativeCount'):
            number(name, 1, 20, True, row.get(name))


def demand_streams(df, request, container_litres):
    """No lower-bound/unknown extrapolations, rate floor, or future observations."""
    rows = df.sort_values(['container', 'date']).copy()
    rows['gap'] = rows.groupby('container').date.diff().dt.days
    ordinary = rows[(rows.gap > 0) & rows['fill'].notna() & ~rows.censored & ~rows.overfull].copy()
    ordinary['dailyPercent'] = ordinary['fill'] / ordinary.gap
    rates = ordinary.groupby('container').dailyPercent.median().to_dict()
    samples = ordinary.groupby('container').size().to_dict()
    overrides = {(r['locationId'], r['material']): r for r in request.get('overrides', [])}
    known = set(zip(rows.site, rows.material))
    if set(overrides) - known:
        raise ValueError('An override names a site/material without history through the selected cutoff.')
    streams, excluded = [], []
    for row in rows.groupby('container', sort=True).tail(1).itertuples():
        if row.container not in rates:
            excluded.append(dict(locationId=row.site, material=row.material))
            continue
        override = overrides.get((row.site, row.material), {})
        baseline = override.get('baselineCount', request['baselineContainers'][row.material])
        alternative = override.get('alternativeCount', request['alternativeContainers'][row.material])
        # Baseline count states the physical capacity represented by the historical
        # percentage. The SAME inferred incoming volume feeds both alternatives.
        daily = rates[row.container] / 100 * baseline * container_litres
        streams.append(dict(locationId=row.site, material=row.material, dailyLitres=daily,
            baselineCount=baseline, alternativeCount=alternative, cycles=int(samples[row.container])))
    return streams, excluded


def filling_summary(streams, container_litres):
    result = []
    for material in MATERIALS:
        rows = [s for s in streams if s['material'] == material]
        positive = [s for s in rows if s['dailyLitres'] > 0]
        def average(count):
            return float(np.mean([s[count] * container_litres / s['dailyLitres'] for s in positive])) if positive else None
        result.append(dict(material=material, supportedStreams=len(rows), positiveStreams=len(positive),
            zeroDemandStreams=len(rows)-len(positive), historicalCycles=sum(s['cycles'] for s in rows),
            baselineAverageDays=average('baselineCount'), alternativeAverageDays=average('alternativeCount')))
    return result


def run_schedule(streams, locations, cfg, request, start, alternative, settings):
    counts = np.array([s['alternativeCount' if alternative else 'baselineCount'] for s in streams], dtype=int)
    capacity = counts * cfg.container_volume_m3 * 1000
    demand = np.array([s['dailyLitres'] for s in streams])
    sites = sorted(set(s['locationId'] for s in streams))
    indices = {site: np.array([i for i, s in enumerate(streams) if s['locationId'] == site], dtype=int) for site in sites}
    interval = request['alternativeIntervalDays' if alternative else 'baselineIntervalDays']
    # Spread the inventory across the interval. Actual due dates remain calendar
    # dates: holidays/weekends defer a due stop, they do not erase it.
    phase = {site: i % interval for i, site in enumerate(sites)}
    pending, stored, daily = set(), np.zeros(len(streams)), []
    total_spill, full_days, emptied, visits, collected = 0., 0, 0, 0, 0.
    for day_index in range(request['days']):
        date = start + pd.Timedelta(days=day_index)
        incoming = stored + demand
        spill = float(np.maximum(incoming - capacity, 0).sum())
        total_spill += spill
        stored = np.minimum(incoming, capacity)
        full_days += int(((incoming >= capacity - 1e-8) & (demand > 0)).sum())
        pending.update(site for site in sites if day_index % interval == phase[site])
        stops = []
        for site in sorted(pending):
            ids = indices[site]
            if stored[ids].sum() <= 1e-9:
                pending.discard(site)  # No invented work for a zero-demand site.
                continue
            point = locations.get(site)
            if point is None:
                continue
            volume = float(stored[ids].sum())
            stop = dict(site=site,lat=point['latitude'],lon=point['longitude'],vol_l=volume,
                kg=volume*cfg.glass_density_t_m3,n_bins=int(counts[ids].sum()),must=True,value=1.)
            for material in MATERIALS:
                stop[f'{material}_l'] = sum(float(stored[i]) for i in ids if streams[i]['material'] == material)
            stops.append(stop)
        served = set()
        km, hours, trucks = 0., 0., 0
        if date.day_of_week in cfg.working_weekdays and stops:
            frame = pd.DataFrame(stops)
            route = plan_routes(frame,cfg,time_limit_s=min(1, settings.get('solverTimeLimitSeconds', 1)))
            km, hours, trucks = float(route.kpis['km']),float(route.kpis['hours']),int(route.kpis['trucks'])
            served = {site for truck in route.routes for trip in truck['trips'] for site in trip['stops']}
        day_bins = 0
        for site in served:
            ids = indices[site]
            collected += float(stored[ids].sum())
            stored[ids] = 0
            day_bins += int(counts[ids].sum())
        pending.difference_update(served)
        emptied += day_bins
        visits += len(served)
        daily.append(dict(date=date.date().isoformat(),truckDays=trucks,distanceKm=km,hours=hours,
            containersEmptied=day_bins,siteVisits=len(served),pendingSites=len(pending),spillLitres=spill))
    truck_days = sum(d['truckDays'] for d in daily)
    distance = sum(d['distanceKm'] for d in daily)
    money = lambda v: float(Decimal(str(v)).quantize(Decimal('.01'),rounding=ROUND_HALF_UP))
    fixed, per_km, container_rate = settings.get('fixedTruckCostEuro',0),settings.get('costPerKmEuro',0),request['containerCostPerMonthEuro']
    fixed_cost, road_cost = money(truck_days*fixed),money(distance*per_km)
    installed = int(counts.sum())
    container_cost = money(installed*container_rate*request['days']/MONTH_DAYS)
    configured = any(v > 0 for v in (fixed, per_km, container_rate))
    total = money(fixed_cost+road_cost+container_cost) if configured else None
    return dict(name='alternative' if alternative else 'baseline',intervalDays=interval,
        installedContainers=installed,truckDays=truck_days,peakTrucks=max((d['truckDays'] for d in daily),default=0),
        distanceKm=distance,workingHours=sum(d['hours'] for d in daily),emptyingHours=emptied*cfg.service_min_per_bin/60,
        containersEmptied=emptied,siteVisits=visits,demandLitres=float(demand.sum()*request['days']),
        collectedLitres=collected,remainingLitres=float(stored.sum()),spillLitres=total_spill,fullStreamDays=full_days,
        pendingSites=len(pending),pendingSiteDays=sum(d['pendingSites'] for d in daily),daily=daily,
        costs=dict(configured=configured,partial=configured and (fixed == 0 or container_rate == 0),drivingIncluded=fixed > 0 and per_km == 0,
            truckEuro=fixed_cost if fixed>0 else None,roadEuro=road_cost if per_km>0 else None,
            containerEuro=container_cost if container_rate>0 else None,totalEuro=total,
            monthlyEquivalentEuro=money(total*MONTH_DAYS/request['days']) if total is not None else None))


def compare(df, payload, cfg):
    request = payload['capacityScenario']
    validate(request)
    if not cfg.working_weekdays:
        raise ValueError('Select at least one operating weekday.')
    streams, excluded = demand_streams(df,request,cfg.container_volume_m3*1000)
    locations = {r['locationId']:r for r in payload.get('locations',[])}
    start = pd.Timestamp(payload['asOf']) + pd.Timedelta(days=1)
    baseline = run_schedule(streams,locations,cfg,request,start,False,payload['settings'])
    # Identical scenarios reuse the exact routed realization, avoiding numerical
    # solver-time variation masquerading as a benefit.
    same = request['baselineIntervalDays'] == request['alternativeIntervalDays'] and all(s['baselineCount']==s['alternativeCount'] for s in streams)
    alternative = {**deepcopy(baseline),'name':'alternative'} if same else run_schedule(streams,locations,cfg,request,start,True,payload['settings'])
    comparable = bool(streams) and not excluded and all(s['locationId'] in locations for s in streams) and baseline['pendingSites'] == 0 and alternative['pendingSites'] == 0 and alternative['spillLitres'] <= baseline['spillLitres']+1e-6 and alternative['collectedLitres'] >= baseline['collectedLitres']-1e-6 and alternative['pendingSites'] <= baseline['pendingSites']
    return dict(asOf=payload['asOf'],start=start.date().isoformat(),end=(start+pd.Timedelta(days=request['days']-1)).date().isoformat(),
        days=request['days'],supportedStreams=len(streams),excludedStreams=excluded,
        missingCoordinateSites=sorted(set(s['locationId'] for s in streams)-set(locations)),
        fillingTimes=filling_summary(streams,cfg.container_volume_m3*1000),scenarios=[baseline,alternative],
        comparableService=comparable,settings=payload['settings'],request=request,
        assumptions=[
            'Counterfactual planning estimate, not measured savings. Synthetic site/history assignments remain synthetic.',
            'Incoming glass volume is identical in both scenarios: median ordinary historical percent/day × assumed baseline physical capacity. Full, overfull and unknown cycles are excluded; zero rates are retained. No borrowing for unsupported streams.',
            'Counts apply per site and glass type present in the history. Baseline counts are assumptions about the capacity represented by historical percentages, not an inventory recovered from the source data.',
            'All modelled streams start empty; this is a fresh-cycle comparison, not a prediction of current occupancy. Volume is shared evenly across containers of the same type.',
            'Schedules are staggered by site order across calendar-day intervals. Due visits wait for an operating weekday; missed visits retry. No public-holiday shutdown is inferred.',
            'Every scheduled visit empties all modelled glass types at the site. Added containers add service time. Stops must fit one load, compartment limits and the shift; rejected stops remain pending.',
            'Road distances and durations use the car street network and include unloads and yard returns. Solver results may vary for different scenarios. Vehicle-specific road restrictions are not modelled.',
            'Excess above installed capacity is recorded as spilled glass and is not silently collected later. Demand equals collected + remaining + spilled volume.',
            'The confirmed €500 truck-day rate includes truck, driver and driving kilometres. Zero additional €/km means driving is included, not unpriced. Any positive €/km is an explicitly added charge outside the daily package; container rental/ownership remains separate.',
            'Monthly equivalent scales this period to 30.4375 days; it is not an annual or seasonally validated forecast. Full stream-days count site/material streams, not individual physical containers.'
        ])
