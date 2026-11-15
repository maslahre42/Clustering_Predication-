import test from 'node:test'
import assert from 'node:assert/strict'
import { monthlyDashboard } from '../apps/web/app/features/analytics/domain/monthlyDashboard.ts'
import { component, mount, h } from './helpers/vue.mjs'
const row = (month, material, extra = {}) => ({ month, material, collections: 10, numericReadings: 8, overfullCount: 1, meanNumericFill: 50, activeDays: 3, fullOrOverfullCount: 2, prematureCount: 4, ...extra })
test('dashboard keeps all four charts, all streams, cutoff, partial months and exact denominators', () => {
  const source = [row('2026-01', 'white'), row('2026-01', 'brown'), row('2026-03', 'white'), row('2026-04', 'white')]
  const result = monthlyDashboard(source, '2026-03-15', '2026-01-10')
  assert.equal(result.charts.length, 4)
  assert.deepEqual(result.charts[0].series.map(s => s.key), ['white', 'green', 'brown'])
  assert.equal(result.charts[0].series[1].points[0].value, null)
  assert.equal(result.charts[1].series[0].points[0].value, 3)
  assert.equal(result.charts[3].series[0].points[0].value, 20)
  assert.equal(result.charts[3].series[1].points[0].value, 40)
  assert.deepEqual(result.months.map(m => m.month), ['2026-01', '2026-03'])
  assert.match(result.months[0].coverage, /2026-01-10/)
  assert.match(result.months[1].coverage, /2026-03-15/)
  assert.equal(source.length, 4)
})
test('unknown means and missing months break lines; zero remains a measured value', () => {
  const result = monthlyDashboard([row('2026-01', 'white', { meanNumericFill: 0 }), row('2026-02', 'brown'), row('2026-03', 'white', { meanNumericFill: null }), row('2026-04', 'white')], '2026-04-30')
  const series = result.charts[2].series[0]
  assert.deepEqual(series.points.map(p => p.value), [0, null, null, 50])
  assert.equal((series.path.match(/M/g) ?? []).length, 2)
  const empty = monthlyDashboard([], '2026-01-01')
  assert.ok(empty.charts.every(c => c.maximum > 0))
})
test('actual dashboard renders four labeled charts and accessible data', async t => {
  const m = mount(t, await component('MonthlyDashboard'), { months: [row('2026-01', 'white')], asOf: '2026-01-10' }, undefined, {
    UiCard: { render() { return h('section', {}, this.$slots.default()) } }, UiTable: { render() { return h('table', {}, this.$slots.default()) } },
  })
  assert.equal(m.all().filter(n => n.tag === 'svg' && n.props.role === 'img').length, 4)
  assert.match(m.text(), /View chart data/)
  assert.match(m.text(), /including unknown/)
  assert.match(m.text(), /Partial/)
})
