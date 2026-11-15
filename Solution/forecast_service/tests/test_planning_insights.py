from types import SimpleNamespace
import numpy as np
import pandas as pd
import pytest
from test_worker import worker, payload
from integrations.planning_insights import operating_cost, fill_timing
from fillinq.routing import plan_routes, site_demand


def test_cost_counts_trucks_not_loads_and_rounds_cents():
    result = operating_cost(12.125,2,{'costPerKmEuro':1.2,'fixedTruckCostEuro':150})
    assert result['totalEuro'] == 314.55
    assert result['variableEuro'] == 14.55 and result['fixedEuro'] == 300
    assert not result['partial']
    split=operating_cost(.5,1,{'costPerKmEuro':.01,'fixedTruckCostEuro':.005})
    assert split['totalEuro'] == .02 == split['variableEuro']+split['fixedEuro']
    assert operating_cost(10,1,{})['totalEuro'] is None
    assert operating_cost(10,1,{'costPerKmEuro':2})['partial']
    assert operating_cost(None,1,{'costPerKmEuro':2})['totalEuro'] is None
    assert operating_cost(0,0,{'fixedTruckCostEuro':150})['totalEuro'] == 0
    for distance,trucks,settings in [(float('nan'),1,{}),(1,-1,{}),(1,1,{'costPerKmEuro':-1})]:
        with pytest.raises(ValueError): operating_cost(distance,trucks,settings)


def test_material_limits_are_explicit_and_request_local():
    assert worker.config({}).compartment_litres == {}
    with pytest.raises(ValueError): worker.config({'brownCompartmentM3':2})
    with pytest.raises(ValueError): worker.config({'brownCompartmentM3':2,'greenCompartmentM3':2,'whiteCompartmentM3':2,'truckVolumeM3':5})
    cfg=worker.config({'brownCompartmentM3':2,'greenCompartmentM3':3,'whiteCompartmentM3':4})
    assert cfg.truck_volume_m3 == 9 and cfg.compartment_litres['green']==3000
    assert worker.config({}).compartment_litres == {}


def stops():
    return pd.DataFrame([dict(site=s,lat=49.165,lon=9.235,vol_l=1500,kg=525,n_bins=1,must=True,value=1,brown_l=1500,green_l=0,white_l=0) for s in ['A','B']])


def test_full_colour_requires_unloading_and_resets_all_compartments():
    cfg=worker.config({'maxVehicles':1,'brownCompartmentM3':2,'greenCompartmentM3':4,'whiteCompartmentM3':4})
    worker.enable_street_routing(cfg)
    plan=plan_routes(stops(),cfg,time_limit_s=1)
    assert plan.dropped_mandatory == []
    assert plan.kpis['trucks']==1 and plan.kpis['trips']==2
    assert all(t['volume_by_material_l']['brown'] <= 2000 for r in plan.routes for t in r['trips'])
    assert all(r['hours'] <= cfg.shift_hours for r in plan.routes)
    cfg.compartment_litres = dict(brown=2000,green=2000,white=2000)
    frame=stops().assign(vol_l=4500,kg=1575,green_l=1500,white_l=1500,n_bins=3)
    frame=pd.concat([frame,frame.iloc[:1].assign(site='C')],ignore_index=True)
    plan=plan_routes(frame,cfg,time_limit_s=1)
    assert not plan.dropped_mandatory and plan.kpis['trips']==3
    assert all(t['volume_by_material_l'][m] <= 2000 for r in plan.routes for t in r['trips'] for m in cfg.compartment_litres)


def test_oversized_missing_or_inconsistent_material_loads_are_not_silently_served():
    cfg=worker.config({'brownCompartmentM3':1,'greenCompartmentM3':4,'whiteCompartmentM3':4})
    worker.enable_street_routing(cfg)
    result=plan_routes(stops(),cfg,time_limit_s=1)
    assert result.dropped_mandatory == ['A','B']
    assert set(result.reasons.values()) == {'exceeds_compartment_capacity'}
    for frame in [stops().drop(columns='brown_l'),stops().assign(brown_l=500),stops().assign(brown_l=np.nan)]:
        result=plan_routes(frame,cfg,time_limit_s=1)
        assert set(result.reasons.values()) == {'material_demand_unknown'}
        assert result.kpis['stops']==0


