<script setup lang="ts">
import { toRef } from 'vue';
import type { MaterialDynamics } from '~/shared/api/contracts/analytics';
import { GLASS_OPTIONS } from '~/shared/config/materials';
import { createCollectionDynamics } from '../state/createCollectionDynamics';
const props = defineProps<{ dynamics: MaterialDynamics[] }>();
defineEmits<{ inspect: [locationId: string] }>();
const { material, ranking, selected, rows, charts, curve, within28 } = createCollectionDynamics(toRef(props,'dynamics'));
const rankings = [{value:'fastest',label:'Fastest estimated filling'}, {value:'slowest',label:'Slowest estimated filling'}];
const number = (value: number | null | undefined) => value == null ? '—' : value.toFixed(1);
</script>
<template>
  <UiCard class="analytics-panel" aria-label="Collection cadence and filling dynamics">
    <div class="section-heading"><div><h2>Collection cadence & filling dynamics</h2><p>Compare how often containers were emptied with how quickly they filled between recorded visits.</p></div><UiSelect v-model="material" label="Dynamics glass fraction" :options="GLASS_OPTIONS" :allow-empty="false" /></div>
    <template v-if="selected">
      <p><strong>{{ selected.collections }} recorded collections</strong> · {{ selected.bins }} containers · {{ selected.intervals }} intervals between visits. The first collection per container has no known preceding cycle.</p>
      <div class="dynamics-grid">
        <section v-for="chart in charts" :key="chart.title" class="dynamics-chart">
          <h3>{{ chart.title }}</h3>
          <template v-if="chart.distribution"><p>Median <strong>{{ number(chart.distribution.median) }} {{ chart.unit }}</strong> · middle 50%: {{ number(chart.distribution.q1) }}–{{ number(chart.distribution.q3) }} · {{ chart.distribution.count }} cycles</p>
          <ol class="dynamics-histogram" :aria-label="`${material} ${chart.title.toLowerCase()} distribution`"><li v-for="(bar,index) in chart.bars" :key="index" :title="`${bar.isTail ? 'Above ' + number(bar.lower) : number(bar.lower) + '–' + number(bar.upper)} ${chart.unit}: ${bar.count} cycles`"><strong>{{ bar.count }}</strong><div class="dynamics-bar-space"><span :style="{ height: `${bar.height}%`, background: `var(--fraction-${material})` }" /></div><small>{{ bar.isTail ? '>' + number(bar.lower) : number(bar.lower) + '–' + number(bar.upper) }}</small><span class="sr-only">{{ chart.unit }}: {{ bar.count }} cycles</span></li></ol><p class="data-note">The final bar retains all values above the 95th-percentile scale limit (at least 1 {{ chart.unit }}). No outliers are discarded.</p></template>
          <p v-else>No eligible cycles by this date.</p>
        </section>
        <section class="dynamics-chart dynamics-filling-time">
          <h3>Estimated time to fill from empty</h3>
          <template v-if="selected.fillingTimes"><p>Median <strong>{{ number(selected.fillingTimes.median) }} days</strong> · middle 50%: {{ number(selected.fillingTimes.q1) }}–{{ number(selected.fillingTimes.q3) }} days · {{ selected.fillingTimes.count }} positive ordinary cycles.</p>
          <svg viewBox="0 0 700 260" role="img" :aria-label="`${material} estimated filling-time cumulative distribution`"><line x1="45" y1="220" x2="645" y2="220" stroke="currentColor" /><line x1="45" y1="40" x2="45" y2="220" stroke="currentColor" /><line :x1="45+28/90*600" :x2="45+28/90*600" y1="40" y2="220" stroke="currentColor" stroke-dasharray="5 5" opacity=".4" /><polyline :points="curve" fill="none" :stroke="`var(--fraction-${material})`" stroke-width="3" /><text x="3" y="45">100%</text><text x="13" y="225">0%</text><text x="42" y="245">0</text><text :x="45+28/90*600-20" y="245">28 days</text><text x="590" y="245">90 days</text></svg>
          <p>{{ ((within28?.share ?? 0)*100).toFixed(1) }}% of eligible <strong>cycles</strong> project to full within 28 days ({{ within28?.cycles ?? 0 }} of {{ selected.fillingTimes.count }}). The line is a comparison, not an assumed collection schedule. Projections beyond 90 days remain in the denominator.</p></template>
          <p v-else>No positive ordinary cycles support a filling-time estimate.</p>
        </section>
      </div>
      <p class="data-note">Each visit resets the bin. Rate = the next numeric pre-emptying fill ÷ elapsed days. Full/overfull readings are lower bounds: {{ selected.lowerBoundCycles }} cycles are excluded from exact rate and filling-time estimates. {{ selected.unknownCycles }} unknown cycles supply no rate; {{ selected.zeroFillCycles }} zero-fill cycles retain a zero rate but no finite time to full. Time-to-full projections assume the observed speed continues; they are not measured overflow dates or calibrated probabilities. These distributions pool cycles, so frequently visited bins carry more weight.</p>
      <div class="section-heading"><div><h3>Container filling patterns</h3><p>Up to 10 per view, with at least three positive ordinary cycles per container. Historical patterns do not establish current urgency.</p></div><UiSelect v-model="ranking" label="Filling pattern ranking" :options="rankings" :allow-empty="false" /></div>
      <UiTable :table-attrs="{ 'aria-label': 'Container filling pattern rankings' }" density="compact"><template #head><tr><th>Location</th><th>Collections / intervals</th><th>Numeric / lower-bound cycles</th><th>Zero / unknown cycles</th><th>Median cadence</th><th>Median rate</th><th>Estimated days to full</th></tr></template><tr v-for="row in rows" :key="`${row.locationId}:${row.material}`"><td><UiButton :label="row.locationId" mode="plain" @click="$emit('inspect', row.locationId)" /></td><td>{{ row.collections }} / {{ row.intervals }}</td><td>{{ row.numericCycles }} / {{ row.lowerBoundCycles }}</td><td>{{ row.zeroFillCycles }} / {{ row.unknownCycles }}</td><td>{{ number(row.medianIntervalDays) }} days</td><td>{{ number(row.medianRatePercentPerDay) }} pp/day</td><td>{{ number(row.medianDaysToFull) }}</td></tr><template #empty>No containers have enough positive ordinary cycles in this material by the selected cutoff.</template></UiTable>
    </template>
  </UiCard>
</template>
