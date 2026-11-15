<script setup lang="ts">
import type { CollectionPatterns } from '~/shared/api/contracts/analytics';
defineProps<{ patterns: CollectionPatterns }>();
defineEmits<{ inspect: [locationId: string] }>();
</script>
<template>
  <div>
  <UiCard class="analytics-panel">
    <h2>Accumulation between emptyings</h2>
    <p>Assuming every recorded visit empties the bin, its next pre-emptying reading divided by the days since that visit estimates a cycle rate. These are pooled cycle medians by material, not differences between consecutive fill readings.</p>
    <UiTable :table-attrs="{ 'aria-label': 'Observed filling cycle rates' }">
      <template #head><tr><th>Glass</th><th>Median rate</th><th>Numeric cycles below 100%</th><th>Full / overfull cycles</th></tr></template>
      <tr v-for="row in patterns.cycles" :key="row.material"><td><GlassFractionBadge :material="row.material" /></td><td>{{ row.medianRatePercentPerDay == null ? '—' : `${row.medianRatePercentPerDay.toFixed(2)} pp/day` }}</td><td>{{ row.numericCycles }}</td><td>{{ row.lowerBoundCycles }}</td></tr>
    </UiTable>
    <p class="data-note">The first visit has no known prior reset. Unknown visits reset the interval but supply no rate. Numeric 100% and overfull give lower bounds, so they are counted separately and excluded from the median. Sparse or censored histories can bias comparisons.</p>
  </UiCard>
  <UiCard class="analytics-panel">
    <h2>Containers to investigate</h2>
    <p>{{ patterns.reviewBinCount }} containers meet a review rule. Showing {{ patterns.reviewBins.length }}, with repeated overfull first. These flags describe past visits and do not establish current urgency.</p>
    <UiTable :table-attrs="{ 'aria-label': 'Historical container review flags' }">
      <template #head><tr><th>Location</th><th>Glass</th><th>Pattern</th><th>Collections</th><th>At ≤30%</th><th>Overfull</th></tr></template>
      <tr v-for="row in patterns.reviewBins" :key="`${row.locationId}:${row.material}`">
        <td><UiButton :label="row.locationId" mode="plain" @click="$emit('inspect', row.locationId)" /></td><td><GlassFractionBadge :material="row.material" /></td><td>{{ row.reason === 'repeated_overfull' ? 'Repeated overfull' : 'Frequent low fill' }}</td><td>{{ row.collections }}</td><td>{{ row.lowCollections }}</td><td>{{ row.overfullCollections }}</td>
      </tr>
      <template #empty>No containers meet these review rules at the selected cutoff.</template>
    </UiTable>
    <p class="data-note">At least three recorded visits are required. Repeated overfull: at least two explicit overfull readings. Frequent low fill: at least three readings at ≤30%, covering at least half of visits. These are transparent review rules; behavioral clustering is available under Forecast, routes & simulation.</p>
  </UiCard>
  </div>
</template>
