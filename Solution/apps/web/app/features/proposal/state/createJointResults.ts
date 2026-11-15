import { computed, ref, watch, type Ref } from 'vue'
import type { CapacityResult } from '../../../shared/api/contracts/capacity'
import type { RouteMapProposal } from '../domain/routeMap'
export function createJointResults(result: Readonly<Ref<CapacityResult>>) {
  const selectedDate = ref(''), search = ref(''), material = ref(''), page = ref(1)
  const plan = computed(() => result.value.scenarios[1])
  watch(result, () => { selectedDate.value = plan.value?.daily.find(d => d.truckDays > 0)?.date ?? ''; page.value = 1 }, { immediate: true, flush: 'sync' })
  watch([search,material], () => { page.value = 1 }, { flush: 'sync' })
  const day = computed(() => plan.value?.daily.find(d => d.date === selectedDate.value))
  const filtered = computed(() => (result.value.optimization?.recommendations ?? []).filter(r => (!material.value || r.material === material.value) && r.locationId.toLowerCase().includes(search.value.trim().toLowerCase())))
  const pages = computed(() => Math.max(1,Math.ceil(filtered.value.length/25)))
  const rows = computed(() => filtered.value.slice((page.value-1)*25,page.value*25))
  const routeMap = computed<RouteMapProposal | null>(() => {
    const d=day.value, settings=result.value.settings
    if (!d || !settings || !d.routes?.length) return null
    return { planDate: d.date, settings, routing: result.value.routing, stops: d.stops ?? [],
      plan: { routes: d.routes, unserved: [], totals: { trucks:d.truckDays,trips:d.routes.reduce((n,r)=>n+r.trips.length,0),stops:d.siteVisits,bins:d.containersEmptied,
        hours:d.hours,distanceKm:d.distanceKm,weightT:d.routes.reduce((n,r)=>n+r.trips.reduce((v,t)=>v+t.weightKg/1000,0),0),volumeM3:d.routes.reduce((n,r)=>n+r.trips.reduce((v,t)=>v+t.volumeL/1000,0),0),loadsByCapacity:0 } } }
  })
  return { selectedDate,search,material,page,plan,day,filtered,pages,rows,routeMap }
}
