import pytest
from test_worker import worker, payload


def recent_payload():
    return dict(asOf='2026-09-30',settings={},locations=[],observations=[
        dict(locationId='A',material='white',date=day,fillLevel=fill)
        for day,fill in [('2026-09-01','80'),('2026-09-11','80'),('2026-09-21','80'),('2026-09-30','100')]])


@pytest.mark.parametrize('full', ['100','overfull'])
def test_september_full_visit_resets_and_october_first_estimates_only_new_growth(full,monkeypatch):
    monkeypatch.setattr(worker,'make_road_network',lambda:pytest.fail('Fill state must not request street routes'))
    p=recent_payload();p['observations'][-1]['fillLevel']=full
    day=worker.selected_day_state(p)['bins'][0]
    assert day['status']=='emptied' and day['expectedFillPercent']==day['lower']==day['upper']==0
    p['asOf']='2026-10-01'
    tomorrow=worker.selected_day_state(p)['bins'][0]
    assert tomorrow['status']=='estimated' and 0 < tomorrow['expectedFillPercent'] < 50
    assert tomorrow['lastEmptied']=='2026-09-30' and tomorrow['daysSinceEmptied']==1
    assert 0 <= tomorrow['lower'] <= tomorrow['upper'] <= 100
    assert p['observations'][-1]['fillLevel']==full  # No changes to the recorded evidence.


def test_unknown_reading_still_confirms_emptying_but_does_not_invent_a_rate():
    p=recent_payload();p['observations']=[dict(locationId='A',material='brown',date='2026-09-30',fillLevel='unknown')]
    today=worker.selected_day_state(p)
    assert today['bins'][0]['expectedFillPercent']==0 and today['bins'][0]['status']=='emptied'
    p['asOf']='2026-10-01'
    tomorrow=worker.selected_day_state(p)['bins'][0]
    assert tomorrow['status']=='unknown' and tomorrow['expectedFillPercent'] is None
    assert tomorrow['lower'] is None and tomorrow['upper'] is None
    assert worker.readings(p).fill.isna().all()


def test_sparse_bins_borrow_known_material_rates_and_unseen_material_stays_unknown():
    p=recent_payload();p['asOf']='2026-10-01'
    p['observations'] += [dict(locationId=site,material=material,date='2026-09-30',fillLevel='100') for site,material in [('WHITE','white'),('BROWN','brown')]]
    result=worker.selected_day_state(p)
    states={row['locationId']:row for row in result['bins']}
    assert states['WHITE']['status']=='estimated' and states['WHITE']['expectedFillPercent']<50
    assert states['BROWN']['status']=='unknown' and states['BROWN']['expectedFillPercent'] is None


def test_future_visits_do_not_reset_or_train_selected_day_and_empty_source_is_explicit():
    p=recent_payload();p['asOf']='2026-10-01'
    first=worker.selected_day_state(p)
    p['observations'] += [dict(locationId=site,material='white',date='2026-10-02',fillLevel='overfull') for site in ['A','FUTURE']]
    assert worker.selected_day_state(p)==first
    p['observations']=[]
    empty=worker.selected_day_state(p)
    assert empty['bins']==[] and empty['lastObservationDate'] is None
    assert empty['semantics']=='after-recorded-emptyings'


def test_advancing_date_does_not_empty_bins_without_a_recorded_visit():
    p=recent_payload();p['observations'].append(dict(locationId='OLD',material='white',date='2026-09-01',fillLevel='100'))
    p['asOf']='2026-10-01'
    states={row['locationId']:row for row in worker.selected_day_state(p)['bins']}
    assert states['OLD']['daysSinceEmptied']==30 and states['OLD']['status']=='estimated'
    assert states['OLD']['expectedFillPercent'] > states['A']['expectedFillPercent']
    assert worker.readings(p).loc[lambda frame:frame.site=='OLD','fill'].iloc[0]==100
