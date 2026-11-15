<script setup lang="ts">
import type { OperatingCost } from '~/shared/api/contracts/proposal';
import { euro } from '../domain/insights';
defineProps<{ costs?: OperatingCost; truckDays?: boolean }>();
</script>
<template>
  <section class="surface analytics-panel" aria-label="Estimated operating costs">
    <h2>Estimated operating costs</h2>
    <p v-if="!costs?.configured">Enter your truck-day package in Operating costs above to price this plan.</p>
    <template v-else>
      <div class="insight-costs"><div><span>Driving</span><strong>{{ costs.drivingIncluded ? 'Included in truck-day package' : costs.costPerKmEuro > 0 ? euro(costs.variableEuro) : 'Not priced' }}</strong><small>{{ costs.distanceKm?.toFixed(1) ?? 'Unknown' }} road km<span v-if="!costs.drivingIncluded"> × {{ euro(costs.costPerKmEuro) }}/km additional</span></small></div><div><span>Scheduled {{ truckDays ? 'truck-days' : 'trucks' }}</span><strong>{{ costs.fixedTruckCostEuro > 0 ? euro(costs.fixedEuro) : 'Not priced' }}</strong><small>{{ costs.trucks }} shifts × {{ euro(costs.fixedTruckCostEuro) }}</small></div><div><span>{{ costs.partial ? 'Partial estimate' : 'Total estimate' }}</span><strong>{{ euro(costs.totalEuro) }}</strong></div></div>
      <p v-if="costs.partial">The truck-day package or an additional distance charge is not fully priced.</p>
      <p>Planning estimate using forecast loads and road distances. Fixed shift cost is counted once per scheduled truck{{ truckDays ? ' per day' : '' }}, including trucks with several loads. The €500 daily package includes truck, driver and driving kilometres; no separate per-kilometre charge is added by default.</p>
    </template>
  </section>
</template>
