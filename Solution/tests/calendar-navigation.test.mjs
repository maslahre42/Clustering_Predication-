import test from 'node:test'
import assert from 'node:assert/strict'
import { calendarCells, calendarInitialDate, shiftCalendarDate, shiftCalendarMonth, isCalendarDateAllowed } from '../apps/web/app/shared/domain/calendar.ts'
import { paginationItems } from '../apps/web/app/shared/domain/pagination.ts'

test('calendar uses a Monday-first six-week grid with correct leap-day and month boundaries', () => {
  const cells = calendarCells('2024-02')
  assert.equal(cells.length, 42)
  assert.equal(cells[0].date, '2024-01-29')
  assert.equal(cells.at(-1).date, '2024-03-10')
  assert.equal(cells.filter(cell => cell.inMonth).length, 29)
  assert.equal(cells.find(cell => cell.date === '2024-02-29').day, 29)
})
test('calendar disables dates strictly outside the inclusive database horizon', () => {
  const cells = calendarCells('2026-10', '2025-10-17', '2026-10-07', '2026-10-08')
  assert.equal(cells.find(cell => cell.date === '2026-10-07').disabled, false)
  const today = cells.find(cell => cell.date === '2026-10-08')
  assert.equal(today.today, true)
  assert.equal(today.disabled, true)
  assert.equal(isCalendarDateAllowed('2025-10-16', '2025-10-17', '2026-10-07'), false)
  assert.equal(isCalendarDateAllowed('2025-10-17', '2025-10-17', '2026-10-07'), true)
  assert.equal(isCalendarDateAllowed('2026-02-30'), false)
})
test('calendar keyboard and month movement cross years, leap days and DST without shifting service days', () => {
  assert.equal(shiftCalendarDate('2024-02-28', 1), '2024-02-29')
  assert.equal(shiftCalendarDate('2026-03-29', 1), '2026-03-30')
  assert.equal(shiftCalendarDate('2026-01-01', -1), '2025-12-31')
  assert.equal(shiftCalendarDate('2026-01-01', 7), '2026-01-08')
  assert.equal(shiftCalendarMonth('2026-01', -1), '2025-12')
  assert.equal(shiftCalendarMonth('2025-12', 1), '2026-01')
  assert.deepEqual(calendarCells('bad'), [])
  assert.throws(() => shiftCalendarDate('bad', 1))
})
test('pagination keeps boundaries, active neighbors and ellipses without allocating every page', () => {
  assert.deepEqual(paginationItems(1, 1), [1])
  assert.deepEqual(paginationItems(2, 4), [1, 2, 3, 4])
  assert.deepEqual(paginationItems(1, 1000), [1, 2, 3, 4, '…', 1000])
  assert.deepEqual(paginationItems(500, 1000), [1, '…', 499, 500, 501, '…', 1000])
  assert.deepEqual(paginationItems(1000, 1000), [1, '…', 997, 998, 999, 1000])
})

test('opening a calendar anchors to the chosen day or clamps today into the allowed data range', () => {
  assert.equal(calendarInitialDate('2026-05-12', '2025-10-17', '2026-10-07', '2026-11-14'), '2026-05-12')
  assert.equal(calendarInitialDate(undefined, '2025-10-17', '2026-10-07', '2026-11-14'), '2026-10-07')
  assert.equal(calendarInitialDate(undefined, '2025-10-17', '2026-10-07', '2025-01-01'), '2025-10-17')
  assert.equal(calendarInitialDate('bad', undefined, undefined, '2026-11-14'), '2026-11-14')
})
