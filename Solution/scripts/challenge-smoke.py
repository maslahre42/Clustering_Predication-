"""Exercise the challenge workflow against a running API and the bundled dataset.

API_BASE=http://localhost:5080 python3 scripts/challenge-smoke.py --report /tmp/challenge-evidence.json
No source data is changed. Route search is time limited; fleet counts can vary.
"""
import argparse
import json
import os
from datetime import datetime, timezone
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--report', help='Optional path for the complete JSON evidence')
args = parser.parse_args()
base = os.environ.get('API_BASE', 'http://localhost:5080').rstrip('/')


def request(path, params=None, body=None):
    data = None if body is None else json.dumps(body).encode()
    req = Request(base + path + ('?' + urlencode(params) if params else ''), data=data,
                  headers={'Content-Type': 'application/json'} if data else {})
    with urlopen(req, timeout=240) as response:
        return json.load(response)


def check_plan(proposal):
    assert proposal['model']['engine'] == 'omar-python'
    settings = proposal['settings']
    routes = proposal['plan']['routes']
    assert len(routes) == proposal['plan']['totals']['trucks'] <= settings['maxVehicles']
    assert all(bin['lastEmptied'] <= proposal['asOf'] for bin in proposal['bins'])
    served = []
    for route in routes:
        assert route['hours'] <= settings['shiftHours'] + 1e-6
        for trip in route['trips']:
            assert trip['weightKg'] <= settings['truckPayloadT'] * 1000 + 1e-6
            if settings['truckVolumeM3']:
                assert trip['volumeL'] <= settings['truckVolumeM3'] * 1000 + 1e-6
            served.extend(trip['stops'])
    assert len(served) == len(set(served)) == proposal['plan']['totals']['stops']
    unserved = {stop['locationId'] for stop in proposal['plan']['unserved']}
    assert not set(served) & unserved
    assert {stop['locationId'] for stop in proposal['stops']} == set(served) | unserved


assert request('/api/health')['status'] == 'healthy'
partial = request('/api/analytics', {'asOf': '2026-09-08'})
month = next(row for row in partial['months'] if row['month'] == '2026-09' and row['material'] == 'brown')
assert month['collections'] == 9 and month['overfullCount'] == 0
assert round(month['meanNumericFill'], 1) == 28.9
full = request('/api/analytics', {'asOf': '2026-09-30'})
month = next(row for row in full['months'] if row['month'] == '2026-09' and row['material'] == 'brown')
assert month['collections'] == 221 and month['overfullCount'] == 9
assert round(month['meanNumericFill'], 1) == 34.2
assert full['totalCollections'] == 11701 and full['knownBins'] == 1338
assert full['patterns']['firstDate'] == '2025-10-17' and full['patterns']['lastDate'] == '2026-09-30'

options = {'asOf': '2026-08-14', 'solverTimeLimitSeconds': 1}
proposal = request('/api/proposal', options)
check_plan(proposal)
bin = next(bin for bin in proposal['bins'] if bin['expectedFillPercent'] is not None)
forecast = request('/api/forecast', {**options, 'locationId': bin['locationId'], 'material': bin['material'], 'horizonDays': 14})
assert forecast['points'] and all(0 <= point['risk'] <= 1 for point in forecast['points'])
assert all(point['lower'] <= point['upper'] for point in forecast['points'])

simulation = request('/api/simulation', {**options, 'start': '2026-08-10', 'end': '2026-08-12', 'seed': 7})
assert simulation['trainingThrough'] < simulation['start']
assert {scenario['name'] for scenario in simulation['scenarios']} == {'historical', 'dynamic', 'zakaria'}
assert len(simulation['forecastComparison']['models']) == 3
assert all(scenario['missedMandatory'] >= 0 for scenario in simulation['scenarios'])
assert simulation['optimizationCheck']['status'] in {'optimal', 'feasible', 'infeasible', 'unavailable', 'error', 'empty'}

csv = 'Location_id,material_type,date,fill_level_perc\n' + '\n'.join(
    f'uploaded-site,white,2026-07-{day:02d},{fill}' for day, fill in [(1, 30), (11, 50), (21, 70), (31, 60)])
uploaded = request('/api/proposal', options, {'csv': csv})
check_plan(uploaded)
assert {bin['locationId'] for bin in uploaded['bins']} == {'uploaded-site'}
assert uploaded['dataset']['source'] == 'uploaded-csv'
try:
    request('/api/proposal', options, {'csv': csv + '\nuploaded-site,white,not-a-date,120'})
except HTTPError as error:
    assert error.code == 400
    assert json.load(error)['validation']['errors']
else:
    raise AssertionError('Invalid upload was accepted')

# Increasingly restrictive physical capacity must be explicit missed service, never truncated demand.
restricted = request('/api/proposal', {**options, 'truckPayloadT': 0.001, 'maxVehicles': 1})
check_plan(restricted)
assert not restricted['plan']['routes']
assert any(stop['mandatory'] and stop['reason'] == 'exceeds_truck_capacity' for stop in restricted['plan']['unserved'])

evidence = {'verifiedAt': datetime.now(timezone.utc).isoformat(), 'apiBase': base,
            'partialMonth': partial, 'fullHistory': full, 'proposal': proposal,
            'forecast': forecast, 'simulation': simulation, 'uploadedProposal': uploaded,
            'restrictedProposal': restricted}
if args.report:
    with open(args.report, 'w') as report:
        json.dump(evidence, report, indent=2, allow_nan=False)
print(json.dumps({'status': 'passed', 'collections': full['totalCollections'], 'bins': full['knownBins'],
                  'proposal': proposal['plan']['totals'], 'forecastComparison': simulation['forecastComparison'],
                  'optimizationStatus': simulation['optimizationCheck']['status'], 'report': args.report}, indent=2))
