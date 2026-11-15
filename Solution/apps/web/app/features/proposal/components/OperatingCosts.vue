<script setup lang="ts">
import type { OperatingCost } from '~/shared/api/contracts/proposal';
import { euro } from '../domain/insights';
defineProps<{ costs?: OperatingCost; truckDays?: boolean }>();
</script>
<template>
  <section class="surface analytics-panel" aria-label="Estimated operating costs">
    <h2>Estimated operating costs</h2>
    <p v-if="!costs?.configured">Enter your variable cost per road kilometre and fixed cost per truck shift in Operating costs above to price this plan.</p>
    <template v-else>
      <div class="insight-costs"><div><span>Driving</span><strong>{{ costs.costPerKmEuro > 0 ? euro(costs.variableEuro) : 'Not priced' }}</strong><small>{{ costs.distanceKm?.toFixed(1) ?? 'Unknown' }} road km × {{ euro(costs.costPerKmEuro) }}/km</small></div><div><span>Scheduled {{ truckDays ? 'truck-days' : 'trucks' }}</span><strong>{{ costs.fixedTruckCostEuro > 0 ? euro(costs.fixedEuro) : 'Not priced' }}</strong><small>{{ costs.trucks }} shifts × {{ euro(costs.fixedTruckCostEuro) }}</small></div><div><span>{{ costs.partial ? 'Partial estimate' : 'Total estimate' }}</span><strong>{{ euro(costs.totalEuro) }}</strong></div></div>
      <p v-if="costs.partial">One cost rate is unpriced. The total includes only the entered cost categories.</p>
      <p>Planning estimate using forecast loads and road distances. Fixed shift cost is counted once per scheduled truck{{ truckDays ? ' per day' : '' }}, including trucks with several loads. Enter variable and fixed costs without overlapping expenses.</p>
    </template>
  </section>
</template>
