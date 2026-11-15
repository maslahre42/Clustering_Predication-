<script setup lang="ts">
import { computed, onScopeDispose, ref, toRef } from 'vue';
import type { Location } from '~/shared/api/contracts/locations';
import type { ProposalSettings } from '~/shared/api/contracts/proposal';
import type { ProposalDataset } from '~/shared/api/contracts/comparison';
import type { CapacityResult, GlassType } from '~/shared/api/contracts/capacity';
import { API_ROUTES } from '~/shared/api/routes';
import { createCapacityPlanning, type CapacityPlanningCache } from '../state/createCapacityPlanning';
import { CAPACITY_MATERIALS } from '../domain/capacity';
import { euro } from '../domain/insights';
const props = defineProps<{ locations?: Location[]; asOf: string; settings: ProposalSettings; dataset: ProposalDataset | null; dirty: boolean; bins: { locationId: string; material: string }[] }>();
const cached = useState<CapacityPlanningCache | null>('joint-planning-result-v1', () => null);
const state = createCapacityPlanning(toRef(props, 'asOf'), toRef(props, 'settings'), toRef(props, 'dataset'), toRef(props, 'dirty'),
  (query, body, signal) => $fetch<CapacityResult>(API_ROUTES['capacity-scenario'], { method: 'POST', query, body, signal, timeout: body.optimize ? 500000 : 240000 }), cached);
onScopeDispose(state.dispose);
const { input, result, pending, error } = state;
const sites = computed(() => [...new Set(props.bins.map(b => b.locationId))].sort());
const selectedSite = ref('');
const selectedMaterial = ref<GlassType>('white');
const siteMaximum = ref(9);
const overrideAvailable = computed(() => props.bins.some(b => b.locationId === selectedSite.value && b.material === selectedMaterial.value)
  && !input.value.overrides.some(r => r.locationId === selectedSite.value && r.material === selectedMaterial.value));

