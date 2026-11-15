import test from 'node:test'
import assert from 'node:assert/strict'
import { createRequire } from 'node:module'
import { ref, component, mount, h, nextTick } from './helpers/vue.mjs'
import { capacityDefaults, capacityErrors, capacityCostDifference, jointPlanCsv } from '../apps/web/app/features/proposal/domain/capacity.ts'
import { createJointResults } from '../apps/web/app/features/proposal/state/createJointResults.ts'
import { createCapacityPlanning } from '../apps/web/app/features/proposal/state/createCapacityPlanning.ts'
import { DEFAULT_PROPOSAL_SETTINGS } from '../apps/web/app/features/proposal/domain/settings.ts'
const require=createRequire(new URL('../apps/web/package.json',import.meta.url));const {effectScope}=require('vue')
function fixture(t,transport){const scope=effectScope();t.after(()=>scope.stop());const asOf=ref('2026-09-30'),settings=ref({...DEFAULT_PROPOSAL_SETTINGS}),dataset=ref(null),dirty=ref(false);const state=scope.run(()=>createCapacityPlanning(asOf,settings,dataset,dirty,transport));t.after(state.dispose);return{state,asOf,settings,dataset,dirty}}
const Button={props:['label','disabled'],emits:['click'],render(){return h('button',{disabled:this.disabled,onClick:()=>this.$emit('click')},this.label)}}
const Card={render(){return h('section',{},this.$slots.default?.())}}
const scenario=name=>({name,intervalDays:7,installedContainers:3,truckDays:2,peakTrucks:1,distanceKm:20,workingHours:4,emptyingHours:2,containersEmptied:12,siteVisits:4,demandLitres:20000,collectedLitres:15000,remainingLitres:5000,spillLitres:0,fullStreamDays:1,pendingSites:0,pendingSiteDays:0,costs:{configured:true,partial:true,drivingIncluded:true,truckEuro:1000,roadEuro:null,containerEuro:null,totalEuro:1000,monthlyEquivalentEuro:2174.11},daily:[{date:'2026-10-01',truckDays:1}]})
const result=()=>({asOf:'2026-09-30',start:'2026-10-01',end:'2026-10-14',days:14,supportedStreams:3,excludedStreams:[],missingCoordinateSites:[],comparableService:true,fillingTimes:['brown','green','white'].map(material=>({material,supportedStreams:1,positiveStreams:1,zeroDemandStreams:0,historicalCycles:4,baselineAverageDays:10,alternativeAverageDays:20})),scenarios:[scenario('baseline'),scenario('alternative')],assumptions:['Common demand.']})

