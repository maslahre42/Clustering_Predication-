import test from 'node:test'
import assert from 'node:assert/strict'
import { coordinateSourceLabel } from '../apps/web/app/shared/domain/coordinates.ts'
import { knownBins, clusterBins } from '../apps/web/app/features/inventory/domain/catalog.ts'
import { planCsv } from '../apps/web/app/features/manifest/domain/planExport.ts'
test('coordinate labels distinguish absent, synthetic, real, and mixed sources', () => {
  assert.equal(coordinateSourceLabel([]), 'No locations')
  assert.equal(coordinateSourceLabel([{ isSynthetic: true }]), 'Synthetic coordinates')
  assert.equal(coordinateSourceLabel([{ isSynthetic: false }]), 'Imported coordinates')
  assert.equal(coordinateSourceLabel([{ isSynthetic: false }, { isSynthetic: true }]), 'Mixed coordinate sources')
})
test('real-coordinate provenance survives joins, stop grouping and CSV export', () => {
  const snapshot = { asOf: '2026-03-01', observationCount: 1, firstDate: '2026-03-01', lastDate: '2026-03-01', bins: [
    { locationId: 'A', material: 'green', lastCollection: '2026-03-01', lastFillPercent: 80, collections: 1 },
  ] }
  const bins = knownBins(snapshot, [{ locationId: 'A', latitude: 49, longitude: 9, isSynthetic: false }], snapshot.asOf)
  assert.equal(bins[0].isSynthetic, false)
  const stops = clusterBins(bins)
  assert.equal(stops[0].isSynthetic, false)
  assert.ok(planCsv(snapshot.asOf, stops, {}).includes('"49","9","false",""'))
})
