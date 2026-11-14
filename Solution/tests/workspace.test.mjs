import test from 'node:test'
import assert from 'node:assert/strict'
import { knownBins, clusterBins } from '../apps/web/app/features/inventory/domain/catalog.ts'
import { matchesHistoricalFill, historicalFillLabel, historicalFillRank } from '../apps/web/app/shared/domain/fill.ts'
import { planCsv } from '../apps/web/app/features/manifest/domain/planExport.ts'
const locations = [{ locationId: 'A', latitude: 49.14, longitude: 9.21, isSynthetic: true }]
const source = [
  { locationId: 'A', material: 'brown', lastCollection: '2026-03-01', lastFillPercent: 80, collections: 3 },
  { locationId: 'A', material: 'green', lastCollection: '2026-02-20', lastFillPercent: null, collections: 1 },
  { locationId: 'B', material: 'white', lastCollection: '2026-02-20', lastFillPercent: 100, collections: 1 },
  { locationId: 'A', material: 'white', lastCollection: '2026-04-01', lastFillPercent: 100, collections: 1 },
]
const snapshot = { asOf: '2026-03-01', observationCount: 4, firstDate: '2026-02-20', lastDate: '2026-03-01', bins: source }
test('joining a historical snapshot never displays stale or future readings', () => {
  assert.deepEqual(knownBins(snapshot, locations, '2026-02-01'), [])
  assert.deepEqual(knownBins(null, locations, '2026-03-01'), [])
  const bins = knownBins(snapshot, locations, '2026-03-01')
  assert.deepEqual(bins.map(b => b.material), ['brown', 'green'])
  assert.equal(bins[0].key, 'A:brown')
  assert.equal(bins[0].latitude, 49.14)
  assert.equal(source.length, 4)
})
test('location cards group materials without replacing individual bin identity', () => {
  const bins = knownBins(snapshot, locations, '2026-03-01')
  const clusters = clusterBins(bins)
  assert.equal(clusters.length, 1)
  assert.equal(clusters[0].bins.length, 2)
  assert.deepEqual(clusters[0].bins.map(b => b.key), ['A:brown', 'A:green'])
  assert.deepEqual(clusterBins([]), [])
})
test('historical thresholds include the boundary, preserve unknowns when off, and never impute fill', () => {
  const [brown, green] = knownBins(snapshot, locations, '2026-03-01')
  assert.equal(matchesHistoricalFill(brown, 80), true)
  assert.equal(matchesHistoricalFill(brown, 85), false)
  assert.equal(matchesHistoricalFill(green, 0), true)
  assert.equal(matchesHistoricalFill(green, 5), false)
})
test('CSV exports one row per selected bin with cutoff, original measurement dates, and escaped notes', () => {
  const stops = clusterBins(knownBins(snapshot, locations, '2026-03-01'))
  const csv = planCsv('2026-03-01', stops, { A: 'Gate, "north"\nUse side entrance' })
  assert.ok(csv.startsWith('"planning_date","stop","location_id"'))
  assert.ok(csv.includes('"2026-03-01","1","A","brown","2026-03-01","80"'))
  assert.ok(csv.includes('"2026-03-01","1","A","green","2026-02-20",""'))
  assert.ok(csv.includes('"Gate, ""north""\nUse side entrance"'))
  assert.ok(!csv.includes('2026-04-01'))
  assert.equal(planCsv('2026-03-01', [], {}).split('\r\n').length, 1)
})

test('overfull remains distinct from unknown and matches high historical thresholds without a fake percentage', async () => {
  const base = knownBins(snapshot, locations, '2026-03-01')[0]
  const overfull = { ...base, lastFillPercent: null, lastIsOverfull: true }
  const full = { ...base, lastFillPercent: 100, lastIsOverfull: false }
  const unknown = { ...base, lastFillPercent: null, lastIsOverfull: false }
  assert.equal(historicalFillLabel(null, true), 'Overfull')
  assert.equal(historicalFillLabel(null, false), 'Unknown')
  assert.equal(historicalFillLabel(0, false), '0%')
  assert.equal(historicalFillLabel(100, false), '100%')
  assert.equal(matchesHistoricalFill(overfull, 100), true)
  assert.equal(matchesHistoricalFill(unknown, 100), false)
  assert.ok(historicalFillRank(overfull) > historicalFillRank(full))
  assert.equal(overfull.lastFillPercent, null)
  const csv = planCsv('2026-03-01', clusterBins([overfull]), {})
  assert.ok(csv.includes('"was_overfull"'))
  assert.ok(csv.includes('"brown","2026-03-01","","true"'))
  assert.ok(!csv.includes('110'))
})
