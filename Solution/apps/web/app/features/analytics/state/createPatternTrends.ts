import { computed, ref, type Ref } from 'vue'
import type { MonthlyAnalytics } from '../../../shared/api/contracts/analytics'
import { monthlyTrend } from '../domain/patterns.ts'

export function createPatternTrends(months: Readonly<Ref<MonthlyAnalytics[]>>, asOf: Readonly<Ref<string>>, firstDate: Readonly<Ref<string | null | undefined>>) {
  const material = ref('brown')
  const metric = ref('fill')
  const rows = computed(() => {
    const source = monthlyTrend(months.value, material.value, asOf.value, firstDate.value)
    const maximum = metric.value === 'collections' ? Math.max(1, ...source.map(row => row.collections)) : 100
    return source.map(row => {
      const value = metric.value === 'collections' ? row.collections : row.meanNumericFill
      return { ...row, value, width: value == null ? 0 : value / maximum * 100 }
    })
  })
  return { material, metric, rows }
}
