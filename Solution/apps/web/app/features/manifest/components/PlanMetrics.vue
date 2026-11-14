<script setup lang="ts">
import { GLASS_MATERIALS } from '~/shared/config/materials';
const { asOf, stops, selectedBins, distance } = useCollectionPlan();
const fractions = computed(() => GLASS_MATERIALS.map(color => `${selectedBins.value.filter(bin => bin.material === color).length} ${color}`).join(' · '));
</script>
<template>
  <div class="plan-metrics">
    <MetricCard label="GROUPED STOPS" :value="stops.length" caption="Physical collection locations" />
    <MetricCard label="SELECTED BINS" :value="selectedBins.length" :caption="fractions" />
    <MetricCard label="CLOSED LOOP" :value="`${distance.toFixed(1)} km`" caption="Straight-line distance · not road travel" />
    <MetricCard label="PLANNING BASELINE" :value="asOf" caption="Records through this date only" compact />
  </div>
</template>
