import test from 'node:test'
import assert from 'node:assert/strict'
import { component, mount, h, nextTick } from './helpers/vue.mjs'
import { sampleProposal } from './helpers/proposal.mjs'
import { DEFAULT_PROPOSAL_SETTINGS, validateSettings } from '../apps/web/app/features/proposal/domain/settings.ts'

const Badge = { props: ['material'], render() { return h('span', {}, this.material) } }
const Card = { render() { return h('section', {}, this.$slots.default?.()) } } // UiCard is template-only
async function controls() {
  return { UiTable: await component('UiTable'), UiInput: await component('UiInput'), UiButton: await component('UiButton'),
    UiCheckbox: await component('UiCheckbox'), UiTag: await component('UiTag'), UiIcon: { render: () => null }, UiCard: Card, GlassFractionBadge: Badge }
}

test('route table lists stops per truck and load with weights and urgency', async t => {
  const m = mount(t, await component('ProposalRoutesTable'), { proposal: sampleProposal() }, undefined, await controls())
  const rows = m.all().filter(n => n.tag === 'tr' && n.children.some(c => c.tag === 'td'))
  assert.equal(rows.length, 3)
  const text = m.text()
  assert.match(text, /Truck 1/); assert.match(text, /Load 2/)
  assert.match(text, /945 kg/); assert.match(text, /Must empty/); assert.match(text, /If time allows/)
  assert.match(text, /1 h 45 min/)
})

test('route table says so when nothing needs collecting', async t => {
  const proposal = sampleProposal(); proposal.plan.routes = []
  const m = mount(t, await component('ProposalRoutesTable'), { proposal }, undefined, await controls())
  assert.match(m.text(), /No truck is needed/)
})

test('settings form shows source labels, reports edits and blocks an invalid apply', async t => {
  const Form = await component('ProposalSettingsForm')
  const edits = [], events = []
  const props = errors => ({ settings: { ...DEFAULT_PROPOSAL_SETTINGS }, errors, dirty: true,
    onNumber: (key, raw) => edits.push([key, raw]), onFlag: (key, value) => edits.push([key, value]),
    onReset: () => events.push('reset') })
  const m = mount(t, Form, props({}), undefined, await controls())
  assert.match(m.text(), /PreZero/); assert.match(m.text(), /Assumption/)
  const inputs = m.all().filter(n => n.tag === 'input' && n.props.type !== 'checkbox')
  assert.ok(inputs.length >= 10)
  const payload = inputs.find(n => n.props.value === '12')
  payload.props.onInput({ target: { value: '8' } }); await nextTick()
  assert.deepEqual(edits[0], ['truckPayloadT', '8'])
  m.all().find(n => n.tag === 'input' && n.props.type === 'checkbox').props.onChange({ target: { checked: true } })
  assert.deepEqual(edits[1], ['workSaturday', true])
  const button = (root, label) => root.all().find(n => n.tag === 'button' && n.children.some(c => c.text?.includes(label)) || n.tag === 'button' && n.text?.includes(label))
  assert.equal(button(m, 'Apply').props.disabled, false)
  button(m, 'Apply').props.onClick(); button(m, 'Reset').props.onClick()
  assert.equal(m.applied.length, 1) // the mount helper records apply events itself
  assert.deepEqual(events, ['reset'])

  const invalid = mount(t, Form, props(validateSettings({ ...DEFAULT_PROPOSAL_SETTINGS, truckPayloadT: 0 })), undefined, await controls())
  assert.equal(button(invalid, 'Apply').props.disabled, true)
  assert.match(invalid.text(), /greater than 0/)
})
