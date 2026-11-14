import { computed, inject, provide, type InjectionKey } from 'vue'
import { createPlanningDate } from '~/features/workspace/planningDate'
import type { DatasetDateRange } from '~/shared/api/contracts/dataset'
import type { Location } from '~/shared/api/contracts/locations'
import type { PlanningSnapshot } from '~/shared/api/contracts/planning'
import { API_ROUTES } from '~/shared/api/routes'
import { planCsv } from '~/features/manifest/domain/planExport'
import { createWorkspaceModel } from '~/features/workspace/model'
import { downloadCsv } from '~/shared/browser/download'

/** The workspace Nuxt adapter and request-local provider. Feature models never fetch data. */
export function createCollectionWorkspace() {
  const asOf = useState('planning-cutoff', () => new Date().toISOString().slice(0, 10))
  const dateRangeRequest = useFetch<DatasetDateRange>(API_ROUTES['data-range'])
  const query = computed(() => ({ asOf: asOf.value }))
  const snapshotRequest = useFetch<PlanningSnapshot>(API_ROUTES.planning, { query })
  const locationRequest = useFetch<Location[]>(API_ROUTES.locations)
  const healthRequest = useFetch<{ status: string }>(API_ROUTES.health)
  const error = computed(() => snapshotRequest.error.value || locationRequest.error.value)
  const loading = computed(() => snapshotRequest.status.value === 'pending' || locationRequest.status.value === 'pending')
  const model = createWorkspaceModel(asOf, { snapshot: snapshotRequest.data, locations: locationRequest.data, error })

  const planningDate = createPlanningDate(asOf, dateRangeRequest.data)
  async function retry() {
    await dateRangeRequest.refresh()
    await Promise.all([snapshotRequest.refresh(), locationRequest.refresh(), healthRequest.refresh()])
  }
  function exportCsv() {
    if (model.plan.stops.value.length) {
      downloadCsv(planCsv(asOf.value, model.plan.stops.value, model.plan.notes.value), `collection-plan-${asOf.value}.csv`)
    }
  }
  const workspace = { ...model, planningDate, requests: { snapshotRequest, healthRequest, dateRangeRequest, error, loading, retry }, exportCsv }
  provide(workspaceKey, workspace)
  return workspace
}

type CollectionWorkspace = ReturnType<typeof createCollectionWorkspace>
const workspaceKey: InjectionKey<CollectionWorkspace> = Symbol('collection-workspace')
function useCollectionWorkspace() {
  const workspace = inject(workspaceKey)
  if (!workspace) throw new Error('Collection workspace provider missing')
  return workspace
}

// Connected view containers consume only the capability they need. Shared UI uses props/emits.
export function useWorkspaceData() {
  const { asOf, data, requests } = useCollectionWorkspace()
  return { asOf, ...data, ...requests }
}
export function useWorkspaceNavigation() { return useCollectionWorkspace().navigation }
export function usePlanningFilters() { return useCollectionWorkspace().filters }
export function useCollectionPlan() {
  const { asOf, plan, exportCsv } = useCollectionWorkspace()
  return { asOf, ...plan, exportCsv }
}

export function usePlanningDate() {
  const { asOf, planningDate, requests: { dateRangeRequest } } = useCollectionWorkspace()
  return { asOf, ...planningDate, dateRangeRequest }
}
