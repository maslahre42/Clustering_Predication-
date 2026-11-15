"""Bounded joint container/calendar search, followed by actual street-route checks.

The CP-SAT master prices paid service time, not invented road distances. Only
routed feasible candidates can become recommendations; no global optimum claim.
"""
from copy import deepcopy
from decimal import Decimal, ROUND_HALF_UP
import math

import numpy as np
import pandas as pd
from ortools.sat.python import cp_model
from fillinq.routing import plan_routes
from .capacity_planning import MATERIALS, MONTH_DAYS, demand_streams, filling_summary


def cyclic_gap(days, horizon):
    days = sorted(set(days))
    return max(((days[(i+1)%len(days)]-day) % horizon or horizon) for i,day in enumerate(days)) if days else horizon+1


def working_dates(start, horizon, weekdays):
    return [d for d in range(horizon) if (start+pd.Timedelta(days=d)).day_of_week in weekdays]


def baseline_calendar(streams, workdays, horizon, interval):
    # A repeating calendar with evenly spaced nominal visits, moved forward to a
    # working day. Its REAL resulting gaps/fill violations are reported.
    sites = sorted(set(s['locationId'] for s in streams))
    phases = {site:i for i,site in enumerate(sites)}
    n = max(1,math.ceil(horizon/interval))
    calendars=[]
    for s in streams:
        if s['dailyLitres']<=0:
            calendars.append([]);continue
        phase=phases[s['locationId']] % max(1,math.ceil(horizon/n))
        nominal=[(phase+int(i*horizon/n))%horizon for i in range(n)]
        calendars.append(sorted({min(workdays,key=lambda d:(d-day)%horizon) for day in nominal}))
    return calendars


def stream_gap(stream,count,horizon,cfg,request):
    share=max(1,request.get('_positiveTypes',{}).get(stream['locationId'],1))
    limit=request['targetFillPercent']/100*count*cfg.container_volume_m3*1000
    # Conservative per-type shares ensure a same-site combination fits one load.
    # Routing still checks exact volumes, compartments, unloading and street time.
    limit=min(limit,cfg.truck_payload_kg/cfg.glass_density_t_m3/share-1e-7,cfg.truck_volume_l/share-1e-7,
              getattr(cfg,'compartment_litres',{}).get(stream['material'],math.inf))
    return min(horizon,request['maxIntervalDays'],math.floor(limit/stream['dailyLitres']+1e-9))