test('counts, frequency and period validate independently; default truck+driver rate is confirmed €500',()=>{
 assert.equal(DEFAULT_PROPOSAL_SETTINGS.fixedTruckCostEuro,500)
 assert.deepEqual(capacityErrors(capacityDefaults()),[])
 for(const change of [{days:32},{alternativeIntervalDays:0},{containerCostPerMonthEuro:-1},{alternativeContainers:{brown:1,green:1,white:1.5}}]) assert.ok(capacityErrors({...capacityDefaults(),...change}).length)
 const input=capacityDefaults();input.overrides=[{locationId:'A',material:'white',baselineCount:1,alternativeCount:2}];input.overrides.push({...input.overrides[0]});assert.ok(capacityErrors(input).length)
})
test('requests bind independent scenarios, site overrides, rates and uploaded CSV',async t=>{
 let sent;const f=fixture(t,async(q,body,signal)=>{sent={q,body,signal};return result()})
 f.dataset.value={name:'upload.csv',csv:'CSV'};f.settings.value.costPerKmEuro=1.2
 f.state.input.value.alternativeContainers.white=3;f.state.input.value.overrides=[{locationId:'A',material:'white',baselineCount:2,alternativeCount:3}]
 await f.state.run();assert.deepEqual(sent.q,{asOf:'2026-09-30',costPerKmEuro:1.2});assert.equal(sent.body.csv,'CSV');assert.equal(sent.body.alternativeContainers.white,3);assert.equal(sent.body.overrides[0].baselineCount,2);assert.ok(f.state.result.value)
})
for(const change of ['input','cutoff','settings','dataset','dirty'])test(`${change} changes abort pending comparisons and prevent stale financial results`,async t=>{
 let complete,signal;const f=fixture(t,(q,b,s)=>{signal=s;return new Promise(r=>{complete=r})});const pending=f.state.run()
 if(change==='input')f.state.input.value.alternativeIntervalDays=10
 if(change==='cutoff')f.asOf.value='2026-09-29'
 if(change==='settings')f.settings.value.fixedTruckCostEuro=600
 if(change==='dataset')f.dataset.value={name:'new',csv:'NEW'}
 if(change==='dirty')f.dirty.value=true
 complete(result());await pending;assert.equal(signal.aborted,true);assert.equal(f.state.result.value,null);assert.equal(f.state.pending.value,false)
})
test('invalid and unapplied controls make no requests; server input errors remain visible',async t=>{
 let calls=0;const f=fixture(t,async()=>{calls++;throw{data:{validation:{errors:[{message:'Unknown override site'}]}}}})
 f.dirty.value=true;await f.state.run();assert.equal(calls,0)
 f.dirty.value=false;f.state.input.value.days=99;await f.state.run();assert.equal(calls,0)
 f.state.input.value.days=14;await f.state.run();assert.equal(calls,1);assert.match(f.state.error.value,/Unknown override/)
})
test('cost differences remain unavailable when unpriced, and keep the signed alternative-minus-baseline direction',()=>{
 const r=result();r.scenarios[1].costs.totalEuro=500;assert.equal(capacityCostDifference(r),-500)
 r.scenarios[0].costs.totalEuro=null;assert.equal(capacityCostDifference(r),null)
})
test('actual controls bind container counts and collection intervals to the submitted body',async t=>{
 let sent;globalThis.useState=()=>ref(null);globalThis.$fetch=async(path,options)=>{sent=options;return result()};t.after(()=>{delete globalThis.$fetch;delete globalThis.useState})
 const m=mount(t,await component('CapacityPlanning'),{asOf:'2026-09-30',settings:{...DEFAULT_PROPOSAL_SETTINGS},dataset:null,dirty:false,bins:[{locationId:'A',material:'white'}]},undefined,{UiCard:Card,UiButton:Button,CapacityResults:{render(){return h('p','Financial results')}}})
 const input=m.all().find(n=>n.props['aria-label']==='Alternative white containers per site')
 input.value='3';input.props['onUpdate:modelValue'](3)
 // Period, baseline interval and alternative interval are labelled native inputs.
 const numeric=m.all().filter(n=>n.tag==='input');numeric[2].value='10';numeric[2].props['onUpdate:modelValue'](10)
 m.all().find(n=>n.tag==='button'&&n.text==='Compare financial impact').props.onClick();await nextTick();await nextTick()
 assert.equal(sent.body.alternativeContainers.white,3);assert.equal(sent.body.alternativeIntervalDays,10);assert.equal(sent.query.asOf,'2026-09-30')
})
test('financial results include unpriced categories, equal-demand outcomes, filling-time and shift charts',async t=>{
 const r=result();r.comparableService=false;r.excludedStreams=[{locationId:'X',material:'white'}]
 const m=mount(t,await component('CapacityResults'),{result:r})
 assert.match(m.text(),/not a savings claim/);assert.match(m.text(),/Unpriced/);assert.match(m.text(),/Partial inventory/);assert.match(m.text(),/Driving included in truck-day package/);assert.match(m.text(),/Same incoming glass demand/)
 assert.equal(m.all().filter(n=>n.tag==='svg').length,2);assert.match(m.text(),/Estimated average filling time/);assert.match(m.text(),/Daily truck shifts/)
})
test('site overrides preserve independent defaults and reject unknown or duplicate streams',t=>{
 const f=fixture(t,async()=>result()),known=[{locationId:'A',material:'white'}]
 f.state.input.value.alternativeContainers.white=3
 assert.equal(f.state.addOverride('A','white',known),true)
 assert.deepEqual({...f.state.input.value.overrides[0]},{locationId:'A',material:'white',baselineCount:1,alternativeCount:3})
 assert.equal(f.state.addOverride('A','white',known),false)
 assert.equal(f.state.addOverride('A','brown',known),false)
 assert.equal(f.state.input.value.overrides.length,1)
})

