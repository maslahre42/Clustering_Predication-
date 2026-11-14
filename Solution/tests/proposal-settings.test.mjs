import test from 'node:test'
import assert from 'node:assert/strict'
import { DEFAULT_PROPOSAL_SETTINGS, SETTING_GROUPS, validateSettings, proposalQuery } from '../apps/web/app/features/proposal/domain/settings.ts'
import { createProposalSettings } from '../apps/web/app/features/proposal/state/createProposalSettings.ts'

const fields = SETTING_GROUPS.flatMap(group => group.fields)

test('defaults are the numbers PreZero gave and every field says where its value comes from', () => {
  const d = DEFAULT_PROPOSAL_SETTINGS
  assert.deepEqual([d.containerVolumeM3, d.truckPayloadT, d.truckVolumeM3, d.shiftHours, d.fixedTravelMin, d.serviceMinPerBin], [3, 12, 0, 8, 10, 5])
  assert.equal(d.workSaturday, false); assert.equal(d.workSunday, false)
  assert.deepEqual(validateSettings(d), {})
  const source = key => fields.find(field => field.key === key).source
  for (const key of ['containerVolumeM3', 'truckPayloadT', 'shiftHours', 'fixedTravelMin', 'serviceMinPerBin']) assert.equal(source(key), 'PreZero')
  for (const key of ['glassDensityKgM3', 'truckVolumeM3', 'unloadMin']) assert.equal(source(key), 'Assumption')
  assert.equal(source('mustProbability'), 'Planner')
  for (const field of fields) {
    assert.ok(field.label && field.unit !== undefined && field.help, field.key)
    assert.equal(typeof d[field.key], 'number', field.key)
    assert.ok(d[field.key] >= field.min && d[field.key] <= field.max, `${field.key} default inside its own range`)
  }
  assert.equal(new Set(fields.map(field => field.key)).size, fields.length)
})

test('invalid values are named, not clipped', () => {
  const errors = validateSettings({ ...DEFAULT_PROPOSAL_SETTINGS, truckPayloadT: 0, shiftHours: 25, mustProbability: 1.2, maxVehicles: 2.5, glassDensityKgM3: Number.NaN })
  assert.deepEqual(Object.keys(errors).sort(), ['glassDensityKgM3', 'maxVehicles', 'mustProbability', 'shiftHours', 'truckPayloadT'])
  assert.match(errors.truckPayloadT, /greater than 0/)
  assert.match(errors.shiftHours, /24/)
  assert.match(errors.maxVehicles, /whole number/)
  assert.match(errors.glassDensityKgM3, /number/)
  assert.deepEqual(validateSettings({ ...DEFAULT_PROPOSAL_SETTINGS, truckVolumeM3: 0, fixedTravelMin: 0 }), {}) // zero means "not used" for these two
})

test('request sends the cutoff and only the values that differ from the defaults', () => {
  assert.deepEqual(proposalQuery('2026-08-14', DEFAULT_PROPOSAL_SETTINGS), { asOf: '2026-08-14' })
  assert.deepEqual(proposalQuery('2026-08-14', { ...DEFAULT_PROPOSAL_SETTINGS, truckPayloadT: 8, workSaturday: true, fixedTravelMin: 0 }),
    { asOf: '2026-08-14', truckPayloadT: 8, workSaturday: true, fixedTravelMin: 0 })
})

test('edits stay a draft until applied, and an invalid draft cannot be applied', () => {
  const s = createProposalSettings()
  assert.equal(s.dirty.value, false)
  s.setNumber('truckPayloadT', '8')
  assert.equal(s.draft.value.truckPayloadT, 8)
  assert.equal(s.applied.value.truckPayloadT, 12) // no request with half-typed numbers
  assert.equal(s.dirty.value, true)
  s.setNumber('shiftHours', 'abc')
  assert.ok(s.errors.value.shiftHours)
  assert.equal(s.apply(), false)
  assert.equal(s.applied.value.truckPayloadT, 12)
  s.setNumber('shiftHours', '9')
  assert.equal(s.apply(), true)
  assert.deepEqual([s.applied.value.truckPayloadT, s.applied.value.shiftHours], [8, 9])
  assert.equal(s.dirty.value, false)
  assert.deepEqual(s.changed.value.sort(), ['shiftHours', 'truckPayloadT'])
})

test('comma decimals are accepted, flags toggle, discard and reset restore values', () => {
  const s = createProposalSettings()
  s.setNumber('glassDensityKgM3', '412,5'); s.setFlag('workSaturday', true)
  assert.equal(s.draft.value.glassDensityKgM3, 412.5)
  assert.equal(s.apply(), true)
  s.setNumber('glassDensityKgM3', '500')
  s.discard()
  assert.equal(s.draft.value.glassDensityKgM3, 412.5)
  s.reset()
  assert.deepEqual(s.draft.value, DEFAULT_PROPOSAL_SETTINGS)
  assert.deepEqual(s.applied.value, DEFAULT_PROPOSAL_SETTINGS)
  assert.deepEqual(s.changed.value, [])
  assert.notEqual(s.draft.value, DEFAULT_PROPOSAL_SETTINGS) // the shared defaults object is never handed out for mutation
})
