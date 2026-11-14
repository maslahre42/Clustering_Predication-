import type { HistorySortField } from '../../../shared/api/contracts/history'
import { HISTORY_PAGE_SIZE } from '../../../shared/api/contracts/history.ts'
import { createTableSort } from '../../../shared/state/createTableSort.ts'
import { computed, ref, watch, type Ref } from 'vue'

export function createHistoryFilters(asOf: Readonly<Ref<string>>, initialLocationId: Readonly<Ref<string | undefined>>) {
  const material = ref<string | null>()
  const from = ref<string | null>()
  const to = ref<string | null>(asOf.value)
  const selected = ref(initialLocationId.value ?? '')
  const page = ref(1)
  const locationSearch = ref('')
  const { sortBy, sortDirection, sort, resetSort } = createTableSort<HistorySortField>('date', 'desc')
  const query = computed(() => ({
    material: material.value || undefined,
    from: from.value || undefined,
    to: to.value || undefined,
    asOf: asOf.value,
    locationId: selected.value || undefined,
    page: page.value,
    pageSize: HISTORY_PAGE_SIZE,
    locationSearch: locationSearch.value.trim() || undefined,
    sortBy: sortBy.value,
    sortDirection: sortDirection.value,
  }))
  watch([material, from, to, selected, locationSearch, sortBy, sortDirection], () => { page.value = 1 }, { flush: 'sync' })
  function reset() {
    material.value = null
    from.value = null
    to.value = asOf.value
    selected.value = initialLocationId.value ?? ''
    locationSearch.value = ''
    resetSort()
    page.value = 1
  }
  watch([asOf, initialLocationId], reset, { flush: 'sync' })
  return { material, from, to, selected, page, locationSearch, sortBy, sortDirection, sort, query, reset }
}
