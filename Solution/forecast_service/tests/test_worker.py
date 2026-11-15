import importlib.util
from pathlib import Path
from types import SimpleNamespace
import json
import pandas as pd
import pytest

spec = importlib.util.spec_from_file_location('worker', Path(__file__).parents[1] / 'worker.py')
worker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(worker)


def payload():
    rows = [dict(locationId=site, material='white', date=str(day.date()), fillLevel=str(fill))
            for site,fill in [('A',80),('B',50)] for day in pd.date_range('2026-01-01',periods=8,freq='10D')]
    return dict(asOf='2026-03-12',settings={'solverTimeLimitSeconds':1},observations=rows,
                locations=[dict(locationId=s,latitude=49.14,longitude=9.22,isSynthetic=True) for s in ('A','B')])


def test_proposal_uses_actual_omar_engine_and_ignores_future_rows():
    p=payload()
    first=worker.proposal(p)
    p['observations'].append(dict(locationId='FUTURE',material='white',date='2026-04-01',fillLevel='100'))
    second=worker.proposal(p)
    assert first['model']['engine']=='omar-python'
    assert first['model']==second['model']
    assert len(first['model']['seasonality'])==12
    assert first['bins']==second['bins']
    assert first['planDate']>'2026-03-12'
    assert len(first['stops'])==first['plan']['totals']['stops']+len(first['plan']['unserved'])
    json.dumps(worker.clean(first),allow_nan=False)


def test_curve_has_ordered_model_band_and_inclusive_cutoff():
    p=payload(); p.update(locationId='A',material='white',horizonDays=15)
    curve=worker.forecast(p)
    assert len(curve['points'])==16
    assert all(0<=r['lower']<=r['upper']<=100 for r in curve['points'])
    assert all(r['date']<=p['asOf'] for r in curve['history'])


def test_unknown_visit_resets_cycle_but_provides_no_rate():
    p=payload()
    next(r for r in p['observations'] if r['locationId']=='A' and r['date']=='2026-03-12')['fillLevel']='unknown'
    result=worker.proposal(p)
    assert next(r for r in result['bins'] if r['locationId']=='A')['lastEmptied']=='2026-03-12'


def test_empty_history_has_explicit_empty_proposal():
    p=payload();p['observations']=[]
    result=worker.proposal(p)
    assert result['bins']==[] and result['plan']['totals']['trucks']==0


def test_simulation_uses_pre_start_training_and_reports_both_policies():
    p=payload(); p.update(start='2026-02-20',end='2026-02-20',seed=7)
    result=worker.simulation(p)
    assert result['trainingThrough']=='2026-02-19'
    assert [s['name'] for s in result['scenarios']]==['historical','dynamic','zakaria']
    assert len(result['frontier'])==5
    assert all('missedMandatory' in s and 'daily' in s for s in result['scenarios'])


def test_invalid_simulation_range_is_rejected():
    p=payload();p.update(start='2026-01-01',end='2026-03-12')
    with pytest.raises(ValueError,match='1–31'):
        worker.simulation(p)


def test_historical_simulation_does_not_reset_unserved_bins(monkeypatch):
    from fillinq import simulate
    p=payload(); df=worker.readings(p)
    model,_=worker.fit(df[df.date<pd.Timestamp('2026-02-20')])
    twin=simulate.Twin(model,df,start='2026-02-20',end='2026-02-20',seed=7)
    monkeypatch.setattr(simulate,'plan_routes',lambda *a,**kw: SimpleNamespace(routes=[],dropped_mandatory=['A','B'],
        kpis={'km':0,'hours':0,'trucks':0}))
    result=simulate.run_baseline(twin,worker.places(p,df.site.unique(),worker.config({})),worker.config({}),route=True)
    assert result['bin_collections']==0 and result['site_visits']==0
    assert result['daily'].iloc[0]['dropped_mandatory']==2


def test_oversized_sites_are_not_clipped():
    from fillinq.routing import plan_routes
    from fillinq.config import OpsConfig
    stops=pd.DataFrame([dict(site='BIG',lat=49.1,lon=9.2,vol_l=50000,kg=15000,n_bins=3,must=True,value=1)])
    result=plan_routes(stops,OpsConfig(),time_limit_s=1)
    assert result.dropped_mandatory==['BIG'] and result.kpis['weight_t']==0


def test_omar_router_prefers_higher_risk_when_one_truck_cannot_serve_both():
    from fillinq.routing import plan_routes
    from fillinq.config import OpsConfig
    stops=pd.DataFrame([
        dict(site='HIGH',lat=49.1,lon=9.2,vol_l=3000,kg=1050,n_bins=3,must=True,value=.99),
        dict(site='LOW',lat=49.1,lon=9.2,vol_l=1000,kg=350,n_bins=1,must=True,value=.71)])
    cfg=OpsConfig(max_vehicles=1,shift_hours=1)
    result=plan_routes(stops,cfg,time_limit_s=1)
    assert result.dropped_mandatory==['LOW']


def test_no_solver_solution_retains_mandatory_status(monkeypatch):
    from fillinq import routing
    from fillinq.config import OpsConfig
    stops=pd.DataFrame([dict(site='A',lat=49.1,lon=9.2,vol_l=1000,kg=350,n_bins=1,must=True,value=.8)])
    monkeypatch.setattr(routing.pywrapcp.RoutingModel,'SolveWithParameters',lambda *args:None)
    result=routing._solve(stops,OpsConfig(),1,1)
    assert result.dropped_mandatory==['A'] and result.dropped_optional==[]
    assert result.reasons['A']=='solver_no_solution'


def test_empty_service_calendar_rejected():
    with pytest.raises(ValueError,match='at least one'):
        worker.config({f'work{day}':False for day in ['Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday']})
