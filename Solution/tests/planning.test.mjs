import test from 'node:test'
import assert from 'node:assert/strict'
import { distanceKm, orderStops, groupStops, roundTripKm } from '../apps/web/app/shared/domain/geometry.ts'
test('geographic distance is symmetric, zero at the same point, and plausible', () => {
  const a = { latitude: 49, longitude: 9 }
  const b = { latitude: 50, longitude: 9 }
  assert.equal(distanceKm(a, a), 0)
  assert.equal(distanceKm(a, b), distanceKm(b, a))
  assert.ok(distanceKm(a, b) > 111 && distanceKm(a, b) < 112)
})
test('ordering visits nearest first without dropping or mutating stops', () => {
  const depot = { latitude: 49, longitude: 9 }
  const far = { latitude: 49.1, longitude: 9, id: 'far' }
  const near = { latitude: 49.01, longitude: 9, id: 'near' }
  const original = [far, near]
  assert.deepEqual(orderStops(original, depot), [near, far])
  assert.deepEqual(original, [far, near])
  assert.deepEqual(orderStops([], depot), [])
})

test('distance follows the short path across the antimeridian', () => {
  const a = { latitude: 0, longitude: 179.9 }
  const b = { latitude: 0, longitude: -179.9 }
  assert.ok(distanceKm(a, b) > 22 && distanceKm(a, b) < 23)
  assert.ok(Number.isFinite(distanceKm(a, { latitude: 0, longitude: -0.1 })))
})
test('next stop is chosen from the previous stop rather than always from depot', () => {
  const depot = { latitude: 0, longitude: 0 }
  const a = { latitude: 0, longitude: 1, id: 'A' }
  const b = { latitude: 0, longitude: -1.1, id: 'B' }
  const c = { latitude: 0, longitude: 2, id: 'C' }
  assert.deepEqual(orderStops([b, c, a], depot).map(s => s.id), ['A', 'C', 'B'])
})
test('equal-distance and colocated stops are retained in stable order', () => {
  const depot = { latitude: 49, longitude: 9 }
  const bins = [{ ...depot, id: 'brown' }, { ...depot, id: 'green' }]
  assert.deepEqual(orderStops(bins, depot), bins)
})
test('one location containing three selected glass bins becomes one stop', () => {
  const bins = [
    { locationId: 'A', latitude: 49, longitude: 9, material: 'brown' },
    { locationId: 'A', latitude: 49, longitude: 9, material: 'green' },
    { locationId: 'B', latitude: 49.1, longitude: 9, material: 'green' },
    { locationId: 'A', latitude: 49, longitude: 9, material: 'white' },
  ]
  assert.deepEqual(groupStops(bins).map(b => b.locationId), ['A', 'B'])
  assert.equal(bins.length, 4)
  assert.deepEqual(groupStops([]), [])
})
test('round trip includes depot departure and return and handles empty plans', () => {
  const depot = { latitude: 49, longitude: 9 }
  const stop = { latitude: 49.1, longitude: 9 }
  assert.equal(roundTripKm([], depot), 0)
  assert.equal(roundTripKm([depot], depot), 0)
  assert.equal(roundTripKm([stop], depot), 2 * distanceKm(depot, stop))
  const another = { latitude: 49.2, longitude: 9.1 }
  assert.equal(roundTripKm([stop, another], depot), distanceKm(depot, stop) + distanceKm(stop, another) + distanceKm(another, depot))
})
