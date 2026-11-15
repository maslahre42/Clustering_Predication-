"""Exercise the stdin worker after relocation with no sibling contributor projects."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import pytest
from test_worker import payload


@pytest.mark.parametrize('action', ['forecast', 'proposal', 'state', 'capacity', 'capacity-optimized', 'dataset'])
def test_relocated_worker_uses_only_its_bundled_application_code(tmp_path, action):
    service = Path(__file__).resolve().parents[1]
    relocated = tmp_path / 'independent project' / 'forecast_service'
    shutil.copytree(service, relocated, ignore=shutil.ignore_patterns('tests', '__pycache__', '*.pyc'))
    unrelated = tmp_path / 'unrelated working directory'
    unrelated.mkdir()
    # An ambient package must not override the bundled engine.
    ambient = unrelated / 'fillinq'
    ambient.mkdir()
    (ambient / '__init__.py').write_text("raise RuntimeError('Unexpected external engine import')\n")
    request = payload()
    request['action'] = 'capacity' if action == 'capacity-optimized' else action
    if action == 'dataset':
        request['csv'] = 'Location_id,material_type,date,fill_level_perc\nUPLOAD,white,2026-01-01,80'
    elif action == 'forecast':
        request.update(locationId='A',material='white',horizonDays=7)
    elif action in ('capacity','capacity-optimized'):
        request['observations'] = []
        request['capacityScenario'] = dict(days=7, baselineIntervalDays=7, alternativeIntervalDays=7,
            baselineContainers=dict(brown=1,green=1,white=1),alternativeContainers=dict(brown=1,green=1,white=1),
            overrides=[],containerCostPerMonthEuro=0)
        if action == 'capacity-optimized':
            request['capacityScenario'].update(optimize=True,optimizationWeeks=1,targetFillPercent=90,maxContainersPerType=3,maxContainersPerSite=9,minIntervalDays=1,maxIntervalDays=7,siteLimits=[])
    elif action == 'proposal':
        request['observations'] = []  # Empty proposal needs no street-service requests.
    env = {key:value for key,value in os.environ.items() if key not in ('PYTHONPATH','PYTHONHOME')}
    env['PYTHONPATH'] = str(unrelated)
    result = subprocess.run([sys.executable,str(relocated/'worker.py')],input=json.dumps(request),text=True,
                            capture_output=True,cwd=unrelated,env=env,timeout=30)
    assert result.returncode == 0, result.stderr + result.stdout
    response = json.loads(result.stdout)
    if action == 'dataset':
        assert response['rows']==1 and response['locations']==1 and response['source']=='uploaded-csv'
    elif action == 'forecast':
        assert response['locationId']=='A' and len(response['points'])==8
        assert all(row['date'] <= request['asOf'] for row in response['history'])
    elif action in ('capacity','capacity-optimized'):
        assert response['supportedStreams']==0
        if action == 'capacity-optimized':assert response['optimization']['status']=='no-feasible-plan-found'
        else:assert len(response['scenarios'])==2
    elif action == 'state':
        assert len(response['bins'])==2 and all(bin['status']=='emptied' and bin['expectedFillPercent']==0 for bin in response['bins'])
    else:
        assert response['bins']==[] and response['plan']['totals']['trucks']==0
