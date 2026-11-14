import test from 'node:test'
import assert from 'node:assert/strict'
import { spawnSync } from 'node:child_process'
import { isoDateToLocalDate, localDateToIsoDate } from '../apps/web/app/shared/domain/dates.ts'

test('calendar conversion preserves service-day fields, leap days and early years', () => {
  for (const day of ['0001-01-01', '0099-12-31', '2024-02-29', '2026-09-30', '2026-10-07', '9999-12-31']) {
    const date = isoDateToLocalDate(day)
    assert.equal(date.getFullYear(), Number(day.slice(0, 4)))
    assert.equal(date.getMonth() + 1, Number(day.slice(5, 7)))
    assert.equal(date.getDate(), Number(day.slice(8, 10)))
    assert.equal(localDateToIsoDate(date), day)
  }
})

test('empty, malformed and invalid calendar values never create a cutoff', () => {
  for (const day of [null, undefined, '', 'bad', '2026-02-30', '0000-01-01']) {
    assert.equal(isoDateToLocalDate(day), undefined)
  }
  for (const date of [null, undefined, new Date(NaN)]) {
    assert.equal(localDateToIsoDate(date), undefined)
  }
})

for (const timezone of ['Europe/Berlin', 'America/Los_Angeles', 'Pacific/Auckland']) {
  test(`calendar selection keeps the same day across DST in ${timezone}`, () => {
    const moduleUrl = new URL('../apps/web/app/shared/domain/dates.ts', import.meta.url).href
    const script = `
      import assert from 'node:assert/strict';
      import { isoDateToLocalDate, localDateToIsoDate } from ${JSON.stringify(moduleUrl)};
      for (const day of ['2026-03-08', '2026-03-29', '2026-04-05', '2026-09-27', '2026-10-25', '2026-11-01']) {
        assert.equal(localDateToIsoDate(isoDateToLocalDate(day)), day);
        const [year, month, date] = day.split('-').map(Number);
        assert.equal(localDateToIsoDate(new Date(year, month - 1, date)), day);
      }
    `
    const result = spawnSync(process.execPath, ['--experimental-strip-types', '--input-type=module', '-e', script], {
      env: { ...process.env, TZ: timezone }, encoding: 'utf8', timeout: 10000,
    })
    assert.equal(result.status, 0, result.stderr)
  })
}
