import type { SelectedDayFill } from '../../../shared/api/contracts/planning'
import { planningViewBins, type PlanningFillView } from '../domain/fillView.ts'
import { computed, ref, type ComputedRef, type Ref } from 'vue'
import type { PlanningBin } from '../../inventory/types'
import { clusterBins } from '../../inventory/domain/catalog.ts'
import { matchesHistoricalFill, historicalFillRank } from '../../../shared/domain/fill.ts'

interface FillSources {
  asOf?: Readonly<Ref<string>>; fillState?: Readonly<Ref<SelectedDayFill | null | undefined>>
  fillStatePending?: Readonly<Ref<boolean>>; fillStateError?: Readonly<Ref<unknown>>
}
export function createPlanningFilters(bins: ComputedRef<PlanningBin[]>, sources: FillSources = {}) {
  const fillView = ref<PlanningFillView>(sources.fillState ? 'estimate' : 'recorded')
  const viewBins = computed(() => planningViewBins(bins.value,sources.asOf?.value ?? '',fillView.value,
    sources.fillState?.value,sources.fillStatePending?.value,sources.fillStateError?.value))
  const viewClusters = computed(() => clusterBins(viewBins.value))
  const fillStatePending = computed(() => !!sources.fillStatePending?.value)
  const fillStateError = computed(() => sources.fillStateError?.value)
  const lastObservationDate = computed(() => sources.fillState?.value?.asOf === sources.asOf?.value ? sources.fillState?.value?.lastObservationDate : null)

  const defaultMinimumFill = sources.fillState ? 50 : 0
  const search = ref('')
  const material = ref('')
  const minimumFill = ref(defaultMinimumFill)
  const sort = ref('recent')
  const filteredBins = computed(() => viewBins.value.filter(bin =>
    (!material.value || bin.material === material.value) &&
    bin.locationId.toLowerCase().includes(search.value.trim().toLowerCase()) &&
    matchesHistoricalFill({lastFillPercent:bin.viewFillPercent,lastIsOverfull:bin.viewIsOverfull}, minimumFill.value)))

  const filteredClusters = computed(() => clusterBins(filteredBins.value).sort((a, b) => {
    const value = sort.value === 'fill'
      ? Math.max(...b.bins.map(bin => historicalFillRank({lastFillPercent:bin.viewFillPercent,lastIsOverfull:bin.viewIsOverfull}))) - Math.max(...a.bins.map(bin => historicalFillRank({lastFillPercent:bin.viewFillPercent,lastIsOverfull:bin.viewIsOverfull})))
      : b.bins.map(bin => bin.lastCollection).sort().at(-1)!.localeCompare(a.bins.map(bin => bin.lastCollection).sort().at(-1)!)
    return value || a.locationId.localeCompare(b.locationId)
  }))

  function resetFilters() {
    search.value = ''
    material.value = ''
    minimumFill.value = defaultMinimumFill
    sort.value = 'recent'
  }
  return { fillView, viewBins, viewClusters, fillStatePending, fillStateError, lastObservationDate, search, material, minimumFill, sort, filteredBins, filteredClusters, resetFilters }
}
