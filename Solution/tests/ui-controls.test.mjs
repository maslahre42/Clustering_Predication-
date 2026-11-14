import test, { after } from 'node:test'
import assert from 'node:assert/strict'
import { component, mount, h, nextTick, descendants } from './helpers/vue.mjs'

test('native button prevents accidental form submission and disables loading actions', async t => {
  const m = mount(t, await component('UiButton'), { label: 'Apply date', loading: true })
  assert.equal(m.find('button').props.type, 'button')
  assert.equal(m.find('button').props.disabled, true)
  assert.equal(m.find('button').props['aria-busy'], true)
  assert.match(m.text(), /Apply date/)
})
test('partial location checkbox exposes mixed state and emits an individual boolean', async t => {
  const m = mount(t, await component('UiCheckbox'), { label: 'Brown glass', modelValue: false, indeterminate: true })
  const input = m.find('input')
  assert.equal(input.props['aria-checked'], 'mixed')
  assert.equal(input.props.indeterminate, true)
  assert.equal(m.find('label').props.for, input.props.id)
  input.props.onChange({ target: { checked: true } })
  assert.deepEqual(m.changes, [true])
})
test('recorded-fill slider retains its domain bounds and emits a number', async t => {
  const m = mount(t, await component('UiSlider'), { label: 'Recorded fill', modelValue: 0, min: 0, max: 100, step: 5 })
  const input = m.find('input')
  assert.equal(input.props.max, 100)
  assert.equal(input.props.step, 5)
  input.props.onInput({ target: { value: '70' } })
  assert.deepEqual(m.changes, [70])
})
test('optional material select supports clearing without inventing a material', async t => {
  const m = mount(t, await component('UiSelect'), { label: 'Glass fraction', options: [{ value: 'brown', label: 'Brown' }], modelValue: 'brown' })
  assert.match(m.text(), /All materials/)
  m.find('select').props.onChange({ target: { value: '' } })
  assert.deepEqual(m.changes, [''])
})
test('empty and populated tables preserve headers and do not show an empty message beside actual rows', async t => {
  const Table = await component('UiTable')
  const empty = mount(t, Table, {}, { head: () => h('tr', {}, h('th', {}, 'Date')), default: () => [], empty: () => 'No observations' })
  assert.match(empty.text(), /No observations/)
  const populated = mount(t, Table, {}, { head: () => h('tr', {}, h('th', {}, 'Date')), default: () => h('tr', {}, h('td', {}, '2026-09-30')), empty: () => 'No observations' })
  await nextTick()
  assert.match(populated.text(), /2026-09-30/)
  assert.doesNotMatch(populated.text(), /No observations/)
})

test('sort selects cannot offer an unrelated all-materials option', async t => {
  const m = mount(t, await component('UiSelect'), { label: 'Sort locations', allowEmpty: false, modelValue: 'recent', options: [{ value: 'recent', label: 'Latest collection' }] })
  assert.match(m.text(), /Latest collection/)
  assert.doesNotMatch(m.text(), /All materials/)
})

// Components use document only to register/unregister the outside-click listener.
const originalDocument = globalThis.document
globalThis.document = { addEventListener() {}, removeEventListener() {} }
after(() => { if (originalDocument) globalThis.document = originalDocument; else delete globalThis.document })

async function calendarFixture(t, props = {}) {
  return mount(t, await component('CollectionDatePicker'), {
    label: 'Planning date', modelValue: '2026-09-30', min: '2025-10-17', max: '2026-10-07', required: true, ...props,
  }, undefined, { UiIcon: await component('UiIcon'), UiIconButton: await component('UiIconButton'), UiButton: await component('UiButton') })
}

