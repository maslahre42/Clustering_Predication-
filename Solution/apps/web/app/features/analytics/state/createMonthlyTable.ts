import { computed, ref, watch, type Ref } from 'vue'
import type { MonthlyAnalytics } from '../../../shared/api/contracts/analytics'
import type { MonthlyColumn } from '../config/tableColumns'
import { sortTableRows } from '../../../shared/domain/table.ts'
import { createTableSort } from '../../../shared/state/createTableSort.ts'

export const MONTHLY_PAGE_SIZE = 12

export function createMonthlyTable(months: Readonly<Ref<MonthlyAnalytics[]>>) {
  const material = ref<string | null>()
  const page = ref(1)
  const sorting = createTableSort<MonthlyColumn>('month', 'desc')
  const filtered = computed(() => months.value.filter(row => !material.value || row.material === material.value))
  const sorted = computed(() => sortTableRows(filtered.value, row => row[sorting.sortBy.value], sorting.sortDirection.value))
  const rows = computed(() => sorted.value.slice((page.value - 1) * MONTHLY_PAGE_SIZE, page.value * MONTHLY_PAGE_SIZE))
  const pages = computed(() => Math.max(1, Math.ceil(filtered.value.length / MONTHLY_PAGE_SIZE)))

  watch([material, sorting.sortBy, sorting.sortDirection, months], () => { page.value = 1 }, { flush: 'sync' })

  return { material, page, pages, rows, ...sorting }
}
