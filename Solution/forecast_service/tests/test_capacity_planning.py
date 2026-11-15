from copy import deepcopy
from types import SimpleNamespace
import json
import pandas as pd
import pytest
from test_worker import worker, payload
from integrations import capacity_planning as capacity


def request():
    return dict(days=14,baselineIntervalDays=7,alternativeIntervalDays=7,
        baselineContainers=dict(brown=1,green=1,white=1),alternativeContainers=dict(brown=1,green=1,white=2),
        containerCostPerMonthEuro=10,overrides=[])


def p():
    result=payload();result['capacityScenario']=request()
    result['settings'].update(depotLatitude=49.14,depotLongitude=9.22,disposalLatitude=49.14,disposalLongitude=9.22,fixedTruckCostEuro=500)
    return result


@pytest.fixture
def served(monkeypatch):
    def routes(stops,cfg,**kwargs):
        bins=int(stops.n_bins.sum());hours=bins*cfg.service_min_per_bin/60
        return SimpleNamespace(kpis=dict(km=12.,hours=hours,trucks=1),routes=[dict(trips=[dict(stops=stops.site.tolist())])])
    monkeypatch.setattr(capacity,'plan_routes',routes)


def test_doubled_containers_double_filling_time_and_emptying_work_without_inventing_demand(served):
    result=worker.capacity_scenario(p());a,b=result['scenarios'];white=result['fillingTimes'][2]
    assert white['alternativeAverageDays']==pytest.approx(2*white['baselineAverageDays'])
    assert a['demandLitres']==b['demandLitres']
    assert b['installedContainers']==2*a['installedContainers']
    assert b['emptyingHours']==2*a['emptyingHours']
    assert a['truckDays']==b['truckDays']  # Less service time alone need not save a paid shift.
    assert a['costs']['truckEuro']==a['truckDays']*500
    assert a['costs']['drivingIncluded'] and not a['costs']['partial']
    assert b['costs']['containerEuro']==pytest.approx(2*a['costs']['containerEuro'],abs=.01)
    for s in (a,b):assert s['demandLitres']==pytest.approx(s['collectedLitres']+s['remainingLitres']+s['spillLitres'])
    json.dumps(worker.clean(result),allow_nan=False)


def test_frequency_changes_visits_and_cost_but_not_capacity_filling_time(served):
    data=p();data['capacityScenario']['alternativeContainers']['white']=1
    data['capacityScenario']['alternativeIntervalDays']=14
    result=worker.capacity_scenario(data);a,b=result['scenarios']
    assert b['siteVisits']<a['siteVisits']
    assert b['costs']['truckEuro']<a['costs']['truckEuro']
    assert b['spillLitres']>=a['spillLitres']
    assert result['fillingTimes'][2]['baselineAverageDays']==result['fillingTimes'][2]['alternativeAverageDays']
    assert not result['comparableService']


def test_site_override_is_scoped_and_baseline_counts_define_common_volume(served):
    data=p();data['capacityScenario']['overrides']=[dict(locationId='A',material='white',baselineCount=2,alternativeCount=3)]
    streams,_=capacity.demand_streams(worker.readings(data),data['capacityScenario'],3000)
    assert next(s for s in streams if s['locationId']=='A')['dailyLitres']==480
    assert next(s for s in streams if s['locationId']=='B')['baselineCount']==1
    result=worker.capacity_scenario(data)
    assert result['scenarios'][0]['demandLitres']==result['scenarios'][1]['demandLitres']


def test_future_unknown_full_overfull_and_zero_rates_are_handled_explicitly(served):
    data=p();base=worker.capacity_scenario(data)
    data['observations'].append(dict(locationId='FUTURE',material='white',date='2027-01-01',fillLevel='80'))
    assert worker.capacity_scenario(data)==base
    for site,fill in [('UNKNOWN','unknown'),('FULL','100'),('OVER','overfull'),('ZERO','0')]:
        for date in ['2026-01-01','2026-01-11']:
            data['observations'].append(dict(locationId=site,material='brown',date=date,fillLevel=fill))
    result=worker.capacity_scenario(data)
    assert {r['locationId'] for r in result['excludedStreams']}=={'UNKNOWN','FULL','OVER'}
    assert result['fillingTimes'][0]['zeroDemandStreams']==1
    assert result['fillingTimes'][0]['baselineAverageDays'] is None


def test_missing_coordinates_never_become_depot_or_flying_routes(served):
    data=p();data['locations']=[]
    result=worker.capacity_scenario(data)
    assert result['missingCoordinateSites']==['A','B']
    for s in result['scenarios']:
        assert s['collectedLitres']==0 and s['truckDays']==0 and s['pendingSites']==2


def test_unserved_capacity_rejections_do_not_empty_bins_or_hide_overflow(monkeypatch):
    monkeypatch.setattr(capacity,'plan_routes',lambda *args,**kwargs: SimpleNamespace(kpis=dict(km=0,hours=0,trucks=0),routes=[]))
    data=p();data['capacityScenario']['days']=31
    result=worker.capacity_scenario(data)
    for s in result['scenarios']:
        assert s['collectedLitres']==0 and s['containersEmptied']==0 and s['spillLitres']>0
        assert s['demandLitres']==pytest.approx(s['remainingLitres']+s['spillLitres'])


def test_identical_inputs_reuse_routed_outcome_exactly(served):
    data=p();data['capacityScenario']['alternativeContainers']['white']=1
    result=worker.capacity_scenario(data);a,b=result['scenarios']
    assert {**a,'name':'alternative'}==b
    assert result['comparableService']


def test_real_router_enforces_physical_emptying_count_and_returns_street_metrics():
    data=p();data['capacityScenario'].update(days=7,baselineIntervalDays=7,alternativeIntervalDays=7)
    result=worker.capacity_scenario(data);scenario=result['scenarios'][0]
    assert scenario['siteVisits']==2
    assert scenario['containersEmptied']==2
    assert scenario['emptyingHours']==pytest.approx(10/60)
    assert scenario['workingHours']>=scenario['emptyingHours']
    alternative=result['scenarios'][1]
    assert alternative['containersEmptied']==4
    assert alternative['emptyingHours']==pytest.approx(20/60)
    assert alternative['workingHours']>=alternative['emptyingHours']
    assert alternative['demandLitres']==scenario['demandLitres']


@pytest.mark.parametrize('change',[dict(days=32),dict(alternativeIntervalDays=0),dict(containerCostPerMonthEuro=-1),dict(alternativeContainers=dict(brown=1,green=1,white=0)),dict(overrides=[dict(locationId='missing',material='white',baselineCount=1,alternativeCount=2)])])
def test_invalid_input_is_rejected_without_mutating_snapshot(change,served):
    data=p();data['capacityScenario'].update(change);before=deepcopy(data)
    with pytest.raises(worker.DatasetValidationError):worker.capacity_scenario(data)
    assert data==before
