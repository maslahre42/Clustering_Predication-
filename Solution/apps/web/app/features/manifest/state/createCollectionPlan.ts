import { computed, ref, type ComputedRef, type Ref } from 'vue'
import type { PlanningBin } from '../../inventory/types'
import type { WorkspaceConfiguration } from '../../../shared/config/workspace'
import { clusterBins } from '../../inventory/domain/catalog.ts'
import { orderStops, roundTripKm } from '../../../shared/domain/geometry.ts'
import type { CollectionProposal } from '../../../shared/api/contracts/proposal'

interface PlanSources {
  asOf: Ref<string>
  bins: ComputedRef<PlanningBin[]>
  filteredBins: ComputedRef<PlanningBin[]>
  ready: ComputedRef<boolean>
}

export function createCollectionPlan(sources: PlanSources, configuration: WorkspaceConfiguration) {
  const selectedKeys = ref<string[]>([])
  const routeOrder = ref<string[]>([])
  const notes = ref<Record<string, string>>({})
  const collectionDate = ref(sources.asOf.value)
  const acceptedProposal = ref<CollectionProposal | null>(null)
  function editManually() { acceptedProposal.value = null }
  const depot = { ...configuration.depot }
  const selectedBins = computed(() => sources.bins.value.filter(bin => selectedKeys.value.includes(bin.key)))
  const stops = computed(() => {
    const grouped = clusterBins(selectedBins.value)
    if (!routeOrder.value.length) return orderStops(grouped, depot)
    const byId = new Map(grouped.map(stop => [stop.locationId, stop]))
    return [...routeOrder.value.flatMap(id => byId.has(id) ? [byId.get(id)!] : []),
      ...grouped.filter(stop => !routeOrder.value.includes(stop.locationId))]
  })
  const routePoints = computed(() => stops.value.length ? [depot, ...stops.value, depot] : [])
  const distance = computed(() => roundTripKm(stops.value, depot))

  function toggleBin(key: string, checked: boolean) {
    if (!sources.ready.value || !sources.bins.value.some(bin => bin.key === key)) return
    editManually()
    selectedKeys.value = checked ? [...new Set([...selectedKeys.value, key])] : selectedKeys.value.filter(value => value !== key)
  }
  function toggleLocation(id: string, checked: boolean) {
    for (const bin of sources.filteredBins.value.filter(bin => bin.locationId === id)) toggleBin(bin.key, checked)
  }
  function removeStop(id: string) { editManually(); selectedKeys.value = selectedKeys.value.filter(key => !key.startsWith(`${id}:`)) }
  function moveStop(id: string, direction: number) {
    editManually()
    const order = stops.value.map(stop => stop.locationId)
    const index = order.indexOf(id), next = index + direction
    if (index < 0 || next < 0 || next >= order.length) return
    ;[order[index], order[next]] = [order[next]!, order[index]!]
    routeOrder.value = order
  }
  function clearPlan() { selectedKeys.value = []; routeOrder.value = []; notes.value = {}; acceptedProposal.value = null; collectionDate.value = sources.asOf.value }
  /** Replace the manual selection with a route proposal. Unknown bins are ignored; the plan stays editable. */
  function applyProposal(input: string[] | CollectionProposal, order: string[] = []) {
    if (!sources.ready.value) return false
    const proposal = Array.isArray(input) ? null : input
    if (proposal && proposal.asOf !== sources.asOf.value) return false
    const keys = proposal ? proposal.plan.routes.flatMap(route => route.trips.flatMap(trip => trip.stops.flatMap(id =>
      proposal.bins.filter(bin => bin.locationId === id && ['due', 'neighbour', 'optional'].includes(bin.decision)).map(bin => `${id}:${bin.material}`)))) : input as string[]
    if (proposal) order = proposal.plan.routes.flatMap(route => route.trips.flatMap(trip => trip.stops))
    const known = new Set(sources.bins.value.map(bin => bin.key))
    selectedKeys.value = [...new Set(keys.filter(key => known.has(key)))]
    const stopIds = new Set(selectedBins.value.map(bin => bin.locationId))
    routeOrder.value = order.filter(id => stopIds.has(id))
    notes.value = {}
    acceptedProposal.value = proposal ? JSON.parse(JSON.stringify(proposal)) : null
    collectionDate.value = proposal?.planDate ?? sources.asOf.value
    return true
  }
  function addDayCollections() {
    for (const bin of sources.filteredBins.value.filter(bin => bin.lastCollection === sources.asOf.value)) toggleBin(bin.key, true)
  }
  return { depot, selectedKeys, routeOrder, notes, selectedBins, stops, routePoints, distance,
    toggleBin, toggleLocation, removeStop, moveStop, clearPlan, addDayCollections, applyProposal,
    collectionDate, acceptedProposal, editManually }
}
