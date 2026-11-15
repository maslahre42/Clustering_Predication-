import test from 'node:test'
import assert from 'node:assert/strict'
import { monthCoverage } from '../apps/web/app/features/analytics/domain/patterns.ts'
import { createPatternTrends } from '../apps/web/app/features/analytics/state/createPatternTrends.ts'
import { component, mount, ref, nextTick, h } from './helpers/vue.mjs'

test('month coverage identifies first and last partial months and handles leap years', () => {
  assert.equal(monthCoverage('2026-09', '2026-09-08'), 'Partial · 2026-09-01–2026-09-08')
  assert.equal(monthCoverage('2025-10', '2026-09-30', '2025-10-17'), 'Partial · 2025-10-17–2025-10-31')
  assert.equal(monthCoverage('2026-09', '2026-09-30', '2025-10-17'), null)
  assert.equal(monthCoverage('2024-02', '2024-02-28'), 'Partial · 2024-02-01–2024-02-28')
  assert.equal(monthCoverage('2024-02', '2024-02-29'), null)
  assert.equal(monthCoverage('2026-09', '2026-09-08', '2026-09-07'), 'Partial · 2026-09-07–2026-09-08')
})

const row = (month, material, collections, meanNumericFill = 50) =>
  ({ month, material, collections, overfullCount: 0, numericReadings: collections, meanNumericFill })

test('trend filtering, measure and cutoff changes recompute scale without mutating inputs', () => {
  const original = [row('2026-09', 'brown', 9, 260 / 9), row('2026-07', 'brown', 20, null),
    row('2026-08', 'brown', 10, 0), row('2026-08', 'white', 30, 60), row('2026-10', 'brown', 100)]
  const months = ref(original), asOf = ref('2026-09-08'), firstDate = ref('2026-07-01')
  const trend = createPatternTrends(months, asOf, firstDate)
  assert.deepEqual(trend.rows.value.map(row => row.month), ['2026-07', '2026-08', '2026-09'])
  assert.equal(trend.rows.value[0].value, null)
  assert.equal(trend.rows.value[0].width, 0)
  assert.equal(trend.rows.value[1].value, 0)
  assert.equal(trend.rows.value[2].coverage, 'Partial · 2026-09-01–2026-09-08')
  trend.metric.value = 'collections'
  assert.deepEqual(trend.rows.value.map(row => row.width), [100, 50, 45])
  trend.material.value = 'white'
  assert.equal(trend.rows.value.length, 1)
  assert.equal(trend.rows.value[0].width, 100)
  asOf.value = '2026-07-31'
  assert.deepEqual(trend.rows.value, [])
  assert.equal(original[0].month, '2026-09')
})

test('trend controls update actual chart labels and counts', async t => {
  const m = mount(t, await component('CollectionPatternTrends'), {
    months: [row('2026-09', 'brown', 9, 260 / 9), row('2026-09', 'white', 20, null)], asOf: '2026-09-08',
  }, undefined, { UiCard: { render() { return h('section', {}, this.$slots.default()) } }, UiSelect: await component('UiSelect') })
  assert.match(m.text(), /28\.9%/)
  assert.match(m.text(), /Partial · 2026-09-01–2026-09-08/)
  const selects = m.all().filter(n => n.tag === 'select')
  selects[0].props.onChange({ target: { value: 'white' } }); await nextTick()
  assert.doesNotMatch(m.text(), /28\.9%/)
  assert.match(m.text(), /—/)
  selects[1].props.onChange({ target: { value: 'collections' } }); await nextTick()
  assert.equal(m.all().find(n => n.tag === 'ol').props['aria-label'], 'white glass monthly collections')
  assert.match(m.text(), /20 collections/)
})

test('review flags retain unknown rates and open the corresponding location', async t => {
  const opened = []
  const patterns = { cycles: [{ material: 'brown', numericCycles: 0, lowerBoundCycles: 3, medianRatePercentPerDay: null }], reviewBinCount: 1,
    reviewBins: [{ locationId: 'site-A', material: 'white', collections: 3, lowCollections: 0, overfullCollections: 2, reason: 'repeated_overfull' }] }
  const m = mount(t, await component('CollectionPatternEvidence'), { patterns, onInspect: id => opened.push(id) }, undefined, {
    UiCard: { render() { return h('section', {}, this.$slots.default()) } }, UiTable: await component('UiTable'), UiButton: await component('UiButton'),
    GlassFractionBadge: { props: ['material'], render() { return h('span', {}, this.material) } },
  })
  assert.match(m.text(), /Repeated overfull/)
  assert.match(m.text(), /—/)
  m.all().find(n => n.tag === 'button').props.onClick()
  assert.deepEqual(opened, ['site-A'])
})
