<script setup lang="ts">
import { computed } from 'vue';
import type { SimulationResult } from '~/shared/api/contracts/simulation';
import { euro } from '../domain/insights';
import { formatHours } from '../domain/proposal';
const props = defineProps<{ result: SimulationResult }>();
const dates = computed(() => [...new Set(props.result.scenarios.flatMap(s => s.daily.map(d => d.date)))].sort());
const maxVisits = computed(() => Math.max(1, ...props.result.scenarios.flatMap(s => s.daily.map(d => d.stops))));
function points(name: string) {
  const daily = new Map(props.result.scenarios.find(s => s.name === name)?.daily.map(d => [d.date, d.stops]));
  return dates.value.map((date, i) => `${45 + 660 * i / Math.max(1, dates.value.length - 1)},${235 - 190 * (daily.get(date) ?? 0) / maxVisits.value}`).join(' ');
}
</script>
<template>
  <section class="analytics-panel surface">
    <h2>Simulation: historical, forecast-driven and median policies</h2>
    <p>{{ result.start }}–{{ result.end }} · {{ result.knownBins }} known bins · training through {{ result.trainingThrough }} · seed {{ result.seed }} · {{ result.effectiveSolverTimeSeconds }} s per routing attempt.</p>
    <p><strong>Simulated outcomes, not measured savings.</strong> All policies use the same seeded demand model and fleet constraints. Missed sites remain unserved in every scenario.</p>
    <div class="table-scroll"><table class="proposal-comparison"><thead><tr><th>Outcome</th><th v-for="s in result.scenarios" :key="s.name">{{ s.label }}</th></tr></thead><tbody>
      <tr><th>Served site visits</th><td v-for="s in result.scenarios" :key="s.name">{{ s.site_visits }}</td></tr>
      <tr><th>Bins emptied</th><td v-for="s in result.scenarios" :key="s.name">{{ s.bin_collections }}</td></tr>
      <tr><th>Truck-days</th><td v-for="s in result.scenarios" :key="s.name">{{ s.truckDays }}</td></tr>
      <tr><th>Street distance</th><td v-for="s in result.scenarios" :key="s.name">{{ s.distanceKm == null ? '—' : `${s.distanceKm.toFixed(1)} km` }}</td></tr>
      <tr><th>Estimated operating cost</th><td v-for="s in result.scenarios" :key="s.name">{{ euro(s.costs?.totalEuro) }}{{ s.costs?.partial ? ' (partial)' : '' }}</td></tr>
      <tr><th>Total working time</th><td v-for="s in result.scenarios" :key="s.name">{{ formatHours(s.hours) }}</td></tr>
      <tr><th>Mean fill at collection</th><td v-for="s in result.scenarios" :key="s.name">{{ s.mean_fill_at_collection_pct.toFixed(1) }}%</td></tr>
      <tr><th>Collections below 40%</th><td v-for="s in result.scenarios" :key="s.name">{{ (s.share_collections_below_40pct * 100).toFixed(1) }}%</td></tr>
      <tr><th>Simulated container-days full</th><td v-for="s in result.scenarios" :key="s.name">{{ s.overflow_bin_days.toFixed(0) }}</td></tr>
      <tr><th>Full-cycle events</th><td v-for="s in result.scenarios" :key="s.name">{{ s.overflow_events }}</td></tr>
      <tr><th>Missed mandatory stop-days</th><td v-for="s in result.scenarios" :key="s.name">{{ s.missedMandatory }}</td></tr>
    </tbody></table></div>
    <h3>Daily served site visits</h3>
    <svg viewBox="0 0 760 280" role="img" aria-label="Daily site visits for historical and dynamic policies">
      <line x1="45" x2="705" y1="235" y2="235" stroke="#87958c" />
      <text x="5" y="48" font-size="12">{{ maxVisits }}</text><text x="20" y="240" font-size="12">0</text>
      <polyline :points="points('historical')" fill="none" stroke="#6a7687" stroke-width="2" />
      <polyline :points="points('zakaria')" fill="none" stroke="#9262b0" stroke-width="2" />
      <polyline :points="points('dynamic')" fill="none" stroke="#167147" stroke-width="3" />
      <text x="45" y="267" font-size="12">{{ dates[0] }}</text><text x="620" y="267" font-size="12">{{ dates.at(-1) }}</text>
    </svg>
    <p>Gray: historical calendar. Green: forecast-driven policy. Purple: cycle-median policy (80% urgent, 60% same-site). Missing days have zero visits.</p>
    <ProjectValidationResults v-if="result.forecastComparison && result.optimizationCheck" :comparison="result.forecastComparison" :optimization="result.optimizationCheck" />
    <h3>Risk-threshold trade-off</h3><p>Selection-only mandatory-site sweep; these rows do not enforce truck or shift limits and differ from the routed comparison above.</p>
    <table><thead><tr><th>Mandatory risk threshold</th><th>Site visits</th><th>Container-days full</th><th>Full-cycle events</th></tr></thead><tbody>
      <tr v-for="row in result.frontier" :key="row.threshold"><td>{{ (row.threshold * 100).toFixed(0) }}%</td><td>{{ row.site_visits }}</td><td>{{ row.overflow_bin_days.toFixed(0) }}</td><td>{{ row.overflow_events }}</td></tr>
    </tbody></table>
    <details><summary>Simulation assumptions and limitations</summary><ul><li v-for="text in result.assumptions" :key="text">{{ text }}</li></ul></details>
  </section>
</template>
