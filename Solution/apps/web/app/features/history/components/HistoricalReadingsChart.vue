<script setup lang="ts">
import type { Observation } from '~/shared/api/contracts/history';
const props = defineProps<{
    observations: Observation[];
}>();
const points = computed(() => props.observations.filter(o => o.fillLevelPercent !== null).map(o => ({ ...o, timestamp: Date.parse(`${o.date}T00:00:00Z`) })));
const min = computed(() => Math.min(...points.value.map(p => p.timestamp)));
const max = computed(() => Math.max(...points.value.map(p => p.timestamp)));
const colors: Record<string, string> = { brown: 'var(--fraction-brown)', green: 'var(--fraction-green)', white: 'var(--fraction-white)' };
function x(time: number) { return min.value === max.value ? 460 : 55 + (time - min.value) / (max.value - min.value) * 810; }
</script>
<template>
  <div class="readings-chart">
    <div class="chart-legend">
      <GlassFractionBadge v-for="color in ['brown', 'green', 'white']" :key="color" :material="color" />
    </div>
    <svg v-if="points.length" viewBox="0 0 920 250" role="img" aria-label="Actual pre-emptying fill observations by date. Dots are individual readings, not a continuous fill estimate.">
      <g v-for="value in [0, 25, 50, 75, 100]" :key="value">
        <line x1="55" x2="865" :y1="210 - value * 1.7" :y2="210 - value * 1.7" stroke="#dce3e7" />
        <text x="12" :y="214 - value * 1.7" fill="#60707a" font-size="11">{{ value }}%</text>
      </g>
      <circle v-for="(point, i) in points" :key="i" :cx="x(point.timestamp)" :cy="210 - point.fillLevelPercent! * 1.7" r="4" :fill="colors[point.material] ?? '#536572'">
        <title>{{ point.date }} · {{ point.material }} · {{ point.fillLevelPercent }}% before emptying</title>
      </circle>
      <text x="55" y="240" fill="#60707a" font-size="11">{{ new Date(min).toISOString().slice(0, 10) }}</text>
      <text x="865" y="240" text-anchor="end" fill="#60707a" font-size="11">{{ new Date(max).toISOString().slice(0, 10) }}</text>
    </svg>
    <p v-else>No numeric readings available for this location.</p>
    <p v-if="observations.some(o => o.isOverfull)" class="caption">{{ observations.filter(o => o.isOverfull).length }} overfull observations are listed in history but not plotted as invented percentages.</p>
    <p class="caption">Individual pre-emptying observations. No interpolation, sensor readings, or forecast values are implied.</p>
  </div>
</template>
