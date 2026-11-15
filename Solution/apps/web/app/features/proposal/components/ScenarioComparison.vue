<script setup lang="ts">
import { computed } from 'vue';
import type { CollectionProposal } from '~/shared/api/contracts/proposal';
import { compareScenarios, euro, missedUrgent } from '../domain/insights';
const props = defineProps<{ proposal: CollectionProposal; baseline: CollectionProposal | null; dirty?: boolean; readonly?: boolean }>();
defineEmits<{ save: []; clear: [] }>();
const comparison = computed(() => props.baseline ? compareScenarios(props.baseline,props.proposal) : null);
const plans = computed(() => props.baseline ? [props.baseline,props.proposal] : []);
</script>
<template>
  <section class="surface analytics-panel" aria-label="Compare planning scenarios">
    <h2>Compare planning scenarios</h2>
    <p>Save this plan as a baseline, change fleet size, payload, compartments, shift or collection thresholds above, then apply to calculate the alternative. Both plans show completed service beside distance and cost.</p>
    <div v-if="!readonly" class="proposal-actions"><UiButton label="Save current plan as baseline" :disabled="dirty" @click="$emit('save')" /><UiButton v-if="baseline" label="Clear baseline" mode="outline" @click="$emit('clear')" /></div>
    <p v-if="dirty" role="status">Apply your changes to compare the calculated alternative.</p>
    <template v-else-if="baseline && comparison">
      <div class="table-scroll"><table class="insights-table"><thead><tr><th>Outcome / constraint</th><th>Saved baseline</th><th>Current plan</th></tr></thead><tbody>
        <tr><th>Fleet available / payload / shift</th><td v-for="(p,i) in plans" :key="i">{{ p.settings.maxVehicles }} / {{ p.settings.truckPayloadT }} t / {{ p.settings.shiftHours }} h</td></tr>
        <tr><th>Brown / green / white compartments</th><td v-for="(p,i) in plans" :key="i">{{ p.settings.brownCompartmentM3 || 'Unknown' }} / {{ p.settings.greenCompartmentM3 || 'Unknown' }} / {{ p.settings.whiteCompartmentM3 || 'Unknown' }} m³</td></tr>
        <tr><th>Urgent risk threshold</th><td v-for="(p,i) in plans" :key="i">{{ (p.settings.mustProbability*100).toFixed(0) }}%</td></tr>
        <tr><th>Road km</th><td v-for="(p,i) in plans" :key="i">{{ p.plan.totals.distanceKm?.toFixed(1) ?? 'Unavailable' }}</td></tr>
        <tr><th>Scheduled trucks / loads</th><td v-for="(p,i) in plans" :key="i">{{ p.plan.totals.trucks }} / {{ p.plan.totals.trips }}</td></tr>
        <tr><th>Working hours</th><td v-for="(p,i) in plans" :key="i">{{ p.plan.totals.hours.toFixed(1) }}</td></tr>
        <tr><th>Containers collected</th><td v-for="(p,i) in plans" :key="i">{{ p.plan.totals.bins }}</td></tr>
        <tr><th>Missed urgent sites</th><td v-for="(p,i) in plans" :key="i">{{ missedUrgent(p) }}</td></tr>
        <tr><th>Additional €/km / package €/day</th><td v-for="(p,i) in plans" :key="i">{{ p.settings.costPerKmEuro || (p.settings.fixedTruckCostEuro > 0 ? 'Driving included' : 'Unpriced') }} / {{ p.settings.fixedTruckCostEuro || 'Unpriced' }}</td></tr>
        <tr><th>Estimated cost</th><td v-for="(p,i) in plans" :key="i">{{ euro(p.costs?.totalEuro) }}{{ p.costs?.partial ? ' (partial)' : '' }}</td></tr>
      </tbody></table></div>
      <p v-if="comparison.comparable">Matched completed service. Road-distance reduction: {{ comparison.savedKm?.toFixed(1) ?? 'Unavailable' }} km. Estimated cost reduction: {{ euro(comparison.savedEuro) }}{{ proposal.costs?.partial ? ' (partial cost categories)' : '' }}. Negative values mean an increase. These are modelled differences, not measured savings.</p>
      <div v-else role="status"><p>Trade-offs only; a savings claim is unavailable:</p><ul><li v-for="reason in comparison.reasons" :key="reason">{{ reason }}</li></ul></div>
    </template>
    <p v-else>No baseline saved. Baselines are cleared when the date or dataset changes.</p>
  </section>
</template>
