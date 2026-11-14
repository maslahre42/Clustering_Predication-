import { computed, ref, type Ref } from 'vue'
import type { MaterialAnalytics } from '../../../shared/api/contracts/analytics'
import type { MaterialColumn } from '../config/tableColumns'
import { sortTableRows } from '../../../shared/domain/table.ts'
import { createTableSort } from '../../../shared/state/createTableSort.ts'

export function createMaterialTable(materials: Readonly<Ref<MaterialAnalytics[]>>) {
  const material = ref<string | null>()
  const sorting = createTableSort<MaterialColumn>('material')
  const rows = computed(() => sortTableRows(
    materials.value.filter(row => !material.value || row.material === material.value),
    row => sorting.sortBy.value === 'low' ? row.distribution.low0To30 : row[sorting.sortBy.value],
    sorting.sortDirection.value,
  ))

  return { material, rows, ...sorting }
}
