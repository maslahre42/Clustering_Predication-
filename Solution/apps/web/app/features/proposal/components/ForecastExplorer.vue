<script setup lang="ts">
import { computed } from 'vue';
import type { ForecastCurve } from '~/shared/api/contracts/simulation';
const props = defineProps<{ forecast: ForecastCurve }>();
const x = (index: number) => 48 + index * 660 / Math.max(1, props.forecast.points.length - 1);
const y = (fill: number) => 240 - fill * 2;
const expected = computed(() => props.forecast.points.map((p, i) => `${x(i)},${y(p.expectedFill)}`).join(' '));
const band = computed(() => [...props.forecast.points.map((p, i) => `${x(i)},${y(p.upper)}`),
  ...props.forecast.points.map((p, i) => `${x(i)},${y(p.lower)}`).reverse()].join(' '));
</script>
<template>
  <section class="analytics-panel surface">
    <h2>Forecast if this container is not emptied again</h2>
    <p>Last emptied {{ forecast.lastEmptied }} · model median time from that emptying to full: {{ Math.round(forecast.medianDaysToFull) }} days.</p>
    <svg viewBox="0 0 760 285" role="img" aria-label="Expected fill with 10th to 90th percentile model band">
      <g v-for="level in [0, 50, 100]" :key="level"><line x1="48" x2="708" :y1="y(level)" :y2="y(level)" stroke="#ccd5d1" /><text x="6" :y="y(level) + 4" font-size="12">{{ level }}%</text></g>
      <polygon :points="band" fill="#d4eadb" /><polyline :points="expected" fill="none" stroke="#167147" stroke-width="3" />
      <text x="48" y="270" font-size="12">{{ forecast.points[0]?.date }}</text><text x="620" y="270" font-size="12">{{ forecast.points.at(-1)?.date }}</text>
    </svg>
    <p>Green line: expected fill. Shading: 10–90% model band. {{ forecast.note }}</p>
    <details><summary>Recorded pre-emptying observations (not current fill)</summary>
      <table><thead><tr><th>Date</th><th>Observed state</th></tr></thead><tbody>
        <tr v-for="point in forecast.history" :key="point.date"><td>{{ point.date }}</td><td>{{ point.isOverfull ? 'Overfull' : point.fill == null ? 'Unknown' : `${point.fill}%` }}</td></tr>
      </tbody></table>
    </details>
    <details><summary>Daily forecast and overflow probability</summary><table><thead><tr><th>Date</th><th>Expected fill</th><th>10–90% band</th><th>Full probability</th></tr></thead><tbody>
      <tr v-for="point in forecast.points" :key="point.date"><td>{{ point.date }}</td><td>{{ point.expectedFill.toFixed(1) }}%</td><td>{{ point.lower.toFixed(0) }}–{{ point.upper.toFixed(0) }}%</td><td>{{ (point.risk * 100).toFixed(1) }}%</td></tr>
    </tbody></table></details>
  </section>
</template>
