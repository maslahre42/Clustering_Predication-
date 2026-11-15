import test from 'node:test'
import assert from 'node:assert/strict'
import { proposalMap, mapPoint } from '../apps/web/app/features/proposal/domain/routeMap.ts'
import { createRouteMapState } from '../apps/web/app/features/proposal/state/createRouteMapState.ts'
import { sampleProposal } from './helpers/proposal.mjs'
import { component, mount, ref, h, nextTick } from './helpers/vue.mjs'

const locations = ['A', 'B', 'C', 'D'].map(locationId => ({ locationId, latitude: 49.15, longitude: 9.22, isSynthetic: true }))
const coordinates = point => [point.latitude, point.longitude]

test('map preserves solver order, sequential stop numbers, unloading between loads and final return', () => {
  const proposal = sampleProposal(), model = proposalMap(proposal, locations), route = model.trucks[0]
  assert.deepEqual(route.stops.map(stop => [stop.locationId, stop.sequence, stop.load]), [['B', 1, 1], ['A', 2, 1], ['D', 3, 2]])
  assert.equal(route.weightKg, 3370.5)
  assert.equal(route.missing, 0)
  assert.equal(route.paths.length, 3)
  assert.deepEqual(route.paths[0].points.map(coordinates), proposal.plan.routes[0].roadPaths[0].points)
  assert.deepEqual(route.paths[1].points.map(coordinates), proposal.plan.routes[0].roadPaths[1].points)
  assert.equal(route.paths[2].returning, true)
  assert.deepEqual(route.paths[2].points.map(coordinates), proposal.plan.routes[0].roadPaths[2].points)
  assert.ok(route.stops.every(stop => stop.provenance === 'synthetic'))
  assert.deepEqual(model.unserved.map(stop => [stop.locationId, stop.reason]), [['C', 'Optional: no spare time']])
})

test('missing positions never borrow another inventory and missing street geometry has no aerial fallback', () => {
  const proposal = sampleProposal()
  proposal.stops.find(stop => stop.locationId === 'A').latitude = null
  const route = proposalMap(proposal, locations).trucks[0]
  assert.equal(route.missing, 1)
  assert.deepEqual(route.stops.map(stop => stop.sequence), [1, 3])
  assert.deepEqual(route.paths[0].points.map(coordinates), proposal.plan.routes[0].roadPaths[0].points)
  proposal.stops.forEach(stop => { stop.latitude = null; stop.longitude = null })
  proposal.plan.routes[0].roadPaths = []
  const empty = proposalMap(proposal, locations)
  assert.equal(empty.trucks[0].stops.length, 0)
  assert.equal(empty.trucks[0].missing, 3)
  assert.equal(empty.unserved.length, 0)
  assert.equal(empty.trucks[0].paths.length, 0) // no invented disposal -> yard line
})

test('invalid coordinates are omitted, zero is valid, and provenance requires the same coordinates', () => {
  assert.deepEqual(mapPoint(0, 0), { latitude: 0, longitude: 0 })
  for (const point of [[null, 1], [1, undefined], [NaN, 0], [Infinity, 0], [91, 0], [0, -181]]) assert.equal(mapPoint(...point), null)
  const proposal = sampleProposal()
  let stops = proposalMap(proposal).trucks[0].stops
  assert.ok(stops.every(stop => stop.provenance === 'unverified'))
  stops = proposalMap(proposal, locations.map(location => ({ ...location, isSynthetic: false }))).trucks[0].stops
  assert.ok(stops.every(stop => stop.provenance === 'imported'))
  stops = proposalMap(proposal, locations.map(location => ({ ...location, latitude: 20 }))).trucks[0].stops
  assert.ok(stops.every(stop => stop.provenance === 'unverified'))
})

function twoTrucks() {
  const proposal = sampleProposal()
  proposal.plan.routes.push({ truck: 2, trips: [{ stops: ['C'], weightKg: 735, volumeL: 2100 }], hours: 0.5, distanceKm: null, bins: 1 })
  proposal.plan.unserved = []
  return proposal
}

test('truck and load filters, stop inspection and proposal resets remain request-local', () => {
  const source = ref(twoTrucks()), state = createRouteMapState(source, ref(locations))
  assert.equal(state.stops.value.length, 4)
  const color = state.model.value.trucks[1].color
  assert.notEqual(color, state.model.value.trucks[0].color)
  state.selectTruck(1); state.selectedLoad.value = '2'
  assert.deepEqual(state.stops.value.map(stop => stop.locationId), ['D'])
  assert.equal(state.visibleTrucks.value[0].paths.length, 2) // load 2 plus return
  state.selectedStop.value = state.stops.value[0].key
  assert.equal(state.activeStop.value.locationId, 'D')
  state.fit(); assert.equal(state.activeStop.value, null)
  state.selectTruck(2)
  assert.equal(state.selectedLoad.value, '')
  assert.equal(state.visibleTrucks.value[0].color, color)
  assert.equal(state.provenance.value, 'Synthetic site assignments')
  state.showUnserved.value = true
  source.value = sampleProposal()
  assert.equal(state.selectedTruck.value, null)
  assert.equal(state.showUnserved.value, false)
  const other = createRouteMapState(ref(sampleProposal()), ref([]))
  state.selectTruck(1)
  assert.equal(other.selectedTruck.value, null)
  assert.equal(other.provenance.value, 'Unverified site coordinates')
})

test('map controls focus a truck/load, inspect stops and expand without changing the plan', async t => {
  const proposal = twoTrucks(), original = JSON.stringify(proposal)
  const m = mount(t, await component('ProposalRouteMap'), { proposal, locations }, undefined, {
    UiButton: await component('UiButton'), UiSelect: await component('UiSelect'), UiCheckbox: await component('UiCheckbox'),
    ClientOnly: { render() { return this.$slots.default?.() } },
    ProposalLeafletMap: { props: ['trucks', 'yard', 'disposal', 'unserved', 'activeStop', 'fitVersion'],
      render() { return h('div', { 'data-trucks': this.trucks.map(truck => truck.truck).join(','), 'data-active': this.activeStop?.locationId ?? '' }) } },
  })
  const buttonText = n => [n.text, ...n.children.map(buttonText)].join(' ')
  const button = label => m.all().find(n => n.tag === 'button' && buttonText(n).includes(label))
  button('Truck 1').props.onClick(); await nextTick()
  assert.equal(m.all().find(n => n.props['data-trucks'] !== undefined).props['data-trucks'], '1')
  m.find('select').props.onChange({ target: { value: '2' } }); await nextTick()
  assert.match(m.text(), /Load 2/)
  assert.doesNotMatch(m.text(), /Location B/)
  m.all().find(n => n.tag === 'button' && n.props['aria-label'] === 'Truck 1, stop 3, location D').props.onClick(); await nextTick()
  assert.equal(m.all().find(n => n.props['data-active'] !== undefined).props['data-active'], 'D')
  button('Expand map').props.onClick(); await nextTick()
  assert.match(m.text(), /Compact map/)
  assert.match(m.text(), /Car routes do not establish truck-specific access/)
  assert.equal(JSON.stringify(proposal), original)
})
