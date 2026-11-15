import test from 'node:test'
import assert from 'node:assert/strict'
import { createRequire } from 'node:module'
import { createProposalDataset } from '../apps/web/app/features/proposal/state/createProposalDataset.ts'
const require=createRequire(new URL('../apps/web/package.json',import.meta.url))
const {ref}=require('vue')

test('oversize and empty uploads leave the active dataset unchanged',async()=>{
  const selected=ref(null),state=createProposalDataset(selected)
  await state.load({name:'big.csv',size:2000001,text:async()=>{throw Error('must not read')}})
  assert.match(state.error.value,/2 MB/);assert.equal(selected.value,null)
  await state.load({name:'empty.csv',size:1,text:async()=>''})
  assert.match(state.error.value,/empty/);assert.equal(selected.value,null)
})

test('an older file read cannot replace a newer dataset or undo reset',async()=>{
  const selected=ref(null),state=createProposalDataset(selected)
  let resolve
  const old=state.load({name:'old.csv',size:10,text:()=>new Promise(r=>{resolve=r})})
  await state.load({name:'new.csv',size:10,text:async()=>'new data'})
  resolve('old data');await old
  assert.deepEqual(selected.value,{name:'new.csv',csv:'new data'})
  const pending=state.load({name:'old.csv',size:10,text:()=>new Promise(r=>{resolve=r})})
  state.clear();resolve('old data');await pending
  assert.equal(selected.value,null)
})

test('invalid file types and multiple-file drops preserve the active dataset',async()=>{
 const selected=ref({name:'active.csv',csv:'keep'}),state=createProposalDataset(selected)
 await state.load({name:'image.png',size:10,text:async()=>{throw Error('must not read')}})
 assert.match(state.error.value,/.csv extension/);assert.equal(selected.value.csv,'keep')
 await state.drop([{name:'a.csv'},{name:'b.csv'}]);assert.match(state.error.value,/one CSV/);assert.equal(selected.value.csv,'keep')
})
test('server validation completes before activating a file and metadata',async()=>{
 const selected=ref(null),metadata=ref(null);let finish
 const state=createProposalDataset(selected,{metadata,validate:()=>new Promise(r=>{finish=r})})
 const pending=state.load({name:'records.CSV',size:10,text:async()=>'rows'});await Promise.resolve()
 assert.equal(selected.value,null);assert.equal(state.reading.value,true)
 finish({rows:3});await pending
 assert.equal(selected.value.name,'records.CSV');assert.equal(metadata.value.rows,3);assert.equal(state.reading.value,false)
})
test('rejected records keep the prior selected file and its metadata',async()=>{
 const selected=ref({name:'active.csv',csv:'keep'}),metadata=ref({rows:4})
 const state=createProposalDataset(selected,{metadata,validate:async()=>{throw{data:{validation:{errors:[{row_number:2,message:'Invalid fill'}]}}}}})
 await state.load({name:'invalid.csv',size:10,text:async()=>'bad rows'})
 assert.equal(selected.value.name,'active.csv');assert.equal(metadata.value.rows,4)
 assert.equal(state.issues.value[0].row_number,2);assert.match(state.error.value,/rows below/)
})
test('superseded validation is aborted and cannot activate an old upload',async()=>{
 const selected=ref(null),metadata=ref(null);let oldComplete,oldSignal
 const state=createProposalDataset(selected,{metadata,validate:(csv,signal)=>csv==='old'?new Promise(r=>{oldComplete=r;oldSignal=signal}):Promise.resolve({rows:2})})
 const old=state.load({name:'old.csv',size:10,text:async()=>'old'});await Promise.resolve()
 await state.load({name:'new.csv',size:10,text:async()=>'new'});assert.equal(oldSignal.aborted,true)
 oldComplete({rows:1});await old
 assert.equal(selected.value.name,'new.csv');assert.equal(metadata.value.rows,2)
 state.clear();assert.equal(selected.value,null);assert.equal(metadata.value,null)
})
test('nested file drag events keep the highlight until the final leave or drop',async()=>{
 const state=createProposalDataset(ref(null))
 state.dragEnter(['text/plain']);assert.equal(state.dragging.value,false)
 state.dragEnter(['Files']);state.dragEnter(['Files']);state.dragLeave();assert.equal(state.dragging.value,true)
 state.dragLeave();assert.equal(state.dragging.value,false)
 state.dragEnter(['Files']);await state.drop([{name:'dragged.csv',size:10,text:async()=>'rows'}]);assert.equal(state.dragging.value,false)
})
test('leaving the import page cancels validation and does not change the active source',async()=>{
 const selected=ref(null);let complete,signal
 const state=createProposalDataset(selected,{validate:(csv,s)=>{signal=s;return new Promise(r=>{complete=r})}})
 const pending=state.load({name:'aborted.csv',size:10,text:async()=>'rows'});await Promise.resolve();state.dispose()
 complete({rows:3});await pending;assert.equal(signal.aborted,true);assert.equal(selected.value,null)
})
