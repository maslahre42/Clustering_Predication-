<script setup lang="ts">
import { toRef } from 'vue';
import type { MonthlyAnalytics } from '~/shared/api/contracts/analytics';
import { GLASS_OPTIONS } from '~/shared/config/materials';
import { createPatternTrends } from '../state/createPatternTrends';
const props = defineProps<{ months: MonthlyAnalytics[]; asOf: string; firstDate?: string | null }>();
const { material, metric, rows } = createPatternTrends(toRef(props, 'months'), toRef(props, 'asOf'), toRef(props, 'firstDate'));
const metrics = [{ value: 'fill', label: 'Mean fill at collection' }, { value: 'collections', label: 'Collection count' }];
</script>
<template>
  <UiCard class="analytics-panel">
    <div class="section-heading">
      <div><h2>Patterns over time</h2><p>Compare fill at emptying with collection frequency to investigate changes in the schedule.</p></div>
      <div class="analytics-chart-controls">
        <UiSelect v-model="material" label="Trend glass fraction" :options="GLASS_OPTIONS" :allow-empty="false" />
        <UiSelect v-model="metric" label="Trend measure" :options="metrics" :allow-empty="false" />
      </div>
    </div>
    <p>{{ metric === 'fill' ? 'Bar scale: 0–100% numeric mean fill.' : 'Bars scale to the highest collection count in this series.' }} Overfull and unknown readings have no invented fill percentage.</p>
    <ol class="analytics-trend" :aria-label="`${material} glass monthly ${metric === 'fill' ? 'mean fill' : 'collections'}`">
      <li v-for="row in rows" :key="row.month" :class="{ 'analytics-partial': row.coverage }">
        <div class="analytics-trend-label"><strong>{{ row.month }}</strong><small v-if="row.coverage">{{ row.coverage }}</small></div>
        <div class="analytics-trend-track" aria-hidden="true"><span :style="{ width: `${row.width}%`, background: `var(--fraction-${material})` }" /></div>
        <div class="analytics-trend-value"><strong>{{ row.value == null ? '—' : metric === 'fill' ? `${row.value.toFixed(1)}%` : row.value }}</strong><small>{{ row.collections }} collections · {{ row.numericReadings }} numeric · {{ row.overfullCount }} overfull</small></div>
      </li>
    </ol>
    <p v-if="!rows.length">No observations for this glass fraction by {{ asOf }}.</p>
    <p class="data-note">Partial months are marked and have less exposure. Months without readings are absent, not zero-fill months. Holiday and seasonal associations can reflect collection timing; this chart does not establish their cause. The forecast module shows fitted month and school-vacation effects.</p>
  </UiCard>
</template>
