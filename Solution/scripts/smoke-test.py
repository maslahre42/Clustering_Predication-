"""Run against the locally started API: python3 scripts/smoke-test.py."""
import json
import urllib.request
import urllib.error
import os

base = os.environ.get('API_BASE', 'http://localhost:5080')
def get(path):
    with urllib.request.urlopen(base + path, timeout=10) as response:
        return json.load(response)
assert get('/api/health')['status'] == 'healthy'
locations = get('/api/locations')
assert locations
cutoff = '2026-03-01'
snapshot = get('/api/planning?asOf=' + cutoff)
analytics = get('/api/analytics?asOf=' + cutoff)
assert analytics['asOf'] == cutoff
assert analytics['totalCollections'] == snapshot['observationCount']
assert sum(m['collections'] for m in analytics['materials']) == analytics['totalCollections']
assert sum(m['overfullCount'] for m in analytics['materials']) == analytics['overfullCount']
assert snapshot['asOf'] == cutoff
assert all(b['lastCollection'] <= cutoff for b in snapshot['bins'])
assert snapshot['observationCount'] > 0 and snapshot['bins']
assert len({(b['locationId'], b['material']) for b in snapshot['bins']}) == len(snapshot['bins'])
assert all(0 <= b['lastFillPercent'] <= 100 for b in snapshot['bins'] if b['lastFillPercent'] is not None)
history = get('/api/history?pageSize=2')
assert len(history['items']) <= 2 and history['total'] > 0
row = history['items'][0]
filtered = get('/api/history?locationId=' + row['locationId'] + '&material=' + row['material'] + '&from=' + row['date'] + '&to=' + row['date'])
assert filtered['items']
assert all(x['locationId'] == row['locationId'] and x['material'] == row['material'] and x['date'] == row['date'] for x in filtered['items'])
assert any(x['locationId'] == row['locationId'] for x in locations)
past = get('/api/history?asOf=' + cutoff + '&to=2099-12-31')
assert all(x['date'] <= cutoff for x in past['items'])
assert past['total'] == snapshot['observationCount']
early = get('/api/planning?asOf=1900-01-01')
assert early['observationCount'] == 0 and early['bins'] == []
for query in ['asOf=bad-date', 'page=0', 'pageSize=201', 'material=plastic', 'from=not-a-date', 'from=2026-02-01&to=2026-01-01']:
    try:
        get('/api/history?' + query)
    except urllib.error.HTTPError as e:
        assert e.code == 400
    else:
        raise AssertionError('Expected HTTP 400 for ' + query)
print('API health, pagination, identity, inclusive date filtering, and validation passed.')
