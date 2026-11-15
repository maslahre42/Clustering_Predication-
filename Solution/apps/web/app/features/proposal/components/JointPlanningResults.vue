<script setup lang="ts">
import { toRef } from 'vue';
import type { CapacityResult } from '~/shared/api/contracts/capacity';
import type { Location } from '~/shared/api/contracts/locations';
import { createJointResults } from '../state/createJointResults';
import { jointPlanCsv } from '../domain/capacity';
import { downloadCsv } from '~/shared/browser/download';
import { euro } from '../domain/insights';
const props=defineProps<{ result: CapacityResult; locations: Location[] }>();
const state=createJointResults(toRef(props,'result'));
const { selectedDate,search,material,page,plan,day,filtered,pages,rows,routeMap }=state;
</script>
<template>
  <section v-if="result.optimization" class="capacity-results" aria-label="Automatic container and schedule recommendation">
    <h3>{{ plan ? 'Recommended containers & collection calendar' : 'No feasible recommendation found' }}</h3>
    <p>Maximum fill target: {{ result.optimization.targetFillPercent }}% · {{ result.days }}-day repeating cycle · {{ result.optimization.candidatesEvaluated }} routed candidates checked. Best feasible plan found within the search bounds; global optimality is not proven.</p>
    <p v-if="!plan" role="alert">The search did not produce a verified plan within these bounds. Check the operating weekdays, truck capacities, available shifts, site space limits and interval range. Missing coordinates or insufficient data remain visible below. No unsafe plan is offered for dispatch.</p>
    <p v-if="result.optimization.geometryError" role="status">{{ result.optimization.geometryError }}</p>
    <p v-if="!plan">Baseline cycle cost: {{ euro(result.scenarios[0]?.costs.totalEuro) }} · {{ result.excludedStreams.length }} unsupported streams · {{ result.missingCoordinateSites.length }} sites without coordinates.</p>
    <template v-if="plan">
      <p><strong>{{ plan.installedContainers }} modelled containers · {{ plan.truckDays }} paid truck-days · {{ plan.targetViolationStreamDays }} fill-target violations.</strong> Every modelled stream returns to its initial cyclic stock; the cycle collects its entire incoming glass volume.</p>
      <p v-if="!result.scenarios[0]?.feasible">The baseline does not meet the same fill, space, interval or cyclic service constraints. Its cost is shown as a service trade-off.</p>
      <p>Container costs and physical site limits need confirmation. Unpriced container expense and excluded history make the financial recommendation conditional. This is a repeating operating design, not a claim about today's occupancy or a collection already performed.</p>
      <UiButton label="Download optimized collection calendar (CSV)" mode="outline" @click="downloadCsv(jointPlanCsv(result), `optimized-calendar-${result.start}.csv`)" />
      <h4>Daily shift calendar</h4>
      <div class="table-scroll joint-calendar"><table class="insights-table"><thead><tr><th>Date</th><th>Truck shifts</th><th>Site visits</th><th>Containers emptied</th><th>Road km</th><th>Working hours</th></tr></thead><tbody><tr v-for="d in plan.daily" :key="d.date"><td><button type="button" :aria-pressed="selectedDate === d.date" @click="selectedDate = d.date">{{ d.date }}</button></td><td>{{ d.truckDays }}</td><td>{{ d.siteVisits }}</td><td>{{ d.containersEmptied }}</td><td>{{ d.distanceKm.toFixed(1) }}</td><td>{{ d.hours.toFixed(1) }}</td></tr></tbody></table></div>
      <label>Show optimized routes for date<select :value="selectedDate" aria-label="Show optimized routes for date" @change="selectedDate = ($event.target as HTMLSelectElement).value"><option v-for="d in plan.daily" :key="d.date" :value="d.date">{{ d.date }} · {{ d.truckDays }} shifts</option></select></label>
      <ProposalRouteMap v-if="routeMap" :proposal="routeMap" :locations="locations" />
      <p v-else-if="day">No truck collection is scheduled on {{ day.date }}.</p>
      <h4>Recommended inventory and frequency per site/type</h4>
      <div class="capacity-controls"><label>Find recommended site<input v-model="search" type="search" /></label><label>Recommended glass type<select :value="material" aria-label="Recommended glass type" @change="material = ($event.target as HTMLSelectElement).value"><option value="">All types</option><option value="brown">Brown</option><option value="green">Green</option><option value="white">White</option></select></label></div>
      <div class="table-scroll"><table class="insights-table"><thead><tr><th>Site / type</th><th>Current → recommended</th><th>Incoming glass</th><th>Average / maximum gap</th><th>Collections per cycle</th><th>Highest expected fill</th></tr></thead><tbody><tr v-for="r in rows" :key="`${r.locationId}:${r.material}`"><td>{{ r.locationId }} · {{ r.material }}</td><td>{{ r.baselineCount }} → {{ r.recommendedCount }}</td><td>{{ r.dailyLitres.toFixed(1) }} L/day</td><td>{{ r.averageIntervalDays?.toFixed(1) ?? 'No demand' }} / {{ r.maximumIntervalDays ?? '—' }} days</td><td>{{ r.visits }}</td><td>{{ r.maximumFillPercent.toFixed(1) }}%</td></tr></tbody></table></div>
      <div class="proposal-actions"><UiButton label="Previous recommended sites" mode="outline" :disabled="page<=1" @click="page--" /><span>Page {{ page }} of {{ pages }} · {{ filtered.length }} streams</span><UiButton label="Next recommended sites" mode="outline" :disabled="page>=pages" @click="page++" /></div>
    </template>
  </section>
</template>
