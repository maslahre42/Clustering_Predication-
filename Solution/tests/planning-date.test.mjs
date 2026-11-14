import test from 'node:test'
import assert from 'node:assert/strict'
import { createRequire } from 'node:module'
import { createPlanningDate } from '../apps/web/app/features/workspace/planningDate.ts'
const require = createRequire(new URL('../apps/web/package.json', import.meta.url))
const { ref, effectScope } = require('vue')
const range = { firstDate: '2025-10-17', lastDate: '2026-09-30', maxPlanningDate: '2026-10-07' }
function fixture(t, current = '2026-11-14', initial = range) {
  const asOf = ref(current), source = ref(initial), scope = effectScope()
  t.after(() => scope.stop())
  return { asOf, source, model: scope.run(() => createPlanningDate(asOf, source)) }
}
test('planning dates include the first data day and exactly seven days after the last', t => {
  const { model: m } = fixture(t)
  for (const value of ['2025-10-17', '2026-09-30', '2026-10-07']) assert.equal(m.isAllowedDate(value), true)
  for (const value of ['2025-10-16', '2026-10-08', 'bad', null, '2026-02-30']) assert.equal(m.isAllowedDate(value), false)
})
test('out-of-range defaults become the latest real observation; invalid apply cannot change the cutoff', t => {
  const { model: m, asOf } = fixture(t)
  assert.equal(asOf.value, '2026-09-30')
  assert.equal(m.applyPlanningDate('2026-10-07'), true)
  assert.equal(m.applyPlanningDate('2026-10-08'), false)
  assert.equal(asOf.value, '2026-10-07')
})
test('valid dates are preserved and ranges arriving asynchronously update safely', t => {
  const { model: m, asOf, source } = fixture(t, '2026-09-01', null)
  assert.equal(m.applyPlanningDate('2026-09-01'), false)
  source.value = range
  assert.equal(asOf.value, '2026-09-01')
  source.value = { firstDate: '2026-09-15', lastDate: '2026-09-30', maxPlanningDate: '2026-10-07' }
  assert.equal(asOf.value, '2026-09-30')
})
test('empty or malformed date metadata disables planning selection', t => {
  const { model: m, source } = fixture(t, '2026-09-30', { firstDate: null, lastDate: null, maxPlanningDate: null })
  assert.equal(m.bounds.value, null)
  source.value = { ...range, maxPlanningDate: '2026-01-01' }
  assert.equal(m.bounds.value, null)
  assert.equal(m.applyPlanningDate('2026-09-30'), false)
})
