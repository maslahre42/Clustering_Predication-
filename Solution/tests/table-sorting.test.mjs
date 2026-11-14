import test from 'node:test'
import assert from 'node:assert/strict'
import { sortTableRows } from '../apps/web/app/shared/domain/table.ts'

test('numeric table sorting uses numeric order and preserves the source', () => {
  const rows = [{ n: 100 }, { n: 9 }, { n: 20 }]
  assert.deepEqual(sortTableRows(rows, row => row.n, 'asc').map(row => row.n), [9, 20, 100])
  assert.deepEqual(sortTableRows(rows, row => row.n, 'desc').map(row => row.n), [100, 20, 9])
  assert.deepEqual(rows.map(row => row.n), [100, 9, 20])
})
test('missing statistics stay last in both directions and ties are stable', () => {
  const rows = [{ id: 'missing', n: null }, { id: 'a', n: 0 }, { id: 'b', n: 0 }, { id: 'c', n: 50 }]
  assert.deepEqual(sortTableRows(rows, row => row.n, 'asc').map(row => row.id), ['a', 'b', 'c', 'missing'])
  assert.deepEqual(sortTableRows(rows, row => row.n, 'desc').map(row => row.id), ['c', 'a', 'b', 'missing'])
})
test('ISO months sort chronologically before slicing a page', () => {
  const rows = ['2026-01', '2025-12', '2026-02']
  assert.deepEqual(sortTableRows(rows, row => row, 'desc').slice(0, 2), ['2026-02', '2026-01'])
  assert.deepEqual(sortTableRows([], row => row, 'asc'), [])
})