</script>
<template>
  <UiCard id="capacity-planning" class="analytics-panel capacity-planning">
    <p class="eyebrow">CONTAINERS → FREQUENCY → FINANCIAL COST</p>
    <h2>Optimize containers & collection frequency</h2>
    <p>Choose container counts and collection dates automatically, or compare two manual scenarios, using the same incoming glass demand. Review filling time, paid truck shifts and financial cost.</p>
    <p class="data-note">Counts apply to each site where that glass type has history. The source has no physical container inventory: baseline counts are explicit assumptions. Manual comparisons start empty. Automatic recommendations use a repeating cycle with matching start/end stock. Neither changes the database or your active route plan.</p>
    <div class="capacity-controls">
      <label>Comparison period (days)<input v-model.number="input.days" type="number" min="7" max="31" /></label>
      <label>Baseline collection interval (days)<input v-model.number="input.baselineIntervalDays" type="number" min="1" max="28" /></label>
      <label>Alternative collection interval (days)<input v-model.number="input.alternativeIntervalDays" type="number" min="1" max="28" /></label>
      <label>Cost per container per month (€)<input v-model.number="input.containerCostPerMonthEuro" type="number" min="0" max="10000" step="0.01" /></label>
    </div>
    <p>Intervals are calendar days: 7 = weekly; 14 = every two weeks. Sites are staggered across the interval. Due visits wait for an operating weekday; missed visits retry.</p>
    <div class="table-scroll"><table class="insights-table"><thead><tr><th>Containers at each site</th><th>Baseline</th><th>Manual alternative</th></tr></thead><tbody>
      <tr v-for="material in CAPACITY_MATERIALS" :key="material"><th>{{ material }} glass</th><td><input v-model.number="input.baselineContainers[material]" type="number" min="1" max="20" :aria-label="`Baseline ${material} containers per site`" /></td><td><input v-model.number="input.alternativeContainers[material]" type="number" min="1" max="20" :aria-label="`Alternative ${material} containers per site`" /></td></tr>
    </tbody></table></div>
    <details class="proposal-disclosure"><summary>Change containers at a particular site</summary>
      <div class="capacity-controls"><label>Override site<select aria-label="Override site" :value="selectedSite" @change="selectedSite = ($event.target as HTMLSelectElement).value"><option value="">Choose a site</option><option v-for="site in sites" :key="site" :value="site">{{ site }}</option></select></label><label>Override glass type<select aria-label="Override glass type" :value="selectedMaterial" @change="selectedMaterial = ($event.target as HTMLSelectElement).value as GlassType"><option v-for="material in CAPACITY_MATERIALS" :key="material" :value="material">{{ material }}</option></select></label><UiButton label="Add site override" mode="outline" :disabled="!overrideAvailable" @click="state.addOverride(selectedSite, selectedMaterial, bins)" /></div>
      <p>Overrides replace the global count for this site and type. Choose a glass type present in the site's history.</p>
      <div v-if="input.overrides.length" class="table-scroll"><table class="insights-table"><thead><tr><th>Site / type</th><th>Baseline</th><th>Manual alternative</th><th>Action</th></tr></thead><tbody><tr v-for="(row, i) in input.overrides" :key="`${row.locationId}:${row.material}`"><th>{{ row.locationId }} · {{ row.material }}</th><td><input v-model.number="row.baselineCount" type="number" min="1" max="20" :aria-label="`Baseline override ${row.locationId} ${row.material}`" /></td><td><input v-model.number="row.alternativeCount" type="number" min="1" max="20" :aria-label="`Alternative override ${row.locationId} ${row.material}`" /></td><td><UiButton label="Remove override" mode="plain" @click="input.overrides.splice(i,1)" /></td></tr></tbody></table></div>
    </details>
    <h3>Find the best container counts and schedule automatically</h3>
    <p>Use baseline counts as the assumed current inventory. The search chooses counts and dates for each glass type, combines same-site collections, and checks daily street routes. The manual alternative counts above are not constraints on the automatic search.</p>
    <div class="capacity-controls">
      <label>Repeating cycle (weeks)<input v-model.number="input.optimizationWeeks" type="number" min="1" max="8" /></label>
      <label>Maximum fill target (%)<input v-model.number="input.targetFillPercent" type="number" min="50" max="100" /></label>
      <label>Maximum containers per site and type<input v-model.number="input.maxContainersPerType" type="number" min="1" max="20" /></label>
      <label>Maximum total containers per site<input v-model.number="input.maxContainersPerSite" type="number" min="1" max="60" /></label>
      <label>Minimum collection gap (days)<input v-model.number="input.minIntervalDays" type="number" min="1" max="56" /></label>
      <label>Maximum collection gap (days)<input v-model.number="input.maxIntervalDays" type="number" min="1" max="56" /></label>
    </div>
    <p>Default 90% target leaves a 10% modelled buffer. Container limits are scenario assumptions until verified; the longest interval searched cannot exceed the repeating cycle.</p>
    <details class="proposal-disclosure"><summary>Set a physical space limit for one site</summary><div class="capacity-controls"><label>Site for physical space limit<select aria-label="Site for physical space limit" :value="selectedSite" @change="selectedSite = ($event.target as HTMLSelectElement).value"><option value="">Choose a site</option><option v-for="site in sites" :key="site" :value="site">{{ site }}</option></select></label><label>Site maximum total containers<input v-model.number="siteMaximum" type="number" min="1" max="60" /></label><UiButton label="Set site space limit" mode="outline" :disabled="!selectedSite" @click="state.setSiteLimit(selectedSite, siteMaximum)" /></div><div v-for="(limit,i) in input.siteLimits" :key="limit.locationId"><span>{{ limit.locationId }} · maximum {{ limit.maxContainers }} containers</span><UiButton label="Remove site space limit" mode="plain" @click="input.siteLimits.splice(i,1)" /></div></details>
    <UiButton :label="pending ? 'Finding a feasible joint plan…' : 'Find best containers & schedule'" :disabled="pending || dirty" @click="state.run(true)" />
    <p>Applied truck-day package: <strong>{{ settings.fixedTruckCostEuro > 0 ? euro(settings.fixedTruckCostEuro) : 'Unpriced' }}/truck-day</strong> · additional distance charge: {{ settings.costPerKmEuro > 0 ? `${euro(settings.costPerKmEuro)}/km` : settings.fixedTruckCostEuro > 0 ? 'Included in truck-day package' : 'Unpriced' }}. Edit these in Collection settings above. The daily package includes truck, driver and driving kilometres. Container cost 0 means unpriced. Do not include the same expense in multiple rates.</p>
    <p v-if="dirty" role="status">Apply your collection settings before comparing.</p>
    <UiButton :label="pending ? 'Comparing daily street routes…' : 'Compare financial impact'" :disabled="pending || dirty" @click="state.run(false)" />
    <p v-if="pending" role="status">Routing both schedules with the same demand and fleet constraints. This may take a few minutes; a shorter comparison runs faster.</p>
    <p v-if="error" role="alert">{{ error }}</p>
    <JointPlanningResults v-if="result?.optimization" :result="result" :locations="locations ?? []" />
    <CapacityResults v-if="result && (!result.optimization || result.scenarios.length > 1)" :result="result" />
  </UiCard>
</template>