test('automatic search binds target, cycle, count limits and per-site space without changing manual input',async t=>{
 let sent;const f=fixture(t,async(q,b)=>{sent=b;return result()})
 assert.equal(f.state.setSiteLimit('A',5),true);assert.equal(f.state.setSiteLimit('A',6),true);assert.equal(f.state.input.value.siteLimits.length,1)
 f.state.input.value.targetFillPercent=85;f.state.input.value.optimizationWeeks=2
 await f.state.run(true)
 assert.equal(sent.optimize,true);assert.equal(sent.targetFillPercent,85);assert.equal(sent.optimizationWeeks,2);assert.deepEqual(sent.siteLimits,[{locationId:'A',maxContainers:6}])
 assert.equal(f.state.input.value.optimize,false)
 assert.ok(capacityErrors({...capacityDefaults(),optimize:true,minIntervalDays:30,optimizationWeeks:2}).length)
 assert.ok(capacityErrors({...capacityDefaults(),optimize:true,targetFillPercent:101}).length)
})
test('automatic results paginate inventory, reset filters and preserve actual route dates',()=>{
 const r=result();r.settings={...DEFAULT_PROPOSAL_SETTINGS};r.optimization={recommendations:Array.from({length:30},(_,i)=>({locationId:`A${i}`,material:i===0?'white':'green'})),collections:[]}
 r.scenarios[1].daily=[{date:'2026-10-01',truckDays:0},{date:'2026-10-02',truckDays:1,hours:2,distanceKm:10,siteVisits:1,containersEmptied:1,routes:[{truck:1,trips:[{stops:['A'],weightKg:100,volumeL:300}],bins:1,hours:2,distanceKm:10}],stops:[]}]
 const state=createJointResults(ref(r));assert.equal(state.selectedDate.value,'2026-10-02');assert.equal(state.rows.value.length,25)
 state.page.value=2;assert.equal(state.rows.value.length,5);state.material.value='white';assert.equal(state.page.value,1);assert.equal(state.rows.value.length,1)
 assert.equal(state.routeMap.value.planDate,'2026-10-02');state.selectedDate.value='2026-10-01';assert.equal(state.routeMap.value,null)
})
test('calendar CSV uses actual date, truck and visit order and escapes site identifiers',()=>{
 const r=result();r.scenarios[1].daily=[{date:'2026-10-01',routes:[{truck:2,trips:[{stops:['A,"B']}]}]}]
 r.optimization={collections:[{date:'2026-10-01',locationId:'A,"B',material:'white',containers:2,fillPercent:80,volumeL:4800}]}
 const csv=jointPlanCsv(r);assert.match(csv,/"2026-10-01","2","1","1","A,""B","white","2"/)
 assert.equal(csv.split('\r\n').length,2)
})
test('actual automatic-search button submits optimization mode with the configured bounds',async t=>{
 let sent;globalThis.useState=()=>ref(null);globalThis.$fetch=async(path,options)=>{sent=options.body;return result()};t.after(()=>{delete globalThis.$fetch;delete globalThis.useState})
 const m=mount(t,await component('CapacityPlanning'),{asOf:'2026-09-30',settings:{...DEFAULT_PROPOSAL_SETTINGS},dataset:null,dirty:false,bins:[]},undefined,{UiCard:Card,UiButton:Button,CapacityResults:{render(){return h('p','Results')}}})
 m.all().find(n=>n.tag==='button'&&n.text==='Find best containers & schedule').props.onClick();await nextTick();await nextTick()
 assert.equal(sent.optimize,true);assert.equal(sent.targetFillPercent,90);assert.equal(sent.maxContainersPerSite,9)
})
test('an infeasible automatic result offers no dispatch or calendar export',async t=>{
 const r=result();r.scenarios=r.scenarios.slice(0,1);r.optimization={status:'no-feasible-plan-found',targetFillPercent:90,candidatesEvaluated:0,recommendations:[],collections:[]}
 const m=mount(t,await component('JointPlanningResults'),{result:r,locations:[]},undefined,{UiButton:Button})
 assert.match(m.text(),/No feasible recommendation found/);assert.match(m.text(),/No unsafe plan is offered/);assert.doesNotMatch(m.text(),/Download optimized collection calendar/)
})

test('completed financial plans survive module navigation only while their inputs and dataset match',async t=>{
 const asOf=ref('2026-09-30'),settings=ref({...DEFAULT_PROPOSAL_SETTINGS}),dataset=ref(null),dirty=ref(false),cache=ref(null)
 const first=createCapacityPlanning(asOf,settings,dataset,dirty,async()=>result(),cache);await first.run(true);first.dispose()
 assert.ok(cache.value);const restored=createCapacityPlanning(asOf,settings,dataset,dirty,async()=>{throw Error('Must not rerun')},cache)
 assert.ok(restored.result.value);restored.input.value.targetFillPercent=85;assert.equal(cache.value,null);assert.equal(restored.result.value,null)
 await first.run(true);asOf.value='2026-09-29'
 const different=createCapacityPlanning(asOf,settings,dataset,dirty,async()=>result(),cache);assert.equal(different.result.value,null)
 t.after(()=>{first.dispose();restored.dispose();different.dispose()})
})
