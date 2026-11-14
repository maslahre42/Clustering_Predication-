import test from 'node:test'
import assert from 'node:assert/strict'
import { createRequire } from 'node:module'
import { createWorkspaceModel } from '../apps/web/app/features/workspace/model.ts'
const require = createRequire(new URL('../apps/web/package.json', import.meta.url))
const { ref, effectScope } = require('vue')
function fixture(t, configuration) {
  const asOf = ref('2026-03-01')
  const snapshot = ref({ asOf: asOf.value, observationCount: 4, firstDate: '2026-02-01', lastDate: asOf.value, bins: [
    { locationId: 'A', material: 'brown', lastCollection: asOf.value, lastFillPercent: 80, collections: 1 },
    { locationId: 'A', material: 'green', lastCollection: '2026-02-20', lastFillPercent: 20, collections: 1 },
    { locationId: 'B', material: 'white', lastCollection: asOf.value, lastFillPercent: 100, collections: 1 },
    { locationId: 'C', material: 'green', lastCollection: '2026-02-01', lastFillPercent: null, collections: 1 },
  ] })
  const locations = ref(['A', 'B', 'C'].map((locationId, i) => ({ locationId, latitude: 49.1427 + (i + 1) * .01, longitude: 9.2185, isSynthetic: true })))
  const error = ref(null)
  const scope = effectScope()
  t.after(() => scope.stop())
  return { model: scope.run(() => createWorkspaceModel(asOf, { snapshot, locations, error }, configuration)), asOf, snapshot, error }
}
test('selects valid bins once, preserves fractions, and ignores unknown bin keys', t => {
  const { model: m } = fixture(t)
  m.plan.toggleBin('A:brown', true); m.plan.toggleBin('A:brown', true); m.plan.toggleBin('unknown', true)
  assert.deepEqual(m.plan.selectedKeys.value, ['A:brown'])
  m.plan.toggleBin('A:green', true)
  assert.equal(m.plan.selectedBins.value.length, 2)
  assert.equal(m.plan.stops.value.length, 1)
  m.plan.toggleBin('A:brown', false)
  assert.deepEqual(m.plan.selectedKeys.value, ['A:green'])
})
test('group selection changes only currently matching fractions', t => {
  const { model: m } = fixture(t)
  m.plan.toggleBin('A:green', true)
  m.filters.material.value = 'brown'; m.plan.toggleLocation('A', true); m.plan.toggleLocation('A', false)
  assert.deepEqual(m.plan.selectedKeys.value, ['A:green'])
  m.filters.material.value = ''; m.plan.toggleLocation('A', true)
  assert.deepEqual(new Set(m.plan.selectedKeys.value), new Set(['A:green', 'A:brown']))
})
test('combines case-insensitive search, fractions, and historical threshold; sorting stays deterministic', t => {
  const { model: m } = fixture(t)
  m.filters.search.value = ' a '; m.filters.material.value = 'brown'; m.filters.minimumFill.value = 80
  assert.deepEqual(m.filters.filteredBins.value.map(b => b.key), ['A:brown'])
  m.filters.minimumFill.value = 85
  assert.equal(m.filters.filteredBins.value.length, 0)
  m.filters.resetFilters(); m.filters.sort.value = 'fill'
  assert.deepEqual(m.filters.filteredClusters.value.map(c => c.locationId), ['B', 'A', 'C'])
  m.filters.resetFilters()
  assert.deepEqual(m.filters.filteredClusters.value.map(c => c.locationId), ['A', 'B', 'C'])
})
test('same-day collections respect filters and do not select older readings', t => {
  const { model: m } = fixture(t)
  m.filters.material.value = 'brown'; m.plan.addDayCollections()
  assert.deepEqual(m.plan.selectedKeys.value, ['A:brown'])
  m.filters.resetFilters(); m.plan.addDayCollections(); m.plan.addDayCollections()
  assert.deepEqual(m.plan.selectedKeys.value, ['A:brown', 'B:white'])
})
test('changing date immediately clears the plan and hides stale responses until matching data arrives', t => {
  const { model: m, asOf, snapshot } = fixture(t)
  m.plan.toggleLocation('A', true); m.navigation.inspect('A'); m.plan.notes.value.A = 'Gate'; m.plan.routeOrder.value = ['A']
  asOf.value = '2026-02-01'
  assert.deepEqual(m.plan.selectedKeys.value, [])
  assert.deepEqual(m.plan.notes.value, {})
  assert.deepEqual(m.plan.routeOrder.value, [])
  assert.equal(m.navigation.inspectedLocation.value, '')
  assert.equal(m.data.ready.value, false)
  assert.deepEqual(m.data.bins.value, [])
  assert.deepEqual(m.plan.routePoints.value, [])
  m.plan.toggleBin('A:brown', true)
  assert.deepEqual(m.plan.selectedKeys.value, [])
  snapshot.value = { ...snapshot.value, asOf: asOf.value, bins: [snapshot.value.bins[3]] }
  assert.equal(m.data.ready.value, true)
  assert.deepEqual(m.data.bins.value.map(b => b.key), ['C:green'])
})
test('navigation and filter reset preserve selections; clearing the draft removes notes and manual order', t => {
  const { model: m } = fixture(t)
  m.plan.toggleBin('B:white', true); m.navigation.view.value = 'manifest'; m.navigation.view.value = 'planning'; m.filters.resetFilters()
  assert.deepEqual(m.plan.selectedKeys.value, ['B:white'])
  m.plan.notes.value.B = 'Access note'; m.plan.routeOrder.value = ['B']; m.plan.clearPlan()
  assert.deepEqual(m.plan.notes.value, {}); assert.deepEqual(m.plan.routeOrder.value, [])
  assert.equal(m.plan.distance.value, 0); assert.deepEqual(m.plan.routePoints.value, [])
})
test('manual ordering updates route points, ignores invalid moves, and retains new stops without duplicates', t => {
  const { model: m } = fixture(t)
  for (const id of ['A', 'B', 'C']) m.plan.toggleLocation(id, true)
  assert.deepEqual(m.plan.stops.value.map(s => s.locationId), ['A', 'B', 'C'])
  m.plan.moveStop('C', -1)
  assert.deepEqual(m.plan.stops.value.map(s => s.locationId), ['A', 'C', 'B'])
  assert.equal(m.plan.routePoints.value[2].locationId, 'C')
  m.plan.moveStop('A', -1); m.plan.moveStop('B', 1); m.plan.moveStop('unknown', 1)
  assert.deepEqual(m.plan.stops.value.map(s => s.locationId), ['A', 'C', 'B'])
  m.plan.removeStop('A')
  assert.deepEqual(m.plan.stops.value.map(s => s.locationId), ['C', 'B'])
  assert.ok(!m.plan.selectedKeys.value.some(k => k.startsWith('A:')))
  m.plan.routeOrder.value = []
  assert.deepEqual(m.plan.stops.value.map(s => s.locationId), ['B', 'C'])
})
test('errors fail closed for all visible data, selection, and inspection', t => {
  const { model: m, error } = fixture(t)
  error.value = new Error('API unavailable')
  assert.equal(m.data.ready.value, false); assert.deepEqual(m.filters.filteredBins.value, [])
  m.plan.toggleBin('A:brown', true); m.navigation.inspect('A')
  assert.deepEqual(m.plan.selectedKeys.value, []); assert.equal(m.navigation.view.value, 'planning')
})

