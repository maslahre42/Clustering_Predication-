import test from 'node:test'
import assert from 'node:assert/strict'
import { historicalFillState, historicalFillLabel } from '../apps/web/app/shared/domain/fill.ts'

test('recorded fill bands include exact boundaries and distinguish exactly full', () => {
  for (const value of [0, 30, 69, 69.99]) assert.equal(historicalFillState(value), 'low')
  for (const value of [70, 95, 99, 99.99]) assert.equal(historicalFillState(value), 'high')
  assert.equal(historicalFillState(100), 'full')
})

test('missing or invalid readings are unknown, never an empty-bin state', () => {
  for (const value of [null, undefined, NaN, Infinity, -1, 101]) {
    assert.equal(historicalFillState(value), 'unknown')
  }
  assert.equal(historicalFillState(0), 'low')
  assert.equal(historicalFillLabel(null), 'Unknown')
})

test('explicit overflow stays separate from numeric fill and has precedence', () => {
  for (const value of [null, undefined, 0, 70, 100]) {
    assert.equal(historicalFillState(value, true), 'overfull')
    assert.equal(historicalFillLabel(value, true), 'Overfull')
  }
  assert.notEqual(historicalFillState(100), historicalFillState(null, true))
})
