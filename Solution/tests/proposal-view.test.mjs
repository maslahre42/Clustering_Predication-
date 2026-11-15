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

test('settings require streets and have no fixed-time challenge controls', async t => {
  const m = mount(t, await component('ProposalSettingsForm'), { settings: { ...DEFAULT_PROPOSAL_SETTINGS },
    errors: {}, dirty: false }, undefined, await controls())
  assert.match(m.text(), /OSRM/)
  assert.match(m.text(), /compact service sectors/)
  assert.doesNotMatch(m.text(), /Fixed-time challenge|Driving time between stops|Straight-line detour/)
})

test('route table says so when nothing needs collecting', async t => {
  const proposal = sampleProposal(); proposal.plan.routes = []; proposal.plan.unserved = []; proposal.stops = []
  const m = mount(t, await component('ProposalRoutesTable'), { proposal }, undefined, await controls())
  assert.match(m.text(), /No truck is needed/)
})

test('an infeasible route is not described as no collection needed', async t => {
  const proposal = sampleProposal(); proposal.plan.routes = []
  const m = mount(t, await component('ProposalRoutesTable'), { proposal }, undefined, await controls())
  assert.match(m.text(), /No feasible truck route/)
  assert.doesNotMatch(m.text(), /No truck is needed/)
})

test('forecast chart preserves overfull as an observed category and labels its uncertainty band', async t => {
  const forecast = { lastEmptied: '2026-08-14', medianDaysToFull: 20, note: 'Not a service guarantee.',
    history: [{ date: '2026-08-14', fill: null, isOverfull: true }],
    points: [{ date:'2026-08-17', expectedFill:20, lower:5,upper:50,risk:.1 },{date:'2026-09-17',expectedFill:90,lower:60,upper:100,risk:.7}] }
  const m=mount(t,await component('ForecastExplorer'),{forecast})
  assert.match(m.text(),/Overfull/);assert.doesNotMatch(m.text(),/110%/)
  assert.match(m.text(),/10–90%/);assert.ok(m.find('svg'))
})

test('simulation comparison shows service, missed collections, cost and simulation qualifications', async t => {
  const scenario={name:'historical',label:'Historical',site_visits:12,bin_collections:30,truckDays:2,hours:8,
    mean_fill_at_collection_pct:60,share_collections_below_40pct:.2,overflow_bin_days:10,overflow_events:2,missedMandatory:3,
    daily:[{date:'2026-08-10',stops:12}]}
  const result={start:'2026-08-10',end:'2026-08-10',knownBins:100,trainingThrough:'2026-08-09',seed:7,effectiveSolverTimeSeconds:1,
    scenarios:[scenario,{...scenario,name:'dynamic',label:'Dynamic',site_visits:10}],frontier:[],assumptions:['Shared model family.']}
  const m=mount(t,await component('SimulationResults'),{result})
  assert.match(m.text(),/not measured savings/);assert.match(m.text(),/Missed mandatory stop-days/)
  assert.match(m.text(),/selection-only|Selection-only/);assert.ok(m.find('svg'))
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
  assert.deepEqual(edits[1], ['workMonday', true])
  const button = (root, label) => root.all().find(n => n.tag === 'button' && n.children.some(c => c.text?.includes(label)) || n.tag === 'button' && n.text?.includes(label))
  assert.equal(button(m, 'Apply').props.disabled, false)
  button(m, 'Apply').props.onClick(); button(m, 'Reset').props.onClick()
  assert.equal(m.applied.length, 1) // the mount helper records apply events itself
  assert.deepEqual(events, ['reset'])

  const invalid = mount(t, Form, props(validateSettings({ ...DEFAULT_PROPOSAL_SETTINGS, truckPayloadT: 0 })), undefined, await controls())
  assert.equal(button(invalid, 'Apply').props.disabled, true)
  assert.match(invalid.text(), /greater than 0/)
})

test('settings prioritize trucks and working time while advanced options stay collapsed', async t => {
  const m = mount(t, await component('ProposalSettingsForm'), {
    settings: { ...DEFAULT_PROPOSAL_SETTINGS }, errors: {}, dirty: false,
  }, undefined, await controls())
  const groups = m.all().filter(n => n.tag === 'details')
  const text = n => [n.text, ...n.children.map(text)].join(' ')
  assert.equal(groups.filter(n => n.props.open).length, 2)
  assert.ok(groups.filter(n => n.props.open).every(n => /Trucks|Working time/.test(text(n))))
  assert.ok(groups.filter(n => !n.props.open).some(n => /Selection rule/.test(text(n))))
})

