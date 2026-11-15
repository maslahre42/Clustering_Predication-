import test from 'node:test'
import assert from 'node:assert/strict'
import { createRequire } from 'node:module'
import { createAnalysisState } from '../apps/web/app/features/proposal/state/createAnalysisState.ts'
import { DEFAULT_PROPOSAL_SETTINGS, SETTING_GROUPS, validateSettings } from '../apps/web/app/features/proposal/domain/settings.ts'
const require = createRequire(new URL('../apps/web/package.json', import.meta.url))
const { ref, effectScope } = require('vue')

function fixture(t, transport) {
  const scope=effectScope(); t.after(()=>scope.stop())
  const asOf=ref('2026-08-17'), settings=ref({...DEFAULT_PROPOSAL_SETTINGS})
  const state=scope.run(()=>createAnalysisState(asOf,settings,transport))
  t.after(state.dispose)
  return {state,asOf,settings}
}

test('every numeric operating parameter is editable and validated',()=>{
  const numeric=Object.keys(DEFAULT_PROPOSAL_SETTINGS).filter(k=>typeof DEFAULT_PROPOSAL_SETTINGS[k]==='number').sort()
  assert.deepEqual(SETTING_GROUPS.flatMap(g=>g.fields.map(f=>f.key)).sort(),numeric)
  for (const key of numeric) assert.ok(validateSettings({...DEFAULT_PROPOSAL_SETTINGS,[key]:NaN})[key],key)
})

test('forecast request binds cutoff, bin, horizon and applied operating values',async t=>{
  let sent
  const {state}=fixture(t,{forecast:async q=>(sent=q,{asOf:q.asOf,points:[]}),simulation:async()=>({})})
  state.forecastInput.value={locationId:'A',material:'green',horizonDays:30}
  await state.runForecast()
  assert.deepEqual(sent,{asOf:'2026-08-17',locationId:'A',material:'green',horizonDays:30})
  assert.equal(state.forecast.value.asOf,'2026-08-17')
})

test('changing cutoff cancels in-flight results instead of displaying stale forecasts',async t=>{
  let complete,signal
  const {state,asOf}=fixture(t,{forecast:(q,s)=>{signal=s;return new Promise(resolve=>{complete=resolve})},simulation:async()=>({})})
  state.forecastInput.value.locationId='A'
  const pending=state.runForecast()
  asOf.value='2026-08-16'
  complete({asOf:'2026-08-17',points:[]});await pending
  assert.equal(signal.aborted,true)
  assert.equal(state.forecast.value,null)
})

test('simulation validates time bounds and binds seed plus all changed operational values',async t=>{
  const calls=[]
  const {state,settings}=fixture(t,{forecast:async()=>({}),simulation:async q=>{calls.push(q);return {asOf:q.asOf}}})
  state.simulationInput.value={start:'2026-07-01',end:'2026-08-17',seed:7}
  await state.runSimulation();assert.equal(calls.length,0);assert.match(state.simulationError.value,/1–31/)
  settings.value={...settings.value,truckPayloadT:8,neighbourProbability:.2}
  state.simulationInput.value={start:'2026-08-10',end:'2026-08-17',seed:42}
  await state.runSimulation()
  assert.deepEqual(calls[0],{asOf:'2026-08-17',truckPayloadT:8,neighbourProbability:.2,start:'2026-08-10',end:'2026-08-17',seed:42})
  settings.value={...settings.value,truckPayloadT:9}
  assert.equal(state.simulation.value,null)
  assert.equal(state.simulationInput.value.start,'2026-08-10')
})

test('changing the analysis dataset cancels pending simulation and clears selected forecast bin',async t=>{
  const scope=effectScope();t.after(()=>scope.stop())
  const dataset=ref(null),asOf=ref('2026-08-14'),settings=ref({...DEFAULT_PROPOSAL_SETTINGS})
  let resolve,signal
  const state=scope.run(()=>createAnalysisState(asOf,settings,{forecast:async()=>({}),simulation:(q,s)=>{signal=s;return new Promise(r=>{resolve=r})}},dataset))
  t.after(state.dispose)
  state.forecastInput.value.locationId='A'
  const pending=state.runSimulation()
  dataset.value={name:'uploaded.csv',csv:'different dataset'}
  resolve({scenarios:[]});await pending
  assert.equal(signal.aborted,true);assert.equal(state.simulation.value,null)
  assert.equal(state.forecastInput.value.locationId,'')
})
