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