test('highest recorded fill ordering puts overfull before full and keeps overflow flags after grouping', t => {
  const { model: m, snapshot } = fixture(t)
  snapshot.value.bins[0] = { ...snapshot.value.bins[0], lastFillPercent: null, lastIsOverfull: true }
  m.filters.minimumFill.value = 100; m.filters.sort.value = 'fill'
  assert.deepEqual(m.filters.filteredClusters.value.map(c => c.locationId), ['A', 'B'])
  assert.equal(m.filters.filteredClusters.value[0].bins[0].lastIsOverfull, true)
  m.plan.toggleBin('A:brown', true)
  assert.equal(m.plan.stops.value[0].bins[0].lastIsOverfull, true)
})

test('depot configuration is injectable and isolated from caller-owned settings', t => {
  const configuration = { depot: { latitude: 49.5, longitude: 9.5, isSynthetic: false, name: 'Imported depot' } }
  const { model: m } = fixture(t, configuration)
  m.plan.toggleBin('A:brown', true)
  assert.equal(m.plan.routePoints.value[0].latitude, 49.5)
  assert.equal(m.plan.routePoints.value.at(-1).longitude, 9.5)
  assert.equal(m.plan.depot.isSynthetic, false)
  m.plan.depot.latitude = 50
  assert.equal(configuration.depot.latitude, 49.5)
})
test('workspaces do not share selection, notes or navigation across SSR requests', t => {
  const { model: first } = fixture(t), { model: second } = fixture(t)
  first.plan.toggleBin('A:brown', true)
  first.plan.notes.value.A = 'First request only'
  first.navigation.inspect('A')
  assert.deepEqual(second.plan.selectedKeys.value, [])
  assert.deepEqual(second.plan.notes.value, {})
  assert.equal(second.navigation.view.value, 'planning')
})

test('module navigation preserves the plan until the historical cutoff changes', t => {
  const { model: m, asOf } = fixture(t)
  m.plan.toggleBin('A:brown', true)
  assert.deepEqual(m.plan.selectedKeys.value, ['A:brown'])
  m.navigation.view.value = 'manifest'
  assert.deepEqual(m.plan.selectedKeys.value, ['A:brown'])
  m.navigation.view.value = 'analytics'
  assert.deepEqual(m.plan.selectedKeys.value, ['A:brown'])
  asOf.value = '2026-02-01'
  assert.deepEqual(m.plan.selectedKeys.value, [])
  assert.equal(m.navigation.view.value, 'analytics')
})
