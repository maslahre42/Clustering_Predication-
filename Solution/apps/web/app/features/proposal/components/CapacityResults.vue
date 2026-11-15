<script setup lang="ts">
import { computed } from 'vue';
import type { CapacityResult } from '~/shared/api/contracts/capacity';
import { capacityCostDifference } from '../domain/capacity';
import { euro } from '../domain/insights';
const props = defineProps<{ result: CapacityResult }>();
const difference = computed(() => capacityCostDifference(props.result));
const maximumDays = computed(() => Math.max(1, ...props.result.fillingTimes.flatMap(r => [r.baselineAverageDays ?? 0, r.alternativeAverageDays ?? 0])));
const peakTrucks = computed(() => Math.max(1, ...props.result.scenarios.flatMap(s => s.daily.map(d => d.truckDays))));
const number = (n: number | null, digits = 1) => n == null ? 'Unavailable' : n.toFixed(digits);
function shiftPoints(index: number) {
  const daily = props.result.scenarios[index]?.daily ?? [];
  return daily.map((d,i) => `${45+i/Math.max(1,daily.length-1)*600},${200-d.truckDays/peakTrucks.value*160}`).join(' ');
}
</script>
<template>
  <section class="capacity-results" aria-label="Container and frequency financial comparison">
    <h3>Financial impact · {{ result.start }}–{{ result.end }}</h3>
    <p>{{ result.supportedStreams }} modelled site/type streams · {{ result.excludedStreams.length }} without ordinary-cycle evidence · {{ result.missingCoordinateSites.length }} sites without coordinates.</p>
    <p v-if="result.excludedStreams.length || result.missingCoordinateSites.length" role="status">Partial inventory: unsupported streams are excluded from demand, capacity and costs. Sites without coordinates remain pending. These totals do not price a complete service.</p>
    <div class="insight-costs"><div v-for="scenario in result.scenarios" :key="scenario.name"><span>{{ scenario.name === 'baseline' ? 'Baseline' : result.optimization ? 'Recommended' : 'Alternative' }} · period cost</span><strong>{{ euro(scenario.costs.totalEuro) }}</strong><small>{{ euro(scenario.costs.monthlyEquivalentEuro) }} monthly equivalent{{ scenario.costs.partial ? ' · partial estimate' : '' }}</small></div></div>
    <p v-if="difference != null">Alternative minus baseline: <strong>{{ euro(difference) }}</strong> for this period. Negative means lower modelled cost. {{ result.comparableService ? 'Alternative collects at least as much glass with no greater spill or remaining pending sites over the modelled inventory.' : 'Service outcomes differ or inventory coverage is incomplete; this is a cost trade-off, not a savings claim.' }}</p>
    <p>Monthly equivalent uses 30.4375 days. Unpriced categories are excluded from totals, not assumed free.</p>
    <div class="table-scroll"><table class="insights-table"><thead><tr><th>Cost / service outcome</th><th>Baseline</th><th>{{ result.optimization ? 'Recommended' : 'Alternative' }}</th></tr></thead><tbody>
      <tr><th>Truck-day package · truck, driver & driving</th><td v-for="s in result.scenarios" :key="s.name">{{ s.costs.truckEuro == null ? 'Unpriced' : euro(s.costs.truckEuro) }}</td></tr>
      <tr><th>Additional distance charge</th><td v-for="s in result.scenarios" :key="s.name">{{ s.costs.drivingIncluded ? 'Driving included in truck-day package' : s.costs.roadEuro == null ? 'Unpriced' : euro(s.costs.roadEuro) }}</td></tr>
      <tr><th>Containers · period share of monthly cost</th><td v-for="s in result.scenarios" :key="s.name">{{ s.costs.containerEuro == null ? 'Unpriced' : euro(s.costs.containerEuro) }}</td></tr>
      <tr><th>Installed physical containers</th><td v-for="s in result.scenarios" :key="s.name">{{ s.installedContainers }}</td></tr>
      <tr><th>Truck-days / peak trucks in one day</th><td v-for="s in result.scenarios" :key="s.name">{{ s.truckDays }} / {{ s.peakTrucks }}</td></tr>
      <tr><th>Emptying hours / total working hours</th><td v-for="s in result.scenarios" :key="s.name">{{ number(s.emptyingHours) }} / {{ number(s.workingHours) }}</td></tr>
      <tr><th>Street distance</th><td v-for="s in result.scenarios" :key="s.name">{{ number(s.distanceKm) }} km</td></tr>
      <tr><th>Site visits / physical containers emptied</th><td v-for="s in result.scenarios" :key="s.name">{{ s.siteVisits }} / {{ s.containersEmptied }}</td></tr>
      <tr><th>Same incoming glass demand</th><td v-for="s in result.scenarios" :key="s.name">{{ number(s.demandLitres / 1000) }} m³</td></tr>
      <tr><th>Collected / remaining glass</th><td v-for="s in result.scenarios" :key="s.name">{{ number(s.collectedLitres / 1000) }} / {{ number(s.remainingLitres / 1000) }} m³</td></tr>
      <tr><th>Glass exceeding installed capacity</th><td v-for="s in result.scenarios" :key="s.name">{{ number(s.spillLitres / 1000) }} m³</td></tr>
      <tr><th>Site/type stream-days full</th><td v-for="s in result.scenarios" :key="s.name">{{ s.fullStreamDays }}</td></tr>
      <tr><th>Pending sites at period end / pending site-days</th><td v-for="s in result.scenarios" :key="s.name">{{ s.pendingSites }} / {{ s.pendingSiteDays }}</td></tr>
    </tbody></table></div>
    <h3>Estimated average filling time by glass type</h3>
    <p>Arithmetic mean of capacity ÷ daily incoming volume across supported positive-demand site/type streams. Each stream has equal weight. Zero-demand streams have no finite filling time.</p>
    <svg class="capacity-chart" viewBox="0 0 700 310" role="img" aria-label="Average days to full for brown, green and white glass: baseline and alternative"><text x="150" y="20">Days to full · baseline (green) / alternative (blue)</text>
      <g v-for="(row,i) in result.fillingTimes" :key="row.material" :transform="`translate(0,${45+i*85})`"><text x="5" y="25">{{ row.material }}</text><rect x="100" y="0" :width="(row.baselineAverageDays ?? 0)/maximumDays*400" height="20" fill="#167147" /><text :x="110+(row.baselineAverageDays ?? 0)/maximumDays*400" y="15">{{ number(row.baselineAverageDays) }}</text><rect x="100" y="28" :width="(row.alternativeAverageDays ?? 0)/maximumDays*400" height="20" fill="#3974b5" /><text :x="110+(row.alternativeAverageDays ?? 0)/maximumDays*400" y="43">{{ number(row.alternativeAverageDays) }}</text><text x="100" y="67">{{ row.positiveStreams }} positive streams · {{ row.zeroDemandStreams }} zero-demand · {{ row.historicalCycles }} cycles</text></g>
    </svg>
    <h3>Daily truck shifts</h3>
    <svg class="capacity-chart" viewBox="0 0 700 255" role="img" aria-label="Daily truck shifts for baseline and alternative"><text x="5" y="35">{{ peakTrucks }}</text><text x="15" y="205">0</text><line x1="45" x2="645" y1="200" y2="200" stroke="currentColor" /><polyline :points="shiftPoints(0)" fill="none" stroke="#167147" stroke-width="3" /><polyline :points="shiftPoints(1)" fill="none" stroke="#3974b5" stroke-width="3" stroke-dasharray="6 4" /><text x="45" y="225">{{ result.start }}</text><text x="555" y="225">{{ result.end }}</text><text x="45" y="248">Baseline: green · Alternative: blue dashed</text></svg>
    <details><summary>Demand, financial and service assumptions</summary><ul><li v-for="text in result.assumptions" :key="text">{{ text }}</li></ul></details>
  </section>
</template>
