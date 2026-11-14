import { computed, toValue, type MaybeRefOrGetter } from 'vue'
import type { CollectionAnalytics } from '~/shared/api/contracts/analytics'
import { API_ROUTES } from '~/shared/api/routes'

export function useHistoricalAnalytics(asOf: MaybeRefOrGetter<string>) {
  const query = computed(() => ({ asOf: toValue(asOf) }))
  const request = useFetch<CollectionAnalytics>(API_ROUTES.analytics, { query })
  const ready = computed(() => !request.error.value && request.data.value?.asOf === toValue(asOf))
  return { ...request, ready }
}
