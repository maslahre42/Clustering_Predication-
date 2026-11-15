"""Exercise the stdin worker after relocation with no sibling contributor projects."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import pytest
from test_worker import payload


@pytest.mark.parametrize('action', ['forecast', 'proposal', 'state'])
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
    request['action'] = action
    if action == 'forecast':
        request.update(locationId='A',material='white',horizonDays=7)
    elif action == 'proposal':
        request['observations'] = []  # Empty proposal needs no street-service requests.
    env = {key:value for key,value in os.environ.items() if key not in ('PYTHONPATH','PYTHONHOME')}
    env['PYTHONPATH'] = str(unrelated)
    result = subprocess.run([sys.executable,str(relocated/'worker.py')],input=json.dumps(request),text=True,
                            capture_output=True,cwd=unrelated,env=env,timeout=30)
    assert result.returncode == 0, result.stderr + result.stdout
    response = json.loads(result.stdout)
    if action == 'forecast':
        assert response['locationId']=='A' and len(response['points'])==8
        assert all(row['date'] <= request['asOf'] for row in response['history'])
    elif action == 'state':
        assert len(response['bins'])==2 and all(bin['status']=='emptied' and bin['expectedFillPercent']==0 for bin in response['bins'])
    else:
        assert response['bins']==[] and response['plan']['totals']['trucks']==0