test('invalid advanced settings expand so their errors can be corrected', async t => {
  const m = mount(t, await component('ProposalSettingsForm'), {
    settings: { ...DEFAULT_PROPOSAL_SETTINGS, depotLatitude: 100 },
    errors: { depotLatitude: 'Must be at most 90.' }, dirty: true,
  }, undefined, await controls())
  const text = n => [n.text, ...n.children.map(text)].join(' ')
  const group = m.all().find(n => n.tag === 'details' && /Travel and depot/.test(text(n)))
  assert.equal(group.props.open, true)
  assert.match(text(group), /Must be at most 90/)
})

test('simulation waits for applied settings and appears before optional forecast exploration', async t => {
  const Analysis = await component('ForecastAnalysis')
  const components = { ...await controls(), SimulationResults: { render: () => null }, ForecastExplorer: { render: () => null } }
  const props = { asOf: '2026-08-20', settings: { ...DEFAULT_PROPOSAL_SETTINGS }, proposal: sampleProposal(), dataset: null }
  const m = mount(t, Analysis, { ...props, settingsDirty: true }, undefined, components)
  const text = n => [n.text, ...n.children.map(text)].join(' ')
  const run = m.all().find(n => n.tag === 'button' && /Run simulation/.test(text(n)))
  assert.equal(run.props.disabled, true)
  // Guard the request handler as well as the disabled appearance.
  assert.doesNotThrow(() => run.props.onClick())
  assert.match(m.text(), /Apply your collection settings above/)
  assert.ok(m.text().indexOf('Simulation & backtest') < m.text().indexOf('Explore a container'))
  assert.equal(m.find('details').props.open, undefined)
  const applied = mount(t, Analysis, { ...props, settingsDirty: false }, undefined, components)
  assert.equal(applied.all().find(n => n.tag === 'button' && /Run simulation/.test(text(n))).props.disabled, false)
})

test('combined-project validation reports matched cases and distinguishes the bounded one-load check',async t=>{
  const comparison={targets:10,evaluated:10,commonNumericCases:6,commonCensoredCases:2,unknownTargets:0,note:'Identical targets; lower bounds excluded from MAE.',
    models:[{name:'omar',label:'Seasonal cycle model',available:10,mae:12,bias:-2,lowerBoundShortfall:5},{name:'zakaria',label:'Frozen cycle-median model',available:10,mae:14,bias:3,lowerBoundShortfall:7},{name:'kaise',label:'Persistence reference',available:8,mae:20,bias:-5,lowerBoundShortfall:15}]}
  const optimization={date:'2026-08-10',sites:['A','B'],status:'solver_unavailable',message:'Configure a valid license.',scope:'one-load-per-truck',complete:false,note:'Sample only; one load per truck.'}
  const m=mount(t,await component('ProjectValidationResults'),{comparison,optimization})
  assert.match(m.text(),/6 shared uncensored numeric cases/)
  assert.match(m.text(),/Persistence reference/);assert.match(m.text(),/12.00/)
  assert.match(m.text(),/solver_unavailable/);assert.match(m.text(),/Sample only/)
})

test('data evidence exposes failed grouping gates and preserves unknown and overfull counts',async t=>{
  const evidence={rows:20,bins:5,dateMin:'2026-01-01',dateMax:'2026-02-01',unknown:2,overfull:3,warnings:[],source:'uploaded-csv',fingerprint:'abc123456789000',
    grouping:{method:'rule_tiers',gate:{silhouette:true,separability:false},eligible:4,insufficient:1,note:'Reset-aware rates.',profiles:[{label:'low_pressure',n_series:4,feature_medians:{mean_fill_pct:30,median_rate_pct_per_day:2}}],labels:[]}}
  const m=mount(t,await component('ProposalDataEvidence'),{evidence},undefined,await controls())
  assert.match(m.text(),/2 unknown readings/);assert.match(m.text(),/3 overfull/)
  assert.match(m.text(),/Descriptive pressure tiers/);assert.match(m.text(),/failed — tiers used/)
  assert.match(m.text(),/uploaded-csv/)
})
