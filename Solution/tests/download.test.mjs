import test from 'node:test'
import assert from 'node:assert/strict'
import { downloadCsv } from '../apps/web/app/shared/browser/download.ts'
test('CSV browser adapter assigns the filename and releases its temporary URL', t => {
  const previous = Object.getOwnPropertyDescriptor(globalThis, 'document')
  const anchor = { click() { this.clicked = true } }
  Object.defineProperty(globalThis, 'document', { configurable: true, value: { createElement: () => anchor } })
  t.after(() => previous ? Object.defineProperty(globalThis, 'document', previous) : delete globalThis.document)
  let cleanup, revoked, payload
  t.mock.method(URL, 'createObjectURL', blob => { payload = blob; return 'blob:plan' })
  t.mock.method(URL, 'revokeObjectURL', url => { revoked = url })
  t.mock.method(globalThis, 'setTimeout', callback => { cleanup = callback; return 0 })
  downloadCsv('a,b', 'plan.csv')
  assert.equal(payload.type, 'text/csv;charset=utf-8;')
  assert.equal(anchor.href, 'blob:plan'); assert.equal(anchor.download, 'plan.csv'); assert.equal(anchor.clicked, true)
  cleanup(); assert.equal(revoked, 'blob:plan')
})
