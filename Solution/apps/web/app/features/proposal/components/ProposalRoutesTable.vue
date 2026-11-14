<script setup lang="ts">
import { computed } from 'vue';
import type { CollectionProposal } from '~/shared/api/contracts/proposal';
import { DECISION_LABELS, formatHours, formatRisk, routeRows } from '~/features/proposal/domain/proposal';

const props = defineProps<{ proposal: CollectionProposal }>();
const rows = computed(() => routeRows(props.proposal));
const trucks = computed(() => props.proposal.plan.routes.map(route => ({
  truck: route.truck, loads: route.trips.length, bins: route.bins,
  stops: route.trips.reduce((count, trip) => count + trip.stops.length, 0),
  time: formatHours(route.hours), distance: route.distanceKm,
})));
</script>
<template>
  <div class="proposal-routes">
    <p v-if="!trucks.length" class="proposal-empty">{{ proposal.plan.unserved.length ? 'No feasible truck route was scheduled. Review the unserved reasons and settings.' : `No truck is needed on ${proposal.planDate} with these settings.` }}</p>
    <template v-else>
      <ul class="proposal-trucks" aria-label="Trucks in this proposal">
        <li v-for="truck in trucks" :key="truck.truck">
          <strong>Truck {{ truck.truck }}</strong>
          <span>{{ truck.loads }} {{ truck.loads === 1 ? 'load' : 'loads' }} · {{ truck.stops }} stops · {{ truck.bins }} containers</span>
          <span>{{ truck.time }}<template v-if="truck.distance != null"> · {{ truck.distance.toFixed(1) }} km straight-line × detour</template></span>
        </li>
      </ul>
      <UiTable :table-attrs="{ 'aria-label': 'Proposed stops in driving order' }" density="compact">
        <template #head>
          <tr>
            <th scope="col">Truck</th><th scope="col">Load</th><th scope="col">Stop</th><th scope="col">Location</th>
            <th scope="col">Glass to empty</th><th scope="col">Estimated weight</th><th scope="col">Overflow risk</th><th scope="col">Why</th>
          </tr>
        </template>
        <tr v-for="row in rows" :key="`${row.truck}:${row.locationId}`">
          <td>Truck {{ row.truck }}</td>
          <td>Load {{ row.load }}</td>
          <td>{{ row.sequence }}</td>
          <td :title="row.locationId">Location {{ row.locationId.slice(0, 8) }}</td>
          <td><GlassFractionBadge v-for="material in row.materials" :key="material" :material="material" /></td>
          <td>{{ Math.round(row.weightKg).toLocaleString('en-US') }} kg</td>
          <td>{{ formatRisk(row.risk) }}</td>
          <td><UiTag :label="row.mandatory ? DECISION_LABELS.due : DECISION_LABELS.optional" :color="row.mandatory ? 'danger' : 'neutral'" density="compact" /></td>
        </tr>
      </UiTable>
    </template>
  </div>
</template>
