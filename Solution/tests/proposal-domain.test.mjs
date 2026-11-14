import test from 'node:test'
import assert from 'node:assert/strict'
import { createRequire } from 'node:module'
import { DECISION_LABELS, REASON_LABELS, routeRows, servedBinKeys, servedOrder, proposalSummary, proposalCsv, topRisks, formatHours } from '../apps/web/app/features/proposal/domain/proposal.ts'
import { sampleProposal } from './helpers/proposal.mjs'
import { createWorkspaceModel } from '../apps/web/app/features/workspace/model.ts'
import { API_ROUTES } from '../apps/web/app/shared/api/routes.ts'
const require = createRequire(new URL('../apps/web/package.json', import.meta.url))
const { ref, effectScope } = require('vue')

test('proposal endpoint is routed through the web proxy allow-list', () => {
  assert.equal(API_ROUTES.proposal, '/api/proposal')
})

test('every decision and unserved reason has a plain-language label', () => {
  for (const decision of ['due', 'neighbour', 'optional', 'skipped', 'no_forecast']) assert.ok(DECISION_LABELS[decision])
  for (const reason of ['exceeds_truck_capacity', 'exceeds_shift', 'fleet_limit', 'optional_not_scheduled', 'missing_coordinates']) assert.ok(REASON_LABELS[reason])
})

test('route rows follow truck, load and stop order and list only the bins that are emptied', () => {
  const rows = routeRows(sampleProposal())
  assert.deepEqual(rows.map(row => [row.truck, row.load, row.sequence, row.locationId]), [[1, 1, 1, 'B'], [1, 1, 2, 'A'], [1, 2, 3, 'D']])
  assert.deepEqual(rows[1].materials, ['green', 'white']) // brown at A is skipped
  assert.equal(rows[1].bins, 2)
  assert.equal(rows[1].mandatory, true)
  assert.equal(rows[2].mandatory, false)
  assert.equal(rows[0].weightKg, 945)
  assert.equal(rows[0].risk, 0.75)
})

test('served bins and order exclude skipped bins and unserved stops', () => {
  const proposal = sampleProposal()
  assert.deepEqual(servedOrder(proposal), ['B', 'A', 'D'])
  assert.deepEqual(servedBinKeys(proposal), ['B:white', 'A:white', 'A:green', 'D:white'])
})

test('summary counts decisions and keeps unserved mandatory stops visible', () => {
  const proposal = sampleProposal()
  assert.deepEqual(proposalSummary(proposal), { due: 2, neighbour: 1, optional: 2, skipped: 1, noForecast: 1, mandatoryStops: 2, optionalStops: 2, unservedMandatory: 0, unservedOptional: 1 })
  proposal.plan.unserved.push({ locationId: 'B', mandatory: true, reason: 'fleet_limit' })
  assert.equal(proposalSummary(proposal).unservedMandatory, 1)
})

test('highest overflow risk comes first and bins without forecast come last', () => {
  const top = topRisks(sampleProposal(), 3)
  assert.deepEqual(top.map(b => `${b.locationId}:${b.material}`), ['A:white', 'B:white', 'D:white'])
  const all = topRisks(sampleProposal())
  assert.equal(all.length, 7)
  assert.equal(all.at(-1).decision, 'no_forecast')
})

test('route sheet CSV has one line per emptied bin, quoted, in route order', () => {
  const lines = proposalCsv(sampleProposal()).split('\r\n')
  assert.equal(lines[0], '"plan_date","truck","load","stop","location_id","material","decision","expected_fill_percent","overflow_probability","estimated_weight_kg","last_emptied","history_through"')
  assert.equal(lines.length, 5)
  assert.equal(lines[1], '"2026-08-17","1","1","1","B","white","due","90.0","0.75","945","2026-08-03","2026-08-14"')
  assert.match(lines[2], /"A","white","due"/); assert.match(lines[3], /"A","green","neighbour"/)
  assert.match(lines[4], /^"2026-08-17","1","2","3","D"/)
})

test('hours are shown as hours and minutes', () => {
  assert.equal(formatHours(1.75), '1 h 45 min'); assert.equal(formatHours(0.5), '30 min'); assert.equal(formatHours(8), '8 h 00 min')
})

function workspace(t) {
  const asOf = ref('2026-08-14')
  const material = (locationId, m) => ({ locationId, material: m, lastCollection: '2026-08-03', lastFillPercent: 50, collections: 3 })
  const snapshot = ref({ asOf: asOf.value, observationCount: 9, firstDate: '2026-01-01', lastDate: asOf.value,
    bins: [material('A', 'white'), material('A', 'green'), material('A', 'brown'), material('B', 'white'), material('D', 'white')] })
  const locations = ref(['A', 'B', 'D'].map((locationId, i) => ({ locationId, latitude: 49.15 + i * 0.01, longitude: 9.22, isSynthetic: true })))
  const scope = effectScope(); t.after(() => scope.stop())
  return { asOf, model: scope.run(() => createWorkspaceModel(asOf, { snapshot, locations, error: ref(null) })) }
}

test('a proposal can be handed to the manual collection plan in its route order', t => {
  const { model } = workspace(t)
  const proposal = sampleProposal()
  model.plan.toggleBin('A:brown', true)
  model.plan.notes.value = { A: 'old note' }
  model.plan.applyProposal(servedBinKeys(proposal), servedOrder(proposal))
  assert.deepEqual([...model.plan.selectedKeys.value].sort(), ['A:green', 'A:white', 'B:white', 'D:white']) // replaces the manual selection
  assert.deepEqual(model.plan.stops.value.map(s => s.locationId), ['B', 'A', 'D'])
  assert.deepEqual(model.plan.notes.value, {})
  model.plan.moveStop('D', -1) // still editable afterwards
  assert.deepEqual(model.plan.stops.value.map(s => s.locationId), ['B', 'D', 'A'])
})

test('unknown bins in a proposal are ignored and changing the date clears the applied plan', t => {
  const { model, asOf } = workspace(t)
  model.plan.applyProposal(['A:white', 'ZZ:white', 'B:blue'], ['ZZ', 'A'])
  assert.deepEqual(model.plan.selectedKeys.value, ['A:white'])
  assert.deepEqual(model.plan.stops.value.map(s => s.locationId), ['A'])
  asOf.value = '2026-08-13'
  assert.deepEqual(model.plan.selectedKeys.value, [])
  assert.deepEqual(model.plan.routeOrder.value, [])
})
