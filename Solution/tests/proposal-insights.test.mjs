import test from 'node:test'
import assert from 'node:assert/strict'
import { ref, nextTick, component, mount, h } from './helpers/vue.mjs'
import { sampleProposal } from './helpers/proposal.mjs'
import { validateSettings, proposalQuery } from '../apps/web/app/features/proposal/domain/settings.ts'
import { compareScenarios, timingRows, daysLabel, euro, nextSlide } from '../apps/web/app/features/proposal/domain/insights.ts'
import { createScenarioComparison } from '../apps/web/app/features/proposal/state/createScenarioComparison.ts'
const plan = () => { const p=sampleProposal();p.dataset={ fingerprint:'source' };p.plan.totals.distanceKm=12.5;p.costs={configured:true,partial:false,totalEuro:165,variableEuro:15,fixedEuro:150,costPerKmEuro:1.2,fixedTruckCostEuro:150,trucks:1,distanceKm:12.5};p.settings.costPerKmEuro=1.2;p.settings.fixedTruckCostEuro=150;return p }
const Button={props:['label','disabled'],emits:['click'],render(){return h('button',{disabled:this.disabled,onClick:()=>this.$emit('click')},this.label)}}

test('explicit chamber sizes and cost rates bind into requests without assumptions',()=>{
 const p=plan().settings
 assert.deepEqual(validateSettings(p),{})
 const full={...p,brownCompartmentM3:2,greenCompartmentM3:3,whiteCompartmentM3:4}
 assert.deepEqual(validateSettings(full),{})
 assert.ok(validateSettings({...full,truckVolumeM3:8}).truckVolumeM3)
 assert.ok(validateSettings({...full,greenCompartmentM3:0}).greenCompartmentM3)
 assert.ok(validateSettings({...full,whiteCompartmentM3:.0001}).whiteCompartmentM3)
 assert.deepEqual(proposalQuery('2026-08-14',full),{asOf:'2026-08-14',brownCompartmentM3:2,greenCompartmentM3:3,whiteCompartmentM3:4,costPerKmEuro:1.2,fixedTruckCostEuro:150})
})

test('comparison only exposes differences as savings with matched completed service and inputs',()=>{
 const a=plan(),b=plan();b.settings.maxVehicles=3;b.settings.shiftHours=9;b.plan.totals.distanceKm=10;b.costs.totalEuro=162
 assert.deepEqual(compareScenarios(a,b),{comparable:true,reasons:[],savedKm:2.5,savedEuro:3})
 for (const mutate of [p=>p.plan.unserved.push({locationId:'Z',mandatory:true}),p=>p.plan.routes[0].trips.pop(),p=>p.dataset.fingerprint='other',p=>p.asOf='2026-08-13',p=>p.settings.costPerKmEuro=1,p=>p.settings.glassDensityKgM3=200,p=>p.routing.distanceSource='aerial']) {
  const c=plan();mutate(c);const result=compareScenarios(a,c);assert.equal(result.comparable,false);assert.equal(result.savedEuro,null);assert.equal(result.savedKm,null);assert.ok(result.reasons.length)
 }
 const unpriced=plan();delete unpriced.costs
 assert.equal(compareScenarios(unpriced,unpriced).savedEuro,null)
})

test('baseline is a separate snapshot, survives reload and clears immediately on context changes',()=>{
 const current=ref(plan()), context=ref('date-dataset'),s=createScenarioComparison(current,context)
 s.save();current.value.plan.totals.trucks=7
 assert.equal(s.baseline.value.plan.totals.trucks,1)
 current.value=null;assert.equal(s.baseline.value.plan.totals.trucks,1)
 current.value=plan();assert.ok(s.comparison.value)
 context.value='different-date';assert.equal(s.baseline.value,null)
 s.save();s.clear();assert.equal(s.baseline.value,null)
})

