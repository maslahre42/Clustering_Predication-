import { computed, ref, watch, type Ref } from 'vue'
import type { CollectionProposal } from '../../../shared/api/contracts/proposal'
import type { Location } from '../../../shared/api/contracts/locations'
import { proposalMap } from '../domain/routeMap.ts'

export function createRouteMapState(proposal: Readonly<Ref<CollectionProposal>>, locations: Readonly<Ref<readonly Location[]>>) {
  const selectedTruck = ref<number | null>(null)
  const selectedLoad = ref('')
  const selectedStop = ref('')
  const showUnserved = ref(false)
  const expanded = ref(false)
  const fitVersion = ref(0)
  const model = computed(() => proposalMap(proposal.value, locations.value))
  const visibleTrucks = computed(() => model.value.trucks.filter(truck => selectedTruck.value == null || truck.truck === selectedTruck.value)
    .map(truck => ({ ...truck, paths: truck.paths.filter(path => !selectedLoad.value || path.load === Number(selectedLoad.value)),
      stops: truck.stops.filter(stop => !selectedLoad.value || stop.load === Number(selectedLoad.value)) })))
  const stops = computed(() => visibleTrucks.value.flatMap(truck => truck.stops))
  const activeStop = computed(() => stops.value.find(stop => stop.key === selectedStop.value) ?? null)
  const missing = computed(() => visibleTrucks.value.reduce((sum, truck) => sum + truck.missing, 0))
  const provenance = computed(() => {
    const sources = new Set(stops.value.map(stop => stop.provenance))
    return !sources.size ? 'No mapped collection stops' : sources.size > 1 ? 'Mixed coordinate sources'
      : sources.has('synthetic') ? 'Synthetic site assignments' : sources.has('imported') ? 'Imported site coordinates' : 'Unverified site coordinates'
  })
  const loads = computed(() => {
    const truck = model.value.trucks.find(truck => truck.truck === selectedTruck.value)
    return [{ value: '', label: 'All loads' }, ...Array.from({ length: truck?.loads ?? 0 }, (_, i) => ({ value: String(i + 1), label: `Load ${i + 1}` }))]
  })
  function selectTruck(truck: number | null) { selectedTruck.value = truck; selectedLoad.value = ''; selectedStop.value = ''; fitVersion.value++ }
  function fit() { selectedStop.value = ''; fitVersion.value++ }
  watch(selectedLoad, fit, { flush: 'sync' })
  watch(proposal, () => { selectTruck(null); showUnserved.value = false }, { flush: 'sync' })
  return { selectedTruck, selectedLoad, selectedStop, showUnserved, expanded, fitVersion, model, visibleTrucks,
    stops, activeStop, missing, provenance, loads, selectTruck, fit }
}
