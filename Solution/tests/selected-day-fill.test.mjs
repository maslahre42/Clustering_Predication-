import test from 'node:test'
import assert from 'node:assert/strict'
import { planningViewBins, planningFillLabel } from '../apps/web/app/features/planning/domain/fillView.ts'
import { createWorkspaceModel } from '../apps/web/app/features/workspace/model.ts'
import { component, mount, h, nextTick, ref } from './helpers/vue.mjs'
const bin=(id='A',material='white',date='2026-09-30',fill=100)=>({key:`${id}:${material}`,locationId:id,material,lastCollection:date,lastFillPercent:fill,lastIsOverfull:false,collections:4,name:id,latitude:49.14,longitude:9.22,isSynthetic:true})
const estimate=(date='2026-10-01',values=[])=>({asOf:date,semantics:'after-recorded-emptyings',lastObservationDate:'2026-09-30',note:'Estimates only.',bins:values})
const value=(id='A',material='white',fill=5,last='2026-09-30',status='estimated')=>({locationId:id,material,lastEmptied:last,daysSinceEmptied:1,expectedFillPercent:fill,lower:1,upper:10,status})

test('a recorded full bin shows post-emptying refill on 1 October while its history is preserved',()=>{
 const source={...bin(),lastIsOverfull:true,lastFillPercent:null},raw=structuredClone(source)
 const shown=planningViewBins([source],'2026-10-01','estimate',estimate('2026-10-01',[value()]))[0]
 assert.equal(shown.viewFillPercent,5);assert.equal(shown.viewIsOverfull,false);assert.equal(planningFillLabel(shown),'~5.0%')
 assert.equal(shown.lastIsOverfull,true);assert.deepEqual(source,raw)
 assert.equal(planningFillLabel(planningViewBins([source],'2026-10-01','recorded',null)[0]),'Overfull')
 const emptied=planningViewBins([bin()],'2026-09-30','estimate',estimate('2026-09-30',[{...value('A','white',0,'2026-09-30','emptied'),lower:0,upper:0}]))[0]
 assert.equal(planningFillLabel(emptied),'0% · emptied')
})

test('pending, failed, mismatched and unavailable estimates never fall back to the old full value',()=>{
 for(const [state,pending,error] of [[null,true,null],[estimate('2026-09-30',[value()]),false,null],[estimate('2026-10-01',[value()]),false,new Error('offline')],[estimate('2026-10-01',[value('A','white',3,'2026-09-29')]),false,null],[estimate('2026-10-01',[value('A','white',null,'2026-09-30','unknown')]),false,null]]){
  const row=planningViewBins([bin()],'2026-10-01','estimate',state,pending,error)[0]
  assert.equal(row.viewFillPercent,null);assert.ok(['Unknown','Estimating…'].includes(planningFillLabel(row)))
 }
 for(const invalid of [NaN,Infinity,-1,101])assert.equal(planningViewBins([bin()],'2026-10-01','estimate',estimate('2026-10-01',[value('A','white',invalid)]))[0].viewFillPercent,null)
 assert.equal(planningViewBins([bin()],'2026-10-01','estimate',estimate('2026-10-01',[value('A','white',0,'2026-09-30','emptied')]))[0].viewState,'unknown')
})
function workspace(){
 const asOf=ref('2026-10-01'),snapshot=ref({asOf:asOf.value,bins:[bin(),bin('A','brown','2026-09-01',90),bin('B','white','2026-09-30',null)]})
 const locations=ref(['A','B'].map(locationId=>({locationId,latitude:49.14,longitude:9.22,isSynthetic:true})))
 const fillState=ref(estimate(asOf.value,[value(),value('A','brown',95,'2026-09-01'),value('B','white',null,'2026-09-30','unknown')]))
 const error=ref(null),fillStateError=ref(null),fillStatePending=ref(false)
 return {model:createWorkspaceModel(asOf,{snapshot,locations,error,fillState,fillStatePending,fillStateError}),asOf,snapshot,fillState,fillStateError,fillStatePending}
}

test('filters and sorting follow the selected view, keep materials separate, and retain original export evidence',()=>{
 const {model:m}=workspace();assert.equal(m.filters.fillView.value,'estimate')
 m.filters.minimumFill.value=80;assert.deepEqual(m.filters.filteredBins.value.map(b=>b.key),['A:brown'])
 m.filters.fillView.value='recorded';assert.deepEqual(m.filters.filteredBins.value.map(b=>b.key),['A:white','A:brown'])
 m.filters.minimumFill.value=0;m.filters.fillView.value='estimate';m.filters.sort.value='fill'
 assert.deepEqual(m.filters.filteredClusters.value.map(c=>c.locationId),['A','B'])
 m.plan.toggleBin('A:white',true);assert.equal(m.plan.selectedBins.value[0].lastFillPercent,100)
 assert.equal(m.filters.viewBins.value.find(b=>b.key==='A:white').viewFillPercent,5)
})

test('date changes clear selection and never display a previous day estimate while new data arrives',()=>{
 const {model:m,asOf,snapshot,fillState}=workspace();m.plan.toggleBin('A:white',true)
 asOf.value='2026-10-02';assert.deepEqual(m.plan.selectedKeys.value,[]);assert.deepEqual(m.filters.viewBins.value,[])
 snapshot.value={...snapshot.value,asOf:asOf.value}
 assert.ok(m.filters.viewBins.value.every(b=>b.viewFillPercent===null))
 fillState.value=estimate('2026-10-02',[value('A','white',10)])
 assert.equal(m.filters.viewBins.value[0].viewFillPercent,10)
})

