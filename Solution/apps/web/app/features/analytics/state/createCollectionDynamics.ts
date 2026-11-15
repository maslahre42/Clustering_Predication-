import { computed, ref, type Ref } from 'vue'
import type { MaterialDynamics } from '../../../shared/api/contracts/analytics'

export function createCollectionDynamics(data: Ref<MaterialDynamics[]>) {
  const material = ref('brown'), ranking = ref('fastest')
  const selected = computed(() => data.value.find(row => row.material === material.value))
  const rows = computed(() => selected.value ? ranking.value === 'fastest' ? selected.value.fastestBins : selected.value.slowestBins : [])
  const charts = computed(() => [
    { title: 'Days between collections', unit: 'days', distribution: selected.value?.cadence },
    { title: 'Filling speed between emptyings', unit: 'pp/day', distribution: selected.value?.rates },
  ].map(chart => ({ ...chart, bars: chart.distribution?.buckets.map(bucket => ({ ...bucket, height: bucket.count / Math.max(1,...chart.distribution!.buckets.map(row => row.count)) * 100 })) ?? [] })))
  const curve = computed(() => selected.value?.fillingCurve.map(point => `${45+point.days/90*600},${220-point.share*180}`).join(' ') ?? '')
  const within28 = computed(() => selected.value?.fillingCurve.find(point => point.days === 28))
  return { material, ranking, selected, rows, charts, curve, within28 }
}
