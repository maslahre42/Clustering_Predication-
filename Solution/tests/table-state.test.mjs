import test from 'node:test'
import assert from 'node:assert/strict'
import { createRequire } from 'node:module'
import { createTableSort } from '../apps/web/app/shared/state/createTableSort.ts'
import { createMonthlyTable } from '../apps/web/app/features/analytics/state/createMonthlyTable.ts'
import { createMaterialTable } from '../apps/web/app/features/analytics/state/createMaterialTable.ts'

const require = createRequire(new URL('../apps/web/package.json', import.meta.url))
const { ref, effectScope, watch } = require('vue')

function fixture(t, create) {
  const scope = effectScope()
  t.after(() => scope.stop())
  return scope.run(create)
}

test('sort changes publish field and direction together and reset to the configured default', t => {
  fixture(t, () => {
    const sorting = createTableSort('date', 'desc')
    const updates = []
    watch([sorting.sortBy, sorting.sortDirection], ([field, direction]) => updates.push([field, direction]), { flush: 'sync' })
    sorting.sort('material')
    assert.deepEqual(updates, [['material', 'asc']])
    sorting.sort('material')
    assert.equal(sorting.sortDirection.value, 'desc')
    sorting.resetSort()
    assert.equal(sorting.sortBy.value, 'date')
    assert.equal(sorting.sortDirection.value, 'desc')
  })
})

test('monthly model filters and sorts before paging and resets when the data changes', t => {
  fixture(t, () => {
    const months = ref(Array.from({ length: 25 }, (_, n) => ({
      month: `${2024 + Math.floor(n / 12)}-${String(n % 12 + 1).padStart(2, '0')}`,
      material: n % 2 ? 'green' : 'brown', collections: n + 1,
      overfullCount: 0, numericReadings: 1, meanNumericFill: n,
    })))
    const table = createMonthlyTable(months)
    assert.equal(table.pages.value, 3)
    assert.equal(table.rows.value[0].collections, 25)
    table.page.value = 3
    table.sort('collections')
    assert.equal(table.page.value, 1)
    assert.equal(table.rows.value[0].collections, 1)
    table.page.value = 2
    table.material.value = 'green'
    assert.equal(table.page.value, 1)
    assert.equal(table.pages.value, 1)
    assert.equal(table.rows.value.length, 12)
    months.value = []
    assert.equal(table.pages.value, 1)
    assert.deepEqual(table.rows.value, [])
  })
})

test('material model sorts nested low-fill counts and preserves unknown statistics', t => {
  fixture(t, () => {
    const materials = ref([
      { material: 'brown', meanNumericFill: null, distribution: { low0To30: 3 } },
      { material: 'green', meanNumericFill: 0, distribution: { low0To30: 1 } },
    ])
    const table = createMaterialTable(materials)
    table.sort('low')
    assert.deepEqual(table.rows.value.map(row => row.material), ['green', 'brown'])
    table.sort('meanNumericFill'); table.sort('meanNumericFill')
    assert.deepEqual(table.rows.value.map(row => row.material), ['green', 'brown'])
    table.material.value = 'brown'
    assert.equal(table.rows.value[0].meanNumericFill, null)
    table.material.value = 'white'
    assert.deepEqual(table.rows.value, [])
  })
})
