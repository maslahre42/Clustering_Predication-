<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import type { BinFillTiming } from '~/shared/api/contracts/proposal';
import { timingRows, daysLabel } from '../domain/insights';
const props = defineProps<{ rows: BinFillTiming[] }>();
const search = ref(''), material = ref(''), page = ref(0);
const filtered = computed(() => timingRows(props.rows,search.value,material.value));
const visible = computed(() => filtered.value.slice(page.value*12,page.value*12+12));
watch([search,material,() => props.rows],() => { page.value=0 });
</script>
<template>
  <section class="surface analytics-panel" aria-label="Estimated time to full">
    <h2>When might each container become full?</h2>
    <p>Days are relative to the history cutoff. The middle estimate and 10–90% model range approximate seasonal filling from the last recorded emptying. These ranges are uncalibrated estimates; the collection rule still uses overflow risk, working days and available capacity.</p>
    <div class="proposal-actions insight-filters"><label>Search location<input aria-label="Search location" :value="search" @input="search = ($event.target as HTMLInputElement).value" type="search" /></label><label>Glass type<select aria-label="Glass type" :value="material" @change="material = ($event.target as HTMLSelectElement).value"><option value="">All glass</option><option value="brown">Brown</option><option value="green">Green</option><option value="white">White</option></select></label></div>
    <div class="table-scroll"><table class="insights-table"><thead><tr><th>Location / glass</th><th>Last emptied</th><th>Middle estimate</th><th>Estimated full date</th><th>10–90% range (days)</th><th>Completed cycles</th></tr></thead><tbody><tr v-for="row in visible" :key="`${row.locationId}:${row.material}`"><td>{{ row.locationId }} · {{ row.material }}</td><td>{{ row.lastEmptied }}</td><td>{{ daysLabel(row.medianDaysUntilFull) }}</td><td>{{ row.predictedFullDate ?? 'Unavailable' }}</td><td>{{ row.earlyDaysUntilFull == null ? 'Unavailable' : `${row.earlyDaysUntilFull.toFixed(1)} to ${row.lateDaysUntilFull?.toFixed(1)}` }}</td><td>{{ row.historyCycles }} ({{ row.censoredCycles }} lower bounds)<span v-if="row.reason"> · {{ row.reason === 'no_completed_cycles' ? 'No completed cycles for this container' : 'Outside supported model range' }}</span></td></tr></tbody></table></div>
    <p v-if="!filtered.length">No matching containers.</p>
    <div class="proposal-actions"><button type="button" :disabled="page === 0" @click="page--">Previous containers</button><span>{{ filtered.length ? page*12+1 : 0 }}–{{ Math.min((page+1)*12,filtered.length) }} of {{ filtered.length }}</span><button type="button" :disabled="(page+1)*12 >= filtered.length" @click="page++">Next containers</button></div>
  </section>
</template>
