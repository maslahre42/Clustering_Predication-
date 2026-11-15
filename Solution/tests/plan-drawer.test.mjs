import test from 'node:test'
import assert from 'node:assert/strict'
import { ref } from './helpers/vue.mjs'
import { createPlanDrawerState } from '../apps/web/app/features/planning/state/createPlanDrawerState.ts'

test('an empty plan starts collapsed and an existing plan starts expanded',()=>{
 assert.equal(createPlanDrawerState(ref(0)).collapsed.value,true)
 assert.equal(createPlanDrawerState(ref(2)).collapsed.value,false)
})

test('adding the first stop opens the drawer and removing the final stop collapses it',()=>{
 const stops=ref(0),drawer=createPlanDrawerState(stops)
 stops.value=1;assert.equal(drawer.collapsed.value,false)
 stops.value=3;stops.value=0;assert.equal(drawer.collapsed.value,true)
 stops.value=1;assert.equal(drawer.collapsed.value,false)
})

test('manual toggles remain available and populated edits preserve the chosen collapsed state',()=>{
 const stops=ref(0),drawer=createPlanDrawerState(stops)
 drawer.toggle();assert.equal(drawer.collapsed.value,false)
 drawer.toggle();assert.equal(drawer.collapsed.value,true)
 stops.value=1;drawer.toggle();assert.equal(drawer.collapsed.value,true)
 stops.value=2;assert.equal(drawer.collapsed.value,true)
 drawer.toggle();stops.value=1;assert.equal(drawer.collapsed.value,false)
 stops.value=0;assert.equal(drawer.collapsed.value,true)
})
