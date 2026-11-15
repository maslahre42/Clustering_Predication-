import pytest
from test_worker import worker, payload

HEADER='Location_id,material_type,date,fill_level_perc\n'


def test_validation_summarizes_entire_file_without_models_or_street_requests(monkeypatch):
    def unavailable(*args,**kwargs):raise AssertionError('Validation must not fit or route')
    monkeypatch.setattr(worker,'fit',unavailable);monkeypatch.setattr(worker,'make_road_network',unavailable)
    p=payload();p['csv']=HEADER+'A,white,2026-01-01,80\nA,green,2026-01-02,overfull\nB,brown,2027-01-01,30'
    result=worker.dataset_validation(p)
    assert (result['rows'],result['locations'],result['bins'])==(3,2,3)
    assert result['firstDate']=='2026-01-01' and result['lastDate']=='2027-01-01'
    assert result['materials']==dict(brown=1,green=1,white=1)
    assert len(result['fingerprint'])==64 and result['source']=='uploaded-csv'
    assert worker.dataset_validation(p)==result


@pytest.mark.parametrize('csv',[HEADER,HEADER+'A,white,2026-01-01,999','site,date\nA,2026-01-01',HEADER+'A,white,2026-01-01,unknown'])
def test_rejected_imports_keep_row_level_validation(csv):
    p=payload();p['csv']=csv
    with pytest.raises(worker.DatasetValidationError) as rejected:worker.dataset_validation(p)
    assert rejected.value.errors and rejected.value.errors[0]['message']
