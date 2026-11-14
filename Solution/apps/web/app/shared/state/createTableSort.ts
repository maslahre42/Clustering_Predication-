import { computed, ref } from 'vue'
import type { TableSortDirection } from '../domain/table'

/** One state update keeps field and direction consistent for reactive requests. */
export function createTableSort<Field extends string>(initialField: Field, initialDirection: TableSortDirection = 'asc') {
  const state = ref<{ field: Field; direction: TableSortDirection }>({ field: initialField, direction: initialDirection })
  const sortBy = computed(() => state.value.field)
  const sortDirection = computed(() => state.value.direction)

  function sort(field: Field) {
    state.value = {
      field,
      direction: state.value.field === field && state.value.direction === 'asc' ? 'desc' : 'asc',
    }
  }

  function resetSort() {
    state.value = { field: initialField, direction: initialDirection }
  }

  return { sortBy, sortDirection, sort, resetSort }
}
