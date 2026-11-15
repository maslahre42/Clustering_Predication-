import { computed, ref, watch, type Ref } from 'vue'
import type { ProposalDataset } from '../../shared/api/contracts/comparison'
import type { Location } from '../../shared/api/contracts/locations'
import type { SelectedDayFill, PlanningSnapshot } from '../../shared/api/contracts/planning'
import { DEFAULT_WORKSPACE, type WorkspaceConfiguration } from '../../shared/config/workspace.ts'
import { knownBins, clusterBins } from '../inventory/domain/catalog.ts'
import { createPlanningFilters } from '../planning/state/createPlanningFilters.ts'
import { createCollectionPlan } from '../manifest/state/createCollectionPlan.ts'

export type WorkspaceView = 'planning' | 'history' | 'forecasts' | 'manifest' | 'status' | 'details' | 'analytics'
export interface WorkspaceSources {
  snapshot: Ref<PlanningSnapshot | null | undefined>
  locations: Ref<Location[] | null | undefined>
  analysisDataset?: Readonly<Ref<ProposalDataset | null | undefined>>
  fillState?: Readonly<Ref<SelectedDayFill | null | undefined>>
  fillStatePending?: Readonly<Ref<boolean>>
  fillStateError?: Readonly<Ref<unknown>>
  error: Readonly<Ref<unknown>>
}

/** Compose request-local feature models; HTTP and browser effects belong to adapters. */
export function createWorkspaceModel(asOf: Ref<string>, sources: WorkspaceSources, configuration: WorkspaceConfiguration = DEFAULT_WORKSPACE) {
  const ready = computed(() => !sources.error.value && sources.snapshot.value?.asOf === asOf.value)
  const bins = computed(() => ready.value ? knownBins(sources.snapshot.value, sources.locations.value ?? [], asOf.value) : [])
  const clusters = computed(() => clusterBins(bins.value))
  const filters = createPlanningFilters(bins, {asOf,fillState:sources.fillState,fillStatePending:sources.fillStatePending,fillStateError:sources.fillStateError})
  const plan = createCollectionPlan({ asOf, bins, filteredBins: filters.filteredBins, ready }, configuration)
  const mapLocations = computed(() => filters.filteredClusters.value.map(({ bins: _bins, ...location }) => location))
  const view = ref<WorkspaceView>('planning')
  const inspectedLocation = ref('')
  function inspect(id: string) {
    if (clusters.value.some(cluster => cluster.locationId === id)) {
      inspectedLocation.value = id
      view.value = 'details'
    }
  }
  if (sources.analysisDataset) watch(sources.analysisDataset, () => plan.clearPlan(), { flush: 'sync' })
  watch(asOf, () => { plan.clearPlan(); inspectedLocation.value = '' }, { flush: 'sync' })
  return { asOf, data: { ready, bins, clusters, mapLocations }, filters, plan, navigation: { view, inspectedLocation, inspect } }
}
