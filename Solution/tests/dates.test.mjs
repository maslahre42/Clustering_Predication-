import test from 'node:test'
import assert from 'node:assert/strict'
import { isIsoDate } from '../apps/web/app/shared/domain/dates.ts'
test('date selection accepts strict ISO calendar dates including leap days', () => {
  for (const value of ['2026-03-01', '2024-02-29', '2026-12-31', '0001-01-01']) assert.equal(isIsoDate(value), true, value)
})
test('date selection rejects missing, malformed and normalized impossible dates', () => {
  for (const value of [null, undefined, '', '2026-02-29', '2026-02-30', '2026-04-31', '2026-13-01', '0000-01-01', '2026-1-01', '01/03/2026', '2026-03-01T00:00:00Z']) assert.equal(isIsoDate(value), false, String(value))
})