def test_material_demand_is_aggregated_by_colour_at_site():
    cfg=worker.config({})
    frame=pd.DataFrame(dict(site=['A','A','B'],material=['brown','green','white'],fill=[50,25,100]))
    result=site_demand(frame,cfg)
    assert result.loc['A','brown_l']==1500 and result.loc['A','green_l']==750
    assert result.loc['B','white_l']==3000
    assert np.allclose(result.vol_l,result[['brown_l','green_l','white_l']].sum(axis=1))


def test_time_to_full_is_cutoff_safe_and_unknown_visit_resets():
    p=payload(); first=worker.proposal(p)
    p['observations'].append(dict(locationId='A',material='white',date='2027-01-01',fillLevel='100'))
    assert worker.proposal(p)['fillTiming']==first['fillTiming']
    row=first['fillTiming'][0]
    assert row['earlyDaysUntilFull'] <= row['medianDaysUntilFull'] <= row['lateDaysUntilFull']
    p['observations'].append(dict(locationId='SPARSE',material='brown',date=p['asOf'],fillLevel='unknown'))
    latest=worker.proposal(p)
    sparse=next(row for row in latest['fillTiming'] if row['locationId']=='SPARSE')
    assert sparse['reason']=='no_completed_cycles' and sparse['medianDaysUntilFull'] is None
    next(r for r in p['observations'] if r['locationId']=='A' and r['date']==p['asOf'])['fillLevel']='unknown'
    assert next(row for row in worker.proposal(p)['fillTiming'] if row['locationId']=='A')['lastEmptied']==p['asOf']


def test_past_full_estimates_remain_negative_and_empty_model_is_explicit():
    df=pd.DataFrame(dict(container=['A|brown'],site=['A'],material=['brown'],date=pd.to_datetime(['2026-01-01'])))
    iv=pd.DataFrame(dict(container=['A|brown'],censored=[True]))
    model=SimpleNamespace(days_to_full=lambda containers, dates, q:np.array([q*10]))
    row=fill_timing(df,model,iv,'2026-01-20')[0]
    assert row['medianDaysUntilFull']==-14 and row['predictedFullDate']=='2026-01-06'
    assert row['censoredCycles']==1
    assert fill_timing(df,None,pd.DataFrame(),'2026-01-20')[0]['reason']=='no_completed_cycles'
    for invalid_model in [None,SimpleNamespace(days_to_full=lambda *args:np.array([float('nan')])),SimpleNamespace(days_to_full=lambda *args:np.array([4000]))]:
        unavailable=fill_timing(df,invalid_model,iv,'2026-01-20')[0]
        assert unavailable['reason']=='outside_model_range' and unavailable['predictedFullDate'] is None


def test_compartments_and_costs_apply_to_all_simulated_policies():
    p=payload();p.update(start='2026-02-20',end='2026-02-20',seed=7)
    p['settings'].update(brownCompartmentM3=1,greenCompartmentM3=1,whiteCompartmentM3=.1,costPerKmEuro=1.2,fixedTruckCostEuro=100)
    result=worker.simulation(p)
    for scenario in result['scenarios']:
        assert scenario['bin_collections']==0
        assert scenario['costs']['totalEuro']==0
        assert scenario['costs']['trucks']==scenario['truckDays']


def test_gurobi_sample_enforces_the_same_colour_capacities():
    from integrations.comparison import optimization_check
    cfg=worker.config({'maxVehicles':2,'brownCompartmentM3':2,'greenCompartmentM3':4,'whiteCompartmentM3':4})
    worker.enable_street_routing(cfg)
    check=optimization_check(stops(),cfg,limit=2)
    if check['status']=='solver_unavailable': pytest.skip(check['message'])
    assert check['complete'] and check['trucks']==2
    cfg.compartment_litres['brown']=1000
    check=optimization_check(stops(),cfg,limit=2)
    assert check['status']=='infeasible' and not check['complete']


def test_public_explanations_describe_methods_without_contributor_credits():
    import re,json
    p=payload();proposal=worker.proposal(p)
    p.update(start='2026-02-20',end='2026-02-20',seed=7)
    simulation=worker.simulation(p)
    visible=[*proposal['assumptions'],proposal['dataset']['grouping']['note'],*simulation['assumptions'],
        *[s['label'] for s in simulation['scenarios']],*[m['label'] for m in simulation['forecastComparison']['models']],
        simulation['forecastComparison']['note'],simulation['optimizationCheck'].get('note','')]
    assert not re.search(r'\b(omar|kaise|zakaria|zakarea)\b',json.dumps(visible),re.I)
