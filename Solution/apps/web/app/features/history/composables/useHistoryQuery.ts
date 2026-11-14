import { computed, toValue, type MaybeRefOrGetter } from 'vue'
import type { HistoryPage } from '~/shared/api/contracts/history'
import { API_ROUTES } from '~/shared/api/routes'
import { createHistoryFilters } from '../state/createHistoryFilters'

export function useHistoryQuery(asOf: MaybeRefOrGetter<string>, initialLocationId: MaybeRefOrGetter<string | undefined>) {
  const filters = createHistoryFilters(computed(() => toValue(asOf)), computed(() => toValue(initialLocationId)))
  const request = useFetch<HistoryPage>(API_ROUTES.history, { query: filters.query })
  return { ...filters, request }
}

export function useLocationHistory(locationId: MaybeRefOrGetter<string>, asOf: MaybeRefOrGetter<string>) {
  const query = computed(() => ({ locationId: toValue(locationId), asOf: toValue(asOf), pageSize: 200 }))
  return useFetch<HistoryPage>(API_ROUTES.history, { query })
}