test('calendar component rejects out-of-range clicks, emits ISO dates, and restores trigger focus', async t => {
  const m = await calendarFixture(t)
  m.find('details').open = true
  const invalidDay = m.all().find(n => n.props['data-date'] === '2026-10-08')
  assert.equal(invalidDay.props.disabled, true)
  invalidDay.props.onClick()
  assert.deepEqual(m.changes, [])
  m.all().find(n => n.props['data-date'] === '2026-09-29').props.onClick()
  assert.deepEqual(m.changes, ['2026-09-29'])
  assert.equal(m.find('details').open, false)
  assert.equal(m.find('summary').focused, true)
  assert.doesNotMatch(m.text(), /Clear/)
})

test('calendar arrow navigation moves focus across months without committing a date', async t => {
  const m = await calendarFixture(t)
  const current = m.all().find(n => n.props['data-date'] === '2026-09-30')
  let prevented = false
  await current.props.onKeydown({ key: 'ArrowRight', preventDefault() { prevented = true } })
  await nextTick()
  assert.equal(prevented, true)
  assert.match(m.text(), /October 2026/)
  assert.equal(m.all().find(n => n.props['data-date'] === '2026-10-01').focused, true)
  assert.deepEqual(m.changes, [])
})

test('optional history dates clear while disabled calendars cannot change the cutoff', async t => {
  const optional = await calendarFixture(t, { required: false })
  optional.all().find(n => n.tag === 'button' && n.text === 'Clear').props.onClick()
  assert.deepEqual(optional.changes, [undefined])
  const disabled = await calendarFixture(t, { disabled: true })
  disabled.all().find(n => n.props['data-date'] === '2026-09-29').props.onClick()
  assert.deepEqual(disabled.changes, [])
  assert.equal(disabled.find('summary').props['aria-disabled'], true)
})


test('planning calendar stages a selection and only commits through its Apply date button', async t => {
  const m = await calendarFixture(t, { confirm: true })
  m.find('details').open = true
  const apply = () => m.all().find(n => n.tag === 'button' && descendants(n).filter(child => child.tag !== '#comment').map(child => child.text).join('').trim() === 'Apply date')
  assert.equal(apply().props.disabled, true)
  m.all().find(n => n.props['data-date'] === '2026-09-29').props.onClick()
  await nextTick()
  assert.equal(m.find('details').open, true)
  assert.deepEqual(m.changes, [])
  assert.deepEqual(m.applied, [])
  assert.equal(apply().props.disabled, false)
  apply().props.onClick()
  assert.deepEqual(m.changes, ['2026-09-29'])
  assert.deepEqual(m.applied, ['2026-09-29'])
  assert.equal(m.find('details').open, false)
  assert.equal(m.find('summary').focused, true)
})

test('cancelling a planning date leaves the active cutoff unchanged and reopening discards the draft', async t => {
  const m = await calendarFixture(t, { confirm: true })
  m.find('details').open = true
  m.all().find(n => n.props['data-date'] === '2026-09-29').props.onClick()
  await nextTick()
  m.all().find(n => n.tag === 'button' && n.text === 'Cancel').props.onClick()
  assert.deepEqual(m.applied, [])
  assert.deepEqual(m.changes, [])
  m.find('details').open = true
  m.find('details').props.onToggle()
  await nextTick()
  assert.equal(m.all().find(n => n.props['data-date'] === '2026-09-30').props['aria-pressed'], true)
  assert.equal(m.all().find(n => n.tag === 'button' && descendants(n).filter(child => child.tag !== '#comment').map(child => child.text).join('').trim() === 'Apply date').props.disabled, true)
})

test('sortable headers expose direction and emit sorting from a native button', async t => {
  const Header = await component('UiSortableHeader')
  let sorts = 0
  const active = mount(t, Header, { label: 'Collections', active: true, direction: 'asc', onSort: () => sorts++ })
  assert.equal(active.find('th').props['aria-sort'], 'ascending')
  assert.match(active.find('button').props['aria-label'], /descending/)
  active.find('button').props.onClick()
  assert.equal(sorts, 1)
  const inactive = mount(t, Header, { label: 'Glass', active: false, direction: 'desc' })
  assert.equal(inactive.find('th').props['aria-sort'], 'none')
  assert.match(inactive.find('button').props['aria-label'], /ascending/)
})

