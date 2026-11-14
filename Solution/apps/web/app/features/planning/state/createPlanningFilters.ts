import { computed, ref, type ComputedRef } from 'vue'
import type { PlanningBin } from '../../inventory/types'
import { clusterBins } from '../../inventory/domain/catalog.ts'
import { matchesHistoricalFill, historicalFillRank } from '../../../shared/domain/fill.ts'

export function createPlanningFilters(bins: ComputedRef<PlanningBin[]>) {
  const search = ref('')
  const material = ref('')
  const minimumFill = ref(0)
  const sort = ref('recent')
  const filteredBins = computed(() => bins.value.filter(bin =>
    (!material.value || bin.material === material.value) &&
    bin.locationId.toLowerCase().includes(search.value.trim().toLowerCase()) &&
    matchesHistoricalFill(bin, minimumFill.value)))

  const filteredClusters = computed(() => clusterBins(filteredBins.value).sort((a, b) => {
    const value = sort.value === 'fill'
      ? Math.max(...b.bins.map(historicalFillRank)) - Math.max(...a.bins.map(historicalFillRank))
      : b.bins.map(bin => bin.lastCollection).sort().at(-1)!.localeCompare(a.bins.map(bin => bin.lastCollection).sort().at(-1)!)
    return value || a.locationId.localeCompare(b.locationId)
  }))

  function resetFilters() {
    search.value = ''
    material.value = ''
    minimumFill.value = 0
    sort.value = 'recent'
  }
  return { search, material, minimumFill, sort, filteredBins, filteredClusters, resetFilters }
}