test('meter labels distinguish emptied, estimated, missing and recorded full states',async t=>{
 const Meter=await component('PlanningFillMeter'),Historical=await component('HistoricalFillMeter')
 const controls={HistoricalFillMeter:Historical,UiIcon:{render:()=>null}}
 const after=planningViewBins([bin()],'2026-10-01','estimate',estimate('2026-10-01',[value()]))[0]
 assert.match(mount(t,Meter,{bin:after,material:'white'},undefined,controls).text(),/~5.0%/)
 assert.match(mount(t,Meter,{bin:planningViewBins([bin()],'2026-10-01','recorded')[0],material:'white'},undefined,controls).text(),/100%/)
 const zero=planningViewBins([bin()],'2026-09-30','estimate',estimate('2026-09-30',[{...value('A','white',0,'2026-09-30','emptied'),lower:0,upper:0}]))[0]
 assert.match(mount(t,Meter,{bin:zero,material:'white'},undefined,controls).text(),/0% · emptied/)
 assert.match(mount(t,Meter,{material:'white'},undefined,controls).text(),/Unknown/)
})

test('actual view selector switches filtering and threshold labels together',async t=>{
 const {model:m}=workspace();globalThis.usePlanningFilters=()=>m.filters;t.after(()=>delete globalThis.usePlanningFilters)
 const Slider=await component('UiSlider')
 const shown=mount(t,await component('PlanningFilters'),{},undefined,{UiSelect:await component('UiSelect'),UiInput:await component('UiInput'),UiButton:await component('UiButton'),UiSlider:Slider,UiSegmentedControl:{render:()=>null},UiIcon:{render:()=>null}})
 assert.match(shown.text(),/Estimated fill ≥ 50%/);assert.equal(shown.all().find(n=>n.tag==='input'&&n.props.type==='range').props['aria-valuetext'],'50% estimated fill')
 m.filters.minimumFill.value=80
 shown.all().find(n=>n.tag==='select').props.onChange({target:{value:'recorded'}});await nextTick()
 assert.equal(m.filters.fillView.value,'recorded');assert.match(shown.text(),/Recorded fill ≥ 80%/);assert.equal(shown.all().find(n=>n.tag==='input'&&n.props.type==='range').props['aria-valuetext'],'80% recorded fill')
 assert.deepEqual(m.filters.filteredBins.value.map(b=>b.key),['A:white','A:brown'])
})


test('switching fill view resets location pagination so matching bins remain visible',async t=>{
 const filters={fillView:ref('estimate'),filteredClusters:ref(Array.from({length:25},(_,i)=>({locationId:`ID${i}`,bins:[]}))),search:ref(''),material:ref(''),minimumFill:ref(0),sort:ref('recent'),resetFilters(){}}
 globalThis.usePlanningFilters=()=>filters;t.after(()=>delete globalThis.usePlanningFilters)
 const Card={props:['cluster'],render(){return h('p',{},this.cluster.locationId)}}
 const Pagination={props:['modelValue','pages'],emits:['update:modelValue'],render(){return h('button',{onClick:()=>this.$emit('update:modelValue',this.modelValue+1)},'Next locations')}}
 const m=mount(t,await component('LocationClusterList'),{},undefined,{LocationClusterCard:Card,UiPagination:Pagination})
 assert.match(m.text(),/ID0/);m.find('button').props.onClick();await nextTick();assert.match(m.text(),/ID10/);assert.doesNotMatch(m.text(),/ID0 /)
 filters.fillView.value='recorded';await nextTick();assert.match(m.text(),/ID0/);assert.doesNotMatch(m.text(),/ID10/)
 assert.match(m.text(),/Recorded before collection/)
})


test('estimated fill starts at fifty, includes the boundary and reset restores the startup filters',()=>{
 const {model:m,fillState}=workspace()
 fillState.value=estimate('2026-10-01',[value('A','white',50),value('A','brown',49.9,'2026-09-01'),value('B','white',null,'2026-09-30','unknown')])
 assert.equal(m.filters.minimumFill.value,50)
 assert.deepEqual(m.filters.filteredBins.value.map(b=>b.key),['A:white'])
 m.filters.minimumFill.value=0;assert.equal(m.filters.filteredBins.value.length,3)
 m.filters.search.value='B';m.filters.material.value='white';m.filters.sort.value='fill';m.filters.resetFilters()
 assert.equal(m.filters.minimumFill.value,50);assert.equal(m.filters.search.value,'');assert.equal(m.filters.material.value,'');assert.equal(m.filters.sort.value,'recent')
 assert.deepEqual(m.filters.filteredBins.value.map(b=>b.key),['A:white'])
})

test('the default threshold shows estimate progress rather than a false empty result while loading',async t=>{
 const {model:m,fillStatePending}=workspace();fillStatePending.value=true
 globalThis.usePlanningFilters=()=>m.filters;t.after(()=>delete globalThis.usePlanningFilters)
 const State={props:['title'],render(){return h('p',{},this.title)}}
 const shown=mount(t,await component('LocationClusterList'),{},undefined,{WorkspaceState:State,LocationClusterCard:{render:()=>null},UiPagination:{render:()=>null}})
 assert.match(shown.text(),/Estimating fill after emptying/);assert.doesNotMatch(shown.text(),/No locations match/)
 m.filters.fillView.value='recorded';await nextTick();assert.doesNotMatch(shown.text(),/Estimating fill after emptying/)
})
