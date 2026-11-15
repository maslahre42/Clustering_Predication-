from copy import deepcopy
import json
import pytest
from test_worker import worker, payload
from integrations import joint_planning as joint


def p():
    data=payload();data['settings'].update(fixedTruckCostEuro=500,depotLatitude=49.14,depotLongitude=9.22,disposalLatitude=49.14,disposalLongitude=9.22)
    data['capacityScenario']=dict(days=7,baselineIntervalDays=2,alternativeIntervalDays=7,
        baselineContainers=dict(brown=1,green=1,white=1),alternativeContainers=dict(brown=1,green=1,white=1),
        containerCostPerMonthEuro=10,overrides=[],optimize=True,optimizationWeeks=1,targetFillPercent=90,
        maxContainersPerType=3,maxContainersPerSite=9,minIntervalDays=1,maxIntervalDays=7,siteLimits=[])
    return data


def test_joint_optimizer_recommends_dates_counts_routes_and_cost_without_deferred_demand():
    data=p();result=worker.capacity_scenario(data)
    assert result['optimization']['status']=='best-feasible-found'
    assert result['optimization']['globalOptimalityProven'] is False
    a,b=result['scenarios'];assert b['feasible'] and b['cyclicStockStable']
    assert b['collectedLitres']==pytest.approx(b['demandLitres'])
    assert b['spillLitres']==0 and b['targetViolationStreamDays']==0
    assert b['costs']['totalEuro']<=a['costs']['totalEuro']
    assert b['costs']['truckEuro']==b['truckDays']*500
    assert result['optimization']['collections'] and result['optimization']['recommendations']
    assert all(r['maximumFillPercent']<=90+1e-6 for r in result['optimization']['recommendations'])
    assert any(d['routes'] and d['routes'][0]['roadPaths'] for d in b['daily'])
    assert all(s['risk'] is None for d in b['daily'] for s in d['stops'])
    json.dumps(worker.clean(result),allow_nan=False)


def test_periodic_weekend_and_cycle_boundary_require_sufficient_containers():
    data=p()
    # 40% per day: one bin cannot survive a three-day Friday-to-Monday gap.
    for row in data['observations']:row['fillLevel']='80'
    import pandas as pd
    data['observations']=[dict(locationId='A',material='white',date=str(d.date()),fillLevel='80') for d in pd.date_range('2026-02-26',periods=8,freq='2D')]
    result=worker.capacity_scenario(data)
    rec=result['optimization']['recommendations'][0]
    assert rec['recommendedCount']>=2
    assert result['scenarios'][1]['feasible']
    assert all(d['truckDays']==0 for d in result['scenarios'][1]['daily'] if pd.Timestamp(d['date']).day_of_week>=5)


def test_tight_site_bound_reports_infeasibility_instead_of_returning_unsafe_schedule():
    data=p();data['capacityScenario'].update(targetFillPercent=50,maxContainersPerType=1,maxContainersPerSite=1,minIntervalDays=7)
    result=worker.capacity_scenario(data)
    assert result['optimization']['status']=='no-feasible-plan-found'
    assert len(result['scenarios'])==1 and not result['optimization']['recommendations']


def test_missing_coordinates_and_unsupported_history_cannot_become_complete_savings():
    data=p();data['locations']=[]
    result=worker.capacity_scenario(data)
    assert result['missingCoordinateSites']==['A','B']
    assert result['optimization']['status']=='no-feasible-plan-found'
    assert not result['comparableService']


def test_future_readings_do_not_change_demand_or_recommendation_problem():
    data=p();df=worker.readings(data)
    from integrations.capacity_planning import demand_streams
    before=demand_streams(df,data['capacityScenario'],3000)
    data['observations'].append(dict(locationId='FUTURE',material='white',date='2027-01-01',fillLevel='99'))
    assert demand_streams(worker.readings(data),data['capacityScenario'],3000)==before


@pytest.mark.parametrize('change',[dict(targetFillPercent=101),dict(optimizationWeeks=0),dict(maxContainersPerSite=0),dict(minIntervalDays=8,maxIntervalDays=7),dict(siteLimits=[dict(locationId='X',maxContainers=3)])])
def test_invalid_optimization_controls_fail_without_mutating_input(change):
    data=p();data['capacityScenario'].update(change);before=deepcopy(data)
    with pytest.raises(worker.DatasetValidationError):worker.capacity_scenario(data)
    assert data==before


def test_unknown_streams_reserve_site_space_and_cannot_silently_vanish():
    data=p();data['capacityScenario'].update(maxContainersPerSite=1,maxContainersPerType=1)
    data['observations'] += [dict(locationId='A',material='brown',date=date,fillLevel='unknown') for date in ('2026-01-01','2026-01-11')]
    result=worker.capacity_scenario(data)
    assert result['excludedStreams']==[dict(locationId='A',material='brown')]
    assert result['optimization']['status']=='no-feasible-plan-found'


def test_unverified_geometry_is_not_offered_as_dispatch_plan(monkeypatch):
    from fillinq.roads import RoadRoutingError
    def fail(*args):raise RoadRoutingError('Street geometry unavailable')
    monkeypatch.setattr(worker,'street_route_shapes',fail)
    result=worker.capacity_scenario(p())
    assert result['optimization']['status']=='no-feasible-plan-found'
    assert result['optimization']['geometryError']=='Street geometry unavailable'
    assert not result['optimization']['recommendations']


def test_missing_master_incumbent_uses_a_street_checked_calendar_seed(monkeypatch):
    monkeypatch.setattr(joint,'master',lambda *args,**kwargs:(None,dict(status='UNKNOWN',proxyOnly=True)))
    result=worker.capacity_scenario(p())
    assert result['optimization']['status']=='best-feasible-found'
    assert result['scenarios'][1]['feasible']
    assert result['scenarios'][1]['collectedLitres']==pytest.approx(result['scenarios'][1]['demandLitres'])


def test_unused_extra_capacity_is_removed_without_changing_demand_or_calendar():
    data=p();from integrations.capacity_planning import demand_streams
    streams,_=demand_streams(worker.readings(data),data['capacityScenario'],3000)
    choice=([3,3],[[0],[0]])
    result=joint.refine_choice(streams,choice,7,worker.config(data['settings']),data['capacityScenario'])
    assert result[0]==[1,1] and result[1]==[[0],[0]]
    assert choice[0]==[3,3]
    assert all(s['dailyLitres']*7<=2700 for s in streams)
