import { computed, watch, type Ref } from 'vue'
import { isIsoDate } from '../../shared/domain/dates.ts'
import type { DatasetDateRange } from '../../shared/api/contracts/dataset'

export function createPlanningDate(asOf: Ref<string>, source: Readonly<Ref<DatasetDateRange | null | undefined>>) {
  const bounds = computed(() => {
    const range = source.value
    if (!range || !isIsoDate(range.firstDate) || !isIsoDate(range.lastDate) || !isIsoDate(range.maxPlanningDate) ||
        range.firstDate > range.lastDate || range.lastDate > range.maxPlanningDate) return null
    return { firstDate: range.firstDate, lastDate: range.lastDate, maxPlanningDate: range.maxPlanningDate }
  })
  function isAllowedDate(value: string | null | undefined): value is string {
    return !!bounds.value && isIsoDate(value) && value >= bounds.value.firstDate && value <= bounds.value.maxPlanningDate
  }
  function applyPlanningDate(value: string | null | undefined): boolean {
    if (!isAllowedDate(value)) return false
    asOf.value = value
    return true
  }
  watch(bounds, range => {
    // Open on the latest real observation when today's date is outside the available range.
    if (range && !isAllowedDate(asOf.value)) asOf.value = range.lastDate
  }, { immediate: true, flush: 'sync' })
  return { bounds, isAllowedDate, applyPlanningDate }
}
