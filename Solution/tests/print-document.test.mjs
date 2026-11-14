import test from 'node:test'
import assert from 'node:assert/strict'
import { printDatedDocument } from '../apps/web/app/shared/browser/print.ts'

test('printing records the actual generation time and waits for it to render', async () => {
  const calls = []
  await printDatedDocument({
    setTimestamp: value => calls.push(value),
    afterRender: async () => { calls.push('rendered') },
    print: () => calls.push('printed'),
  }, () => new Date('2026-11-14T12:34:56Z'))
  assert.deepEqual(calls, ['2026-11-14T12:34:56.000Z', 'rendered', 'printed'])
})

test('render failure prevents printing a document with stale metadata', async () => {
  let printed = false
  await assert.rejects(printDatedDocument({
    setTimestamp: () => {},
    afterRender: async () => { throw new Error('render failed') },
    print: () => { printed = true },
  }), /render failed/)
  assert.equal(printed, false)
})