test('time-to-full sorts overdue first and retains explicit missing estimates',()=>{
 const rows=[{locationId:'B',material:'green',medianDaysUntilFull:null},{locationId:'C',material:'white',medianDaysUntilFull:2},{locationId:'A',material:'brown',medianDaysUntilFull:-3}]
 assert.deepEqual(timingRows(rows,'','').map(r=>r.locationId),['A','C','B'])
 assert.equal(timingRows(rows,' b ','green').length,1)
 assert.match(daysLabel(-3),/past estimate/);assert.equal(daysLabel(null),'Insufficient history');assert.equal(euro(null),'Not priced')
 assert.equal(rows[0].locationId,'B')
})

test('cost panel distinguishes unpriced and partial costs',async t=>{
 const Cost=await component('OperatingCosts')
 assert.match(mount(t,Cost).text(),/Enter your variable cost/)
 const costs={...plan().costs,partial:true}
 const m=mount(t,Cost,{costs})
 assert.match(m.text(),/Partial estimate/);assert.match(m.text(),/once per scheduled truck/);assert.match(m.text(),/165.00/)
})

test('timing table filters locations, paginates and resets the page',async t=>{
 const rows=Array.from({length:15},(_,i)=>({locationId:`A${i}`,material:i===0?'brown':'green',lastEmptied:'2026-01-01',historyCycles:2,censoredCycles:1,medianDaysUntilFull:i,earlyDaysUntilFull:i-1,lateDaysUntilFull:i+3,predictedFullDate:'2026-01-20',reason:null}))
 const m=mount(t,await component('FillTimingTable'),{rows})
 const buttons=()=>m.all().filter(n=>n.tag==='button')
 assert.equal(buttons()[0].props.disabled,true);buttons()[1].props.onClick();await nextTick();assert.match(m.text(),/13–15 of 15/)
 m.find('select').props.onChange({target:{value:'brown'}});await nextTick();assert.match(m.text(),/1–1 of 1/)
 assert.match(m.text(),/A0/);assert.equal(buttons()[0].props.disabled,true)
 m.find('input').props.onInput({target:{value:'no matching location'}});await nextTick();assert.match(m.text(),/No matching containers/);assert.match(m.text(),/0–0 of 0/)
})

test('scenario controls save and hide stale differences during edits',async t=>{
 let saves=0
 const C=await component('ScenarioComparison')
 const m=mount(t,C,{proposal:plan(),baseline:plan(),onSave:()=>saves++},undefined,{UiButton:Button})
 m.all().find(n=>n.tag==='button'&&n.text.includes('Save')).props.onClick();assert.equal(saves,1)
 assert.match(m.text(),/Matched completed service/)
 const dirty=mount(t,C,{proposal:plan(),baseline:plan(),dirty:true},undefined,{UiButton:Button})
 assert.doesNotMatch(dirty.text(),/Matched completed service/);assert.equal(dirty.find('button').props.disabled,true)
})

test('presentation navigates six actual-data slides, exports and closes by Escape cancel',async t=>{
 let closed=0,exports=0
 const Placeholder={render:()=>h('p',{},'Live data view')}
 const m=mount(t,await component('PlanPresentation'),{proposal:plan(),baseline:null,onClose:()=>closed++,onExport:()=>exports++},undefined,{UiButton:Button,FillTimingTable:Placeholder,OperatingCosts:Placeholder,ScenarioComparison:Placeholder,ProposalRouteMap:Placeholder})
 assert.match(m.text(),/The collection challenge/)
 const dialog=m.find('dialog')
 dialog.props.onKeydown({key:'ArrowRight',target:{tagName:'INPUT'},preventDefault(){}});await nextTick();assert.match(m.text(),/The collection challenge/)
 for(let i=0;i<8;i++){dialog.props.onKeydown({key:'ArrowRight',preventDefault(){}});await nextTick()}
 assert.match(m.text(),/Evidence and hand-off/);assert.match(m.text(),/source/)
 m.all().find(n=>n.tag==='button'&&n.text.includes('Download')).props.onClick();assert.equal(exports,1)
 dialog.props.onCancel({preventDefault(){}});assert.equal(closed,1)
 assert.equal(nextSlide(0,-1),0);assert.equal(nextSlide(5,1),5)
})
