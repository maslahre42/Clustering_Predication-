import test from 'node:test'
import assert from 'node:assert/strict'
import { component, mount, h, nextTick, ref } from './helpers/vue.mjs'
import { createHistoryFilters } from '../apps/web/app/features/history/state/createHistoryFilters.ts'

async function analyticsComponents() {
  return {
    UiTable: await component('UiTable'), UiSelect: await component('UiSelect'),
    UiPagination: await component('UiPagination'), UiSortableHeader: await component('UiSortableHeader'),
    GlassFractionBadge: { props: ['material'], render() { return h('span', {}, this.material) } },
  }
}
test('monthly table sorts the whole dataset and resets the page when filtering or sorting', async t => {
  const months = Array.from({ length: 15 }, (_, index) => ({
    month: `2026-${String(index + 1).padStart(2, '0')}`, material: index % 2 ? 'brown' : 'green',
    collections: index + 1, overfullCount: 0, numericReadings: 1, meanNumericFill: 50,
  }))
  const m = mount(t, await component('MonthlyCollectionTable'), { months }, undefined, await analyticsComponents())
  const button = label => m.all().find(n => n.tag === 'button' && n.props['aria-label'] === label)
  button('Next page').props.onClick(); await nextTick()
  assert.equal(button('Previous page').props.disabled, false)
  button('Sort by Collections ascending').props.onClick(); await nextTick()
  assert.equal(button('Previous page').props.disabled, true)
  assert.equal(m.all().filter(n => n.tag === 'td')[2].text, '1')
  button('Sort by Collections descending').props.onClick(); await nextTick()
  assert.equal(m.all().filter(n => n.tag === 'td')[2].text, '15')
  m.find('select').props.onChange({ target: { value: 'brown' } }); await nextTick()
  assert.equal(m.all().filter(n => n.tag === 'td')[2].text, '14')
  assert.equal(button('Next page').props.disabled, true)
})
test('material statistics filter rows and sort the low-fill distribution column', async t => {
  const makeRow = (material, low) => ({ material, collections: 5, overfullCount: 1, numericReadings: 4,
    unknownCount: 0, meanNumericFill: 50, medianIntervalDays: 7, intervalCount: 3, distribution: { low0To30: low } })
  const m = mount(t, await component('MaterialAnalyticsTable'), { materials: [makeRow('brown', 3), makeRow('green', 1)] }, undefined, await analyticsComponents())
  m.all().find(n => n.tag === 'button' && n.props['aria-label'] === 'Sort by Readings ≤30% ascending').props.onClick()
  await nextTick()
  assert.equal(m.all().find(n => n.tag === 'td').children[0].text, 'green')
  m.find('select').props.onChange({ target: { value: 'brown' } }); await nextTick()
  assert.equal(m.all().filter(n => n.tag === 'td').length, 7)
  assert.equal(m.all().find(n => n.tag === 'td').children[0].text, 'brown')
})

test('collection records Glass fraction header forwards clicks into the server query', async t => {
  const Table = await component('HistoryTable')
  const components = { ...await analyticsComponents(), UiButton: await component('UiButton') }
  const Parent = {
    setup() {
      const filters = createHistoryFilters(ref('2026-03-01'), ref(undefined))
      return () => h(Table, { history: { items: [], total: 200 }, page: filters.page.value,
        sortBy: filters.sortBy.value, sortDirection: filters.sortDirection.value,
        onSort: field => { filters.sort(field); requests.push({ ...filters.query.value }) },
      })
    },
  }
  const requests = []
  const m = mount(t, Parent, {}, undefined, components)
  const button = () => m.all().find(n => n.tag === 'button' && n.props['aria-label']?.startsWith('Sort by Glass fraction'))
  button().props.onClick(); await nextTick()
  assert.equal(requests[0].sortBy, 'material')
  assert.equal(requests[0].sortDirection, 'asc')
  assert.equal(requests[0].asOf, '2026-03-01')
  assert.equal(m.all().find(n => n.tag === 'th' && n.props['aria-sort'] === 'ascending')?.children[0].props['aria-label'], 'Sort by Glass fraction descending')
  button().props.onClick(); await nextTick()
  assert.equal(requests[1].sortBy, 'material')
  assert.equal(requests[1].sortDirection, 'desc')
})
