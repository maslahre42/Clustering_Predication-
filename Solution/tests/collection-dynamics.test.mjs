import test from 'node:test'
import assert from 'node:assert/strict'
import { ref,nextTick,component,mount,h } from './helpers/vue.mjs'
import { createCollectionDynamics } from '../apps/web/app/features/analytics/state/createCollectionDynamics.ts'
const distribution={count:3,minimum:10,q1:15,median:20,q3:25,maximum:30,buckets:[{lower:0,upper:15,count:1},{lower:15,upper:30,count:2,isTail:true}]}
const bin=id=>({locationId:id,material:'brown',collections:4,intervals:3,numericCycles:3,lowerBoundCycles:0,unknownCycles:0,zeroFillCycles:0,medianIntervalDays:20,medianRatePercentPerDay:2,medianDaysToFull:50})
const row=(material='brown')=>({material,collections:4,bins:1,intervals:3,numericCycles:3,lowerBoundCycles:0,unknownCycles:0,zeroFillCycles:0,cadence:distribution,rates:distribution,fillingTimes:distribution,fillingCurve:[{days:0,cycles:0,share:0},{days:28,cycles:1,share:1/3},{days:90,cycles:3,share:1}],fastestBins:[bin('FAST')],slowestBins:[bin('SLOW')]})

test('dynamics controls update material, ranking, chart scale and data without mutation',()=>{
 const original=[row(),{...row('white'),fastestBins:[bin('WHITE')]}],data=ref(original),s=createCollectionDynamics(data)
 assert.equal(s.charts.value[0].bars[1].height,100);assert.equal(s.charts.value[0].bars[0].height,50)
 assert.equal(s.rows.value[0].locationId,'FAST');s.ranking.value='slowest';assert.equal(s.rows.value[0].locationId,'SLOW')
 s.material.value='white';s.ranking.value='fastest';assert.equal(s.rows.value[0].locationId,'WHITE')
 data.value=[];assert.equal(s.selected.value,undefined);assert.deepEqual(s.rows.value,[]);assert.equal(s.curve.value,'')
 assert.equal(original.length,2)
})

test('dynamics panel distinguishes collections and cycles, labels projections and opens ranked locations',async t=>{
 const opened=[],m=mount(t,await component('CollectionDynamicsPanel'),{dynamics:[row(),{...row('white'),fastestBins:[bin('WHITE')]}],onInspect:id=>opened.push(id)},undefined,{
 UiCard:{render(){return h('section',{},this.$slots.default())}},UiSelect:await component('UiSelect'),UiTable:await component('UiTable'),UiButton:await component('UiButton')})
 assert.match(m.text(),/>15.0/); assert.match(m.text(),/4 recorded collections/);assert.match(m.text(),/3 intervals/);assert.match(m.text(),/33.3%/)
 assert.match(m.text(),/not an assumed collection schedule/);assert.match(m.text(),/lower bounds/)
 const selects=m.all().filter(n=>n.tag==='select');selects[1].props.onChange({target:{value:'slowest'}});await nextTick()
 assert.match(m.text(),/SLOW/);m.all().find(n=>n.tag==='button').props.onClick();assert.deepEqual(opened,['SLOW'])
 selects[0].props.onChange({target:{value:'white'}});selects[1].props.onChange({target:{value:'fastest'}});await nextTick()
 assert.match(m.text(),/WHITE/);assert.match(m.find('svg').props['aria-label'],/^white/)
})

test('empty and zero-rate evidence never invent filling-time estimates',async t=>{
 const zero={...row(),collections:1,intervals:0,cadence:null,rates:null,fillingTimes:null,fastestBins:[],slowestBins:[]}
 const m=mount(t,await component('CollectionDynamicsPanel'),{dynamics:[zero]},undefined,{UiCard:{render(){return h('section',{},this.$slots.default())}},UiSelect:await component('UiSelect'),UiTable:await component('UiTable')})
 assert.match(m.text(),/No positive ordinary cycles/);assert.equal(m.find('svg'),undefined)
 assert.doesNotMatch(m.text(),/NaN|Infinity/)
})
