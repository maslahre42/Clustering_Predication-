from test_worker import worker, payload
import pytest
import pandas as pd
from integrations.dataset import DatasetValidationError, source, evidence
from integrations.comparison import profiles, forecast_comparison, optimization_check


def csv_payload(lines):
    return dict(payload(),csv='Location_id,material_type,date,fill_level_perc\n'+'\n'.join(lines))


def test_kaise_upload_rejects_all_bad_rows_without_silent_repair():
    p=csv_payload(['A,pink,2026-1-01,110','B,white,2026-01-01,40','B,white,2026-01-01,40'])
    with pytest.raises(DatasetValidationError) as caught: worker.readings(p)
    assert {e['rule_id'] for e in caught.value.errors}=={'R3','R4','R5','R6'}
    assert {e['row_number'] for e in caught.value.errors}=={1,3}


def test_upload_has_one_dataset_and_inclusive_cutoff_not_sqlite_rows():
    p=csv_payload(['UPLOAD,green,2026-01-01,50','UPLOAD,green,2026-03-12,overfull','FUTURE,white,2026-03-13,40'])
    df=worker.readings(p)
    assert set(df.site)=={'UPLOAD'}
    assert df.overfull.sum()==1
    assert df.iloc[-1].censored
    assert evidence(df,p)['source']=='uploaded-csv'


def test_legacy_unknown_is_retained_but_duplicates_are_rejected():
    p=payload();p['observations'][0]['fillLevel']='unknown'
    df=worker.readings(p)
    assert df.fill.isna().sum()==1
    assert any(w['rule_id']=='R8' for w in evidence(df,p)['warnings'])
    p['observations'].append(p['observations'][0].copy())
    with pytest.raises(DatasetValidationError) as caught:worker.readings(p)
    assert caught.value.errors[0]['rule_id']=='R6'


def test_sparse_or_overfull_only_groups_never_invent_numeric_profiles():
    p=csv_payload(['A,white,2026-01-01,overfull','A,white,2026-01-11,overfull','A,white,2026-01-21,overfull'])
    group=evidence(worker.readings(p),p)['grouping']
    assert group['method']=='rule_tiers' and group['eligible']==0
    assert group['labels'][0]['group']=='insufficient_history'
    assert group['profiles'][0]['feature_medians']['mean_fill_pct'] is None


def test_snapshot_and_groups_ignore_future_rows_and_use_reset_aware_rates():
    p=csv_payload(['A,white,2026-01-01,80','A,white,2026-01-11,80','A,white,2026-01-21,80'])
    first=evidence(worker.readings(p),p)
    assert first['grouping']['profiles'][0]['feature_medians']['median_rate_pct_per_day']==8
    p['csv']+='\nFUTURE,green,2026-04-01,100'
    second=evidence(worker.readings(p),p)
    assert first==second


def test_forecast_comparison_scores_identical_real_targets_with_frozen_training():
    p=csv_payload(['A,white,2026-01-01,80','A,white,2026-01-11,80','A,white,2026-01-21,40','A,white,2026-02-01,100','A,white,2026-02-11,overfull'])
    df=worker.readings(p);start=pd.Timestamp('2026-01-20');end=pd.Timestamp('2026-02-11')
    train=df[df.date<start];model,_=worker.fit(train)
    result=forecast_comparison(df,train,model,profiles(train,start),start,end)
    assert result['commonNumericCases']==1 and result['commonCensoredCases']==2
    scores={m['name']:m for m in result['models']}
    assert scores['kaise']['mae']==40 and scores['zakaria']['mae']==40
    assert all(m['available']==3 for m in result['models'])
    assert 'lower bounds' in result['note']


def test_small_case_gurobi_check_uses_applied_capacity_and_fixed_travel():
    pytest.importorskip('gurobipy')
    cfg=worker.config({'maxVehicles':2,'truckPayloadT':1,'fixedTravelMin':10,'serviceMinPerStop':2})
    stops=pd.DataFrame([dict(site=s,lat=49.1,lon=9.2,vol_l=2000,kg=700,n_bins=1,must=True,value=.9) for s in ['A','B']])
    result=optimization_check(stops,cfg)
    assert result['scope']=='one-load-per-truck'
    if result['status']=='solver_unavailable':pytest.skip('Gurobi license unavailable')
    assert result['status']=='optimal' and result['complete']
    assert result['trucks']==2 and result['fleetLowerBound']==2
    assert all(r['hours']==pytest.approx(52/60) for r in result['routes'])
    assert all(r['distanceKm'] is None for r in result['routes'])


def test_empty_simulation_collection_metrics_do_not_invent_low_fill_collections():
    from fillinq.simulate import _kpis,_new_rec
    result=_kpis(_new_rec(),0)
    assert result['bin_collections']==0 and result['share_collections_below_40pct']==0


def test_all_combined_scenarios_share_training_and_no_future_bin_leaks():
    p=payload();p.update(start='2026-02-20',end='2026-02-20')
    first=worker.simulation(p)
    p['observations'].append(dict(locationId='FUTURE',material='green',date='2026-04-01',fillLevel='100'))
    second=worker.simulation(p)
    assert first['forecastComparison']==second['forecastComparison']
    assert first['dataset']==second['dataset']
    assert {s['name'] for s in first['scenarios']}=={'historical','dynamic','zakaria'}
    assert first['knownBins']==second['knownBins']==2


def test_historical_policy_respects_shared_working_calendar(monkeypatch):
    from fillinq import simulate
    p=payload();df=worker.readings(p)
    start=pd.Timestamp('2026-02-20');model,_=worker.fit(df[df.date<start])
    # 2026-02-20 is Friday; explicitly closed in this test.
    tw=simulate.Twin(model,df,start=start,end=start,seed=7)
    cfg=worker.config({'workFriday':False})
    monkeypatch.setattr(simulate,'plan_routes',lambda *a,**kw: pytest.fail('No truck should run on a closed day'))
    result=simulate.run_baseline(tw,worker.places(p,df.site.unique(),cfg),cfg,route=True)
    assert result['bin_collections']==0
    assert result['daily'].iloc[0].dropped_mandatory==2


def test_missing_independent_solver_is_explicit_and_preserves_sample(monkeypatch):
    import sys
    monkeypatch.setitem(sys.modules,'gurobipy',None)
    cfg=worker.config({})
    stops=pd.DataFrame([dict(site='A',lat=49.1,lon=9.2,vol_l=2000,kg=700,n_bins=1,must=True,value=.9)])
    result=optimization_check(stops,cfg)
    assert result['status']=='solver_unavailable' and not result['complete']
    assert result['unserved'][0]['Location_id']=='A'


def test_twin_handles_known_bin_with_no_fitted_material_cycles():
    from fillinq.simulate import Twin
    p=payload()
    p['observations'].append(dict(locationId='SPARSE',material='green',date='2026-02-01',fillLevel='unknown'))
    df=worker.readings(p);start=pd.Timestamp('2026-02-20')
    model,_=worker.fit(df[df.date<start])
    tw=Twin(model,df,start=start,end=start,seed=7)
    assert 'SPARSE|green' in tw.cid
    assert tw.CR.shape[0]==3
