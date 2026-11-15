<script setup lang="ts">
import { computed } from 'vue';
import type { MonthlyAnalytics } from '~/shared/api/contracts/analytics';
import { monthlyDashboard } from '../domain/monthlyDashboard';
const props = defineProps<{ months: MonthlyAnalytics[]; asOf: string; firstDate?: string | null }>();
const dashboard = computed(() => monthlyDashboard(props.months, props.asOf, props.firstDate));
const format = (value: number | null) => value == null ? 'No reading' : Number(value.toFixed(1)).toString();
</script>
<template>
  <UiCard class="analytics-panel">
    <div class="section-heading"><div><h2>Monthly collection dashboard</h2><p>Collection activity and fill levels across all three glass streams, through {{ asOf }}.</p></div></div>
    <div class="monthly-dashboard-grid">
      <section v-for="chart in dashboard.charts" :key="chart.title" class="monthly-dashboard-chart">
        <h3>{{ chart.title }}</h3><p class="data-note">{{ chart.unit }}</p>
        <ul class="monthly-dashboard-legend"><li v-for="series in chart.series" :key="series.key"><span :style="{ background: series.color }" />{{ series.label }}</li></ul>
        <div class="monthly-dashboard-scroll">
          <svg viewBox="0 0 650 310" role="img" :aria-label="chart.title">
            <g v-for="tick in chart.ticks" :key="tick.value"><line x1="50" x2="630" :y1="tick.y" :y2="tick.y" class="monthly-gridline" /><text x="42" :y="tick.y + 4" text-anchor="end">{{ format(tick.value) }}</text></g>
            <g v-for="guide in chart.guides" :key="guide.value"><line x1="50" x2="630" :y1="guide.y" :y2="guide.y" stroke="var(--text-secondary)" stroke-dasharray="5 4" /><text x="630" :y="guide.y - 5" text-anchor="end">{{ guide.value }}%</text></g>
            <g v-for="series in chart.series" :key="series.key">
              <path v-if="chart.kind === 'line'" :d="series.path" :stroke="series.color" fill="none" stroke-width="2.5" />
              <template v-for="point in series.points" :key="point.month">
                <rect v-if="chart.kind === 'bar' && point.y != null" :x="point.barX" :y="point.y" :width="chart.barWidth - 1" :height="240 - point.y" :fill="series.color"><title>{{ point.month }} · {{ series.label }}: {{ format(point.value) }}</title></rect>
                <circle v-else-if="point.y != null" :cx="point.x" :cy="point.y" r="3.5" :fill="series.color"><title>{{ point.month }} · {{ series.label }}: {{ format(point.value) }}%</title></circle>
              </template>
            </g>
            <text v-for="month in dashboard.months" :key="month.month" :transform="`translate(${month.x},257) rotate(-45)`" text-anchor="end">{{ month.month }}{{ month.coverage ? '*' : '' }}</text>
          </svg>
        </div>
      </section>
    </div>
    <p class="data-note">Dashed guides: 80% service reference and 40% premature-collection boundary for mean fill; 50% comparison reference for collection shares. Means exclude overfull and unknown readings. Full white glass includes numeric 100% and explicit overfull; premature brown glass means numeric fill below 40%. Shares use all collections, including unknown readings, as their denominator. These comparisons do not establish the cause of collection timing.</p>
    <p v-for="month in dashboard.months.filter(row => row.coverage)" :key="month.month" class="data-note">* {{ month.month }}: {{ month.coverage }}</p>
    <details><summary>View chart data</summary><UiTable :table-attrs="{ 'aria-label': 'Monthly dashboard chart data' }" density="compact"><template #head><tr><th>Chart</th><th>Glass</th><th>Month</th><th>Value</th></tr></template><template v-for="chart in dashboard.charts" :key="chart.title"><template v-for="series in chart.series" :key="series.key"><tr v-for="point in series.points" :key="point.month"><td>{{ chart.title }}</td><td>{{ series.label }}</td><td>{{ point.month }}</td><td>{{ format(point.value) }}</td></tr></template></template></UiTable></details>
  </UiCard>
</template>