def seed_choice(streams,workdays,horizon,cfg,request,storage=False):
    sites=sorted(set(s['locationId'] for s in streams))
    phases={site:i*len(workdays)//max(1,len(sites)) for i,site in enumerate(sites)}
    counts=[];calendars=[]
    for s in streams:
        choices=[]
        for count in range(1,request['maxContainersPerType']+1):
            if s['dailyLitres']<=0:
                choices.append((count,[]));continue
            gap=stream_gap(s,count,horizon,cfg,request)
            if gap<request['minIntervalDays']:continue
            n=max(1,math.ceil(horizon/gap));phase=workdays[phases[s['locationId']]]
            days=sorted({min(workdays,key=lambda d:(d-(phase+int(j*horizon/n))%horizon)%horizon) for j in range(n)})
            while cyclic_gap(days,horizon)>gap:
                available=[w for w in workdays if w not in days]
                if not available:break
                best=min(available,key=lambda w:(cyclic_gap(days+[w],horizon),sum(min((w-d)%horizon,(d-w)%horizon) for d in days)*-1))
                days=sorted(days+[best])
            minimum=min(((days[(i+1)%len(days)]-d)%horizon or horizon) for i,d in enumerate(days))
            if cyclic_gap(days,horizon)<=gap and minimum>=request['minIntervalDays']:choices.append((count,days))
        if not choices:return None
        if storage:
            # Count×visits prices real emptying work; fewer road stops break ties.
            # This guides candidates only: actual street costs select the winner.
            def proxy(pair):
                count,days=pair
                rental=count*request['containerCostPerMonthEuro']*horizon/MONTH_DAYS
                service=count*len(days)*cfg.service_min_per_bin/(cfg.shift_hours*60)*request['fixedTruckCostEuro']
                return rental+service,len(days),count
            chosen=min(choices,key=proxy)
        else:chosen=min(choices,key=lambda pair:(pair[0],len(pair[1])))
        counts.append(chosen[0]);calendars.append(chosen[1])
    return counts,calendars


def refine_choice(streams,choice,horizon,cfg,request):
    counts,calendars=deepcopy(choice)
    for i,s in enumerate(streams):
        if s['dailyLitres']<=0:
            counts[i]=1;calendars[i]=[];continue
        # Drop capacity which cannot affect this calendar's peak occupancy.
        required=s['dailyLitres']*cyclic_gap(calendars[i],horizon)/(cfg.container_volume_m3*1000*request['targetFillPercent']/100)
        counts[i]=max(1,min(counts[i],math.ceil(required-1e-9)))
        while len(calendars[i])>1:
            removable=[d for d in calendars[i] if cyclic_gap([w for w in calendars[i] if w!=d],horizon)<=stream_gap(s,counts[i],horizon,cfg,request)]
            if not removable:break
            calendars[i].remove(removable[0])
    return counts,calendars


def master(streams, reserved, workdays, horizon, cfg, request, conservative=False, hint=None):
    model=cp_model.CpModel();n=len(streams)
    max_count=request['maxContainersPerType'];target=request['targetFillPercent']/100
    site_limits={r['locationId']:r['maxContainers'] for r in request.get('siteLimits',[])}
    counts=[];visits=[];empties=[]
    for i,s in enumerate(streams):
        count=model.new_int_var(1,max_count,f'count{i}');counts.append(count)
        x={d:model.new_bool_var(f'v{i}_{d}') for d in workdays};visits.append(x)
        by_day={}
        for d in workdays:
            e=model.new_int_var(0,max_count,f'e{i}_{d}')
            model.add_multiplication_equality(e,[count,x[d]]);by_day[d]=e
        empties.append(by_day)
        if s['dailyLitres']<=0:
            model.add(count==1)
            for v in x.values():model.add(v==0)
            continue
        options=[]
        for c in range(1,max_count+1):
            option=model.new_bool_var(f'c{i}_{c}');options.append(option)
            model.add(count==c).only_enforce_if(option)
            gap=stream_gap(s,c,horizon,cfg,request)
            if gap<request['minIntervalDays']:
                model.add(option==0);continue
            for d in range(horizon):
                window=[x[w] for w in workdays if 1 <= (d-w)%horizon <= gap or (gap==horizon and w==d)]
                model.add(sum(window)>=1).only_enforce_if(option)
        model.add_exactly_one(options)
        for d in range(horizon):
            window=[x[w] for w in workdays if (w-d)%horizon<request['minIntervalDays']]
            if len(window)>1:model.add(sum(window)<=1)
    sites=sorted(set(s['locationId'] for s in streams))
    site_members={site:[i for i,s in enumerate(streams) if s['locationId']==site] for site in sites}
    site_visits={}
    for site,ids in site_members.items():
        model.add(sum(counts[i] for i in ids)+reserved.get(site,0)<=site_limits.get(site,request['maxContainersPerSite']))
        for d in workdays:
            y=model.new_bool_var(f's{site}_{d}');model.add_max_equality(y,[visits[i][d] for i in ids]);site_visits[site,d]=y
    shifts=[]
    # Service-time proxy, reserving 40% of the shift for driving and unloading.
    # Actual road costs, loads, shifts and compartments are checked afterwards.
    available_seconds=math.floor(cfg.shift_hours*3600*.60)
    for d in workdays:
        trucks=model.new_int_var(0,cfg.max_vehicles,f'trucks{d}');shifts.append(trucks)
        service=sum(empties[i][d]*math.ceil(cfg.service_min_per_bin*60) for i in range(n))
        service+=sum(site_visits[site,d]*math.ceil(cfg.service_min_per_stop*60) for site in sites)
        model.add(service<=available_seconds*trucks)
    installed=sum(counts);handled=sum(e for day in empties for e in day.values())
    rental_cents=round(request['containerCostPerMonthEuro']*horizon/MONTH_DAYS*100)
    day_cents=round(request['fixedTruckCostEuro']*100)
    money=day_cents*sum(shifts)+rental_cents*installed
    # Secondary terms are service/stock tie-breaks, not claimed monetary charges.
    tie_limit=1+n*max_count*(2*horizon+1)
    if conservative:model.minimize(installed*(day_cents*cfg.max_vehicles*len(workdays)+rental_cents*n*max_count+1)+money)
    else:model.minimize(money*tie_limit+installed*(horizon+1)+handled)
    if hint:
        seed_counts,seed_days=hint
        for i in range(n):
            model.add_hint(counts[i],seed_counts[i])
            for d in workdays:
                take=int(d in seed_days[i]);model.add_hint(visits[i][d],take);model.add_hint(empties[i][d],seed_counts[i]*take)
        for (site,d),variable in site_visits.items():model.add_hint(variable,int(any(d in seed_days[i] for i in site_members[site])))
        for d,variable in zip(workdays,shifts):
            service=sum(seed_counts[i]*cfg.service_min_per_bin*60 for i in range(n) if d in seed_days[i])
            service+=sum(cfg.service_min_per_stop*60 for site in sites if any(d in seed_days[i] for i in site_members[site]))
            model.add_hint(variable,min(cfg.max_vehicles,math.ceil(service/max(1,available_seconds))))
    solver=cp_model.CpSolver();solver.parameters.max_time_in_seconds=6
    solver.parameters.num_search_workers=4;solver.parameters.max_presolve_iterations=1;solver.parameters.random_seed=7
    status=solver.solve(model)
    status_name=solver.status_name(status)
    if status not in (cp_model.OPTIMAL,cp_model.FEASIBLE):return None,dict(status=status_name,proxyOnly=True)
    return (list(map(lambda c:solver.value(c),counts)),[[d for d in workdays if solver.value(x[d])] for x in visits]),dict(status=status_name,proxyOnly=True)


def evaluate(streams, counts, calendar, locations, cfg, request, start, name, settings):
    horizon=request['optimizationWeeks']*7
    demand=np.array([s['dailyLitres'] for s in streams]);capacity=np.array(counts)*cfg.container_volume_m3*1000
    # These are explicitly cyclic steady-state stocks, not today's occupancy.
    initial=np.array([demand[i]*(horizon-1-max(days)) if days else 0 for i,days in enumerate(calendar)])
    stored=initial.copy();pending=set();daily=[];events=[];route_plans=[]
    spill=collected=0.;violations=full_days=0;filled=[];site_ids={}
    for i,s in enumerate(streams):site_ids.setdefault(s['locationId'],[]).append(i)
    actual_days=[[] for _ in streams]
    max_fill=np.zeros(len(streams));visit_counts=np.zeros(len(streams),dtype=int)
    for d in range(horizon):
        date=start+pd.Timedelta(days=d);incoming=stored+demand
        percentages=np.divide(incoming,capacity,out=np.zeros(len(streams)),where=capacity>0)*100
        max_fill=np.maximum(max_fill,percentages)
        violations+=int(((percentages>request['targetFillPercent']+1e-6)&(demand>0)).sum())
        full_days+=int(((percentages>=100-1e-8)&(demand>0)).sum())
        spilled=float(np.maximum(incoming-capacity,0).sum());spill+=spilled;stored=np.minimum(incoming,capacity)
        pending.update(i for i,days in enumerate(calendar) if d in days)
        records=[];eligible={}
        for site,ids in site_ids.items():
            take=[i for i in ids if i in pending and stored[i]>1e-9]
            if not take or site not in locations:continue
            point=locations[site];volume=float(stored[take].sum())
            row=dict(site=site,lat=point['latitude'],lon=point['longitude'],vol_l=volume,kg=volume*cfg.glass_density_t_m3,
                n_bins=sum(counts[i] for i in take),must=True,value=1.)
            row.update({m+'_l':sum(float(stored[i]) for i in take if streams[i]['material']==m) for m in MATERIALS})
            records.append(row);eligible[site]=take
        routes=[];km=hours=0.;trucks=0;day_bins=0;served=set();plan=None
        if date.day_of_week in cfg.working_weekdays and records:
            frame=pd.DataFrame(records);plan=plan_routes(frame,cfg,time_limit_s=1)
            km=float(plan.kpis['km']);hours=float(plan.kpis['hours']);trucks=int(plan.kpis['trucks'])
            served={site for r in plan.routes for trip in r['trips'] for site in trip['stops']}
            routes=deepcopy(plan.routes)
            for site in served:
                for i in eligible[site]:
                    volume=float(stored[i]);fill=volume/capacity[i]*100;filled.append(fill)
                    events.append(dict(date=date.date().isoformat(),locationId=site,material=streams[i]['material'],containers=counts[i],fillPercent=fill,volumeL=volume))
                    collected+=volume;stored[i]=0;pending.discard(i);visit_counts[i]+=1;actual_days[i].append(d);day_bins+=counts[i]
        daily.append(dict(date=date.date().isoformat(),truckDays=trucks,distanceKm=km,hours=hours,containersEmptied=day_bins,
            siteVisits=len(served),stops=[dict(locationId=r['site'],latitude=r['lat'],longitude=r['lon'],materials=[m for m in MATERIALS if r[m+'_l']>0],bins=r['n_bins'],volumeL=r['vol_l'],weightKg=r['kg'],risk=None,mandatory=True) for r in records if r['site'] in served],pendingSites=len({streams[i]['locationId'] for i in pending}),spillLitres=spilled,routes=routes))
        route_plans.append((plan,records))
    money=lambda n:float(Decimal(str(n)).quantize(Decimal('.01'),rounding=ROUND_HALF_UP))
    truck_days=sum(d['truckDays'] for d in daily);km=sum(d['distanceKm'] for d in daily);installed=sum(counts)
    fixed=settings.get('fixedTruckCostEuro',0);extra=settings.get('costPerKmEuro',0);rental=request['containerCostPerMonthEuro']
    truck_cost=money(truck_days*fixed);road_cost=money(km*extra);rental_cost=money(installed*rental*horizon/MONTH_DAYS)
    total=money(truck_cost+road_cost+rental_cost) if any(v>0 for v in (fixed,extra,rental)) else None
    stable=bool(np.allclose(stored,initial,rtol=1e-8,atol=.001))
    limits={r['locationId']:r['maxContainers'] for r in request.get('siteLimits',[])}
    bounds=all(1<=c<=request['maxContainersPerType'] for c in counts) and all(sum(counts[i] for i in ids)+request.get('_reserved',{}).get(site,0)<=limits.get(site,request['maxContainersPerSite']) for site,ids in site_ids.items())
    intervals=all(not s['dailyLitres'] or (actual_days[i] and cyclic_gap(actual_days[i],horizon)<=request['maxIntervalDays'] and all(((actual_days[i][(j+1)%len(actual_days[i])]-d)%horizon or horizon)>=request['minIntervalDays'] for j,d in enumerate(actual_days[i]))) for i,s in enumerate(streams))
    feasible=bool(streams) and bounds and intervals and not violations and spill<1e-6 and not pending and stable
    summary=dict(name=name,intervalDays=None,installedContainers=installed,truckDays=truck_days,
        peakTrucks=max((d['truckDays'] for d in daily),default=0),distanceKm=km,workingHours=sum(d['hours'] for d in daily),
        emptyingHours=sum(e['containers'] for e in events)*cfg.service_min_per_bin/60,containersEmptied=sum(e['containers'] for e in events),
        siteVisits=sum(d['siteVisits'] for d in daily),demandLitres=float(demand.sum()*horizon),collectedLitres=collected,
        remainingLitres=float(stored.sum()),initialLitres=float(initial.sum()),spillLitres=spill,fullStreamDays=full_days,
        pendingSites=len({streams[i]['locationId'] for i in pending}),pendingSiteDays=sum(d['pendingSites'] for d in daily),
        targetViolationStreamDays=violations,cyclicStockStable=stable,feasible=feasible,
        averageFillAtCollection=float(np.mean(filled)) if filled else None,daily=daily,
        costs=dict(configured=total is not None,partial=fixed==0 or rental==0,drivingIncluded=fixed>0 and extra==0,
            truckEuro=truck_cost if fixed>0 else None,roadEuro=road_cost if extra>0 else None,containerEuro=rental_cost if rental>0 else None,
            totalEuro=total,monthlyEquivalentEuro=money(total*MONTH_DAYS/horizon) if total is not None else None))
    recommendations=[dict(locationId=s['locationId'],material=s['material'],baselineCount=s['baselineCount'],recommendedCount=counts[i],
        dailyLitres=s['dailyLitres'],averageIntervalDays=horizon/int(visit_counts[i]) if visit_counts[i] else None,
        maximumIntervalDays=cyclic_gap(actual_days[i],horizon) if actual_days[i] else None,visits=int(visit_counts[i]),maximumFillPercent=float(max_fill[i])) for i,s in enumerate(streams)]
    return summary,recommendations,events,route_plans


def optimize(df,payload,cfg,shape_routes=None):
    request={**payload['capacityScenario'],'fixedTruckCostEuro':payload['settings'].get('fixedTruckCostEuro',0)}
    streams,excluded=demand_streams(df,request,cfg.container_volume_m3*1000)
    locations={r['locationId']:r for r in payload.get('locations',[])}
    known=set(zip(df.site,df.material));supported={(s['locationId'],s['material']) for s in streams}
    override={(r['locationId'],r['material']):r for r in request.get('overrides',[])}
    reserved={}
    for site,material in known-supported:
        reserved[site]=reserved.get(site,0)+override.get((site,material),{}).get('baselineCount',request['baselineContainers'][material])
    request['_reserved']=reserved
    request['_positiveTypes']={site:sum(s['dailyLitres']>0 for s in streams if s['locationId']==site) for site in set(s['locationId'] for s in streams)}
    if set(r['locationId'] for r in request.get('siteLimits',[]))-set(df.site):raise ValueError('A site limit refers to a location without history through the cutoff.')
    horizon=request['optimizationWeeks']*7;start=pd.Timestamp(payload['asOf'])+pd.Timedelta(days=1)
    workdays=working_dates(start,horizon,cfg.working_weekdays)
    baseline=evaluate(streams,[s['baselineCount'] for s in streams],baseline_calendar(streams,workdays,horizon,request['baselineIntervalDays']),locations,cfg,request,start,'baseline',payload['settings'])
    candidates=[];search=[];seen=set()
    if streams and not(set(s['locationId'] for s in streams)-set(locations)):
        for conservative in (False,True):
            seed=seed_choice(streams,workdays,horizon,cfg,request,storage=not conservative)
            choice,status=master(streams,reserved,workdays,horizon,cfg,request,conservative,hint=seed)
            if choice is None:choice=seed
            status['seedFallback']=status['status'] not in ('OPTIMAL','FEASIBLE')
            search.append(dict(strategy='minimum-inventory' if conservative else 'service-cost',**status))
            if choice is None:continue
            counts,calendar=refine_choice(streams,choice,horizon,cfg,request);fingerprint=(tuple(counts),tuple(tuple(x) for x in calendar))
            limits={r['locationId']:r['maxContainers'] for r in request.get('siteLimits',[])}
            if any(sum(counts[i] for i,s in enumerate(streams) if s['locationId']==site)+reserved.get(site,0)>limits.get(site,request['maxContainersPerSite']) for site in set(s['locationId'] for s in streams)):
                status['rejected']='physical space limit';continue
            if fingerprint in seen:continue
            seen.add(fingerprint)
            evaluated=evaluate(streams,counts,calendar,locations,cfg,request,start,'alternative',payload['settings'])
            candidates.append(evaluated)
    valid=[c for c in candidates if c[0]['feasible']]
    # A feasible baseline is a genuine incumbent: never recommend a worse plan
    # merely because a proxy-guided calendar search produced weaker candidates.
    if baseline[0]['feasible']:
        valid.append(({**deepcopy(baseline[0]),'name':'alternative'},baseline[1],baseline[2],baseline[3]))
    def score(c):
        s=c[0];return (s['costs']['totalEuro'] if s['costs']['totalEuro'] is not None else math.inf,s['installedContainers'],s['workingHours'],s['distanceKm'])
    best=None;geometry_error=None
    for candidate in sorted(valid,key=score):
        if shape_routes:
            try:
                for day,(plan,records) in zip(candidate[0]['daily'],candidate[3]):
                    if plan is not None:
                        shape_routes(plan,cfg,pd.DataFrame(records));day.update(routes=plan.routes,distanceKm=plan.kpis['km'],hours=plan.kpis['hours'])
            except Exception as error:
                from fillinq.roads import RoadRoutingError
                if not isinstance(error,RoadRoutingError):raise
                geometry_error=str(error);continue
        best=candidate;break
    if best:
        # Geometry verification can change road totals. Reprice those exact costs.
        s=best[0];s['distanceKm']=sum(d['distanceKm'] for d in s['daily']);s['workingHours']=sum(d['hours'] for d in s['daily'])
        if payload['settings'].get('costPerKmEuro',0)>0:
            s['costs']['roadEuro']=round(s['distanceKm']*payload['settings']['costPerKmEuro'],2)
            s['costs']['totalEuro']=round((s['costs']['truckEuro'] or 0)+s['costs']['roadEuro']+(s['costs']['containerEuro'] or 0),2)
            s['costs']['monthlyEquivalentEuro']=round(s['costs']['totalEuro']*MONTH_DAYS/horizon,2)
    alternative=best[0] if best else None
    for scenario in [baseline[0]]+([alternative] if alternative else []):
        for day in scenario['daily']:
            day['routes']=[dict(truck=r['truck'],hours=r['hours'],distanceKm=r['km'],bins=r['bins'],territory=r.get('territory'),
                roadPaths=r.get('roadPaths',[]),drivingHours=r.get('drivingHours'),
                trips=[dict(stops=t['stops'],weightKg=t['weight_t']*1000,volumeL=t['volume_m3']*1000,volumeByMaterialL=t.get('volume_by_material_l')) for t in r['trips']]) for r in day['routes']]
    summary_streams=[{**s,'alternativeCount':r['recommendedCount']} for s,r in zip(streams,best[1])] if best else streams
    return dict(routing=cfg.road_network.describe(),asOf=payload['asOf'],start=start.date().isoformat(),end=(start+pd.Timedelta(days=horizon-1)).date().isoformat(),days=horizon,
        supportedStreams=len(streams),excludedStreams=excluded,missingCoordinateSites=sorted(set(s['locationId'] for s in streams)-set(locations)),
        scenarios=[baseline[0]]+([alternative] if alternative else []),fillingTimes=filling_summary(summary_streams,cfg.container_volume_m3*1000),
        comparableService=bool(best and not excluded and baseline[0]['feasible']),settings=payload['settings'],request=payload['capacityScenario'],
        optimization=dict(status='best-feasible-found' if best else 'no-feasible-plan-found',globalOptimalityProven=False,
            targetFillPercent=request['targetFillPercent'],candidatesEvaluated=len(candidates),search=search,geometryError=geometry_error,
            recommendations=best[1] if best else [],collections=best[2] if best else [],
            candidateResults=[dict(strategy=i,feasible=c[0]['feasible'],truckDays=c[0]['truckDays'],cost=c[0]['costs']['totalEuro'],targetViolations=c[0]['targetViolationStreamDays']) for i,c in enumerate(candidates)]),
        assumptions=[
            'Bounded joint search over physical containers and a repeating calendar. CP-SAT selects counts/calendar using service-time proxies; actual street routes determine feasibility and final expense. Global route/count optimality is not proven.',
            'The operating cycle repeats every selected number of weeks. Cyclic starting stock is determined by the calendar; this is steady-state planning, not a claim about current occupancy or an executed collection.',
            'Both plans use identical median ordinary-cycle incoming litres/day. Full, overfull and unknown cycles cannot supply exact rates. Unsupported streams remain excluded and reserve their assumed baseline space at each site.',
            'The maximum fill target is checked before emptying on every day, including non-working days and across the cycle boundary. A feasible plan returns to its initial stock and collects exactly the full cycle demand.',
            'Each glass type can have its own collection dates. Types due at one site on the same day share a road stop. All physical containers of a selected type empty together; their count sets service time.',
            'Site and per-type container maxima are user-configured scenario bounds, not verified physical space surveys. Target and interval bounds are configurable. An infeasible result is not a dispatch plan.',
            'Truck, compartment, payload and shift constraints use the existing car-street router. No aerial-distance fallback. Public-holiday shutdowns and truck-specific road restrictions are not inferred.',
            'The €500 truck-day package includes driver and kilometres. Unpriced container ownership/rental prevents a complete financial optimum. Costs are modelled, not measured savings.',
            'Monthly expense scales the repeating cycle to 30.4375 days. The constant-demand scenario does not establish seasonally robust or stochastic overflow safety.'
        ])
