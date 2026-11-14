import test from 'node:test'
import assert from 'node:assert/strict'
import { createRequire } from 'node:module'
import { createHistoryFilters } from '../apps/web/app/features/history/state/createHistoryFilters.ts'
const require = createRequire(new URL('../apps/web/package.json', import.meta.url))
const { ref, effectScope } = require('vue')
function fixture(t) {
  const asOf = ref('2026-03-01'), location = ref(undefined), scope = effectScope()
  t.after(() => scope.stop())
  return { asOf, location, filters: scope.run(() => createHistoryFilters(asOf, location)) }
}
test('history filters always send the cutoff even when a later end date is chosen', t => {
  const { filters: f } = fixture(t)
  assert.equal(f.query.value.pageSize, 50)
  f.to.value = '2099-01-01'
  assert.equal(f.query.value.asOf, '2026-03-01')
  assert.equal(f.query.value.to, '2099-01-01')
  assert.equal(f.query.value.material, undefined)
})
test('changing filters resets pagination synchronously', t => {
  const { filters: f } = fixture(t)
  f.page.value = 3; f.material.value = 'green'
  assert.equal(f.page.value, 1)
  f.page.value = 2; f.selected.value = 'A'
  assert.equal(f.query.value.page, 1)
  assert.equal(f.query.value.locationId, 'A')
})
test('date and initial-location changes reset query state without removing the cutoff', t => {
  const { filters: f, asOf, location } = fixture(t)
  f.material.value = 'brown'; f.from.value = '2026-01-01'; f.page.value = 3
  asOf.value = '2026-02-01'
  assert.equal(f.to.value, '2026-02-01'); assert.equal(f.from.value, null)
  assert.equal(f.query.value.asOf, '2026-02-01'); assert.equal(f.page.value, 1)
  location.value = 'B'
  assert.equal(f.query.value.locationId, 'B')
  f.selected.value = 'A'; f.reset()
  assert.equal(f.selected.value, 'B')
})

test('sorting toggles direction, resets pagination, and reaches the server query', t => {
  const { filters: f } = fixture(t)
  assert.equal(f.sortBy.value, 'date')
  assert.equal(f.sortDirection.value, 'desc')
  f.page.value = 4; f.sort('date')
  assert.equal(f.page.value, 1)
  assert.equal(f.query.value.sortDirection, 'asc')
  f.sort('date'); assert.equal(f.query.value.sortDirection, 'desc')
  f.sort('fill'); assert.equal(f.query.value.sortBy, 'fill')
  assert.equal(f.query.value.sortDirection, 'asc')
  assert.equal(f.query.value.asOf, '2026-03-01')
})
test('location search trims the query and reset restores default sorting and filters', t => {
  const { filters: f } = fixture(t)
  f.page.value = 3; f.locationSearch.value = ' SITE-A '
  assert.equal(f.page.value, 1)
  assert.equal(f.query.value.locationSearch, 'SITE-A')
  f.sort('material'); f.reset()
  assert.equal(f.query.value.locationSearch, undefined)
  assert.equal(f.query.value.sortBy, 'date')
  assert.equal(f.query.value.sortDirection, 'desc')
})
