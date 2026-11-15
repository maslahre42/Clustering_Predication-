<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount } from 'vue';
import type { CollectionProposal } from '~/shared/api/contracts/proposal';
import { PRESENTATION_SLIDES, nextSlide, missedUrgent } from '../domain/insights';
const props = defineProps<{ proposal: CollectionProposal; baseline: CollectionProposal | null }>();
const emit = defineEmits<{ close: []; export: [] }>();
const dialog = ref<HTMLDialogElement | null>(null), slide = ref(0);
onMounted(() => dialog.value?.showModal?.());
onBeforeUnmount(() => dialog.value?.close?.());
function navigate(event: KeyboardEvent) {
  if (['INPUT','SELECT','TEXTAREA'].includes((event.target as HTMLElement | null)?.tagName ?? '')) return;
  if (event.key === 'ArrowRight' || event.key === 'ArrowLeft') {
    event.preventDefault(); slide.value = nextSlide(slide.value,event.key === 'ArrowRight' ? 1 : -1);
  }
}
</script>
<template>
  <dialog ref="dialog" class="plan-presentation" aria-labelledby="presentation-title" @cancel.prevent="emit('close')" @keydown="navigate">
    <header><span class="eyebrow">CHALLENGE DEMO · {{ slide+1 }} / {{ PRESENTATION_SLIDES.length }}</span><button type="button" aria-label="Close presentation" @click="emit('close')">Close ×</button></header>
    <h2 id="presentation-title">{{ PRESENTATION_SLIDES[slide] }}</h2>
    <div class="presentation-content" aria-live="polite">
      <template v-if="slide === 0"><p class="presentation-lead">Collect the glass that needs service, with less unnecessary driving.</p><p>{{ proposal.model.bins }} containers · {{ proposal.dataset?.rows ?? 'Unknown' }} recorded readings · history through {{ proposal.asOf }}.</p><p>This proposal serves {{ proposal.plan.totals.stops }} sites with {{ proposal.plan.totals.trucks }} trucks on {{ proposal.planDate }}.</p><p>{{ missedUrgent(proposal) }} urgent sites remain unserved. Capacity, working hours and road access constrain the result.</p></template>
      <template v-else-if="slide === 1"><p>Each recorded collection resets the container. The forecast learns filling rates from completed cycles; full readings are lower bounds and unknown readings supply no numeric fill.</p><p>{{ proposal.model.cycles }} completed cycles · {{ proposal.model.censoredCycles }} censored cycles. Future readings are excluded.</p><FillTimingTable :rows="proposal.fillTiming ?? []" /></template>
      <template v-else-if="slide === 2"><p>{{ proposal.plan.totals.distanceKm?.toFixed(1) ?? 'Unknown' }} km on streets · {{ proposal.plan.totals.trips }} loads · {{ proposal.plan.totals.hours.toFixed(1) }} truck-hours. Each truck keeps a service sector across its loads.</p><ProposalRouteMap :proposal="proposal" :locations="[]" /></template>
      <OperatingCosts v-else-if="slide === 3" :costs="proposal.costs" />
      <ScenarioComparison v-else-if="slide === 4" :proposal="proposal" :baseline="baseline" readonly />
      <template v-else><p>Forecasts and simulated differences are planning estimates. The route sheet records this plan for review before dispatch.</p><p>Dataset: {{ proposal.dataset?.source ?? 'Unavailable' }} · fingerprint {{ proposal.dataset?.fingerprint ?? 'Unavailable' }}.</p><p>Distance source: {{ proposal.routing?.provider ?? 'Unavailable' }} · {{ proposal.routing?.profile ?? 'Unavailable' }}.</p><p>Configured compartments: brown {{ proposal.settings.brownCompartmentM3 || 'unknown' }} m³, green {{ proposal.settings.greenCompartmentM3 || 'unknown' }} m³, white {{ proposal.settings.whiteCompartmentM3 || 'unknown' }} m³.</p><ul><li v-for="text in proposal.assumptions" :key="text">{{ text }}</li></ul><UiButton label="Download route sheet (CSV)" @click="emit('export')" /></template>
    </div>
    <footer><button type="button" :disabled="slide === 0" @click="slide = nextSlide(slide,-1)">Previous slide</button><span>{{ slide+1 }} / {{ PRESENTATION_SLIDES.length }} · Arrow keys to navigate · Esc to close</span><button type="button" :disabled="slide === PRESENTATION_SLIDES.length-1" @click="slide = nextSlide(slide,1)">Next slide</button></footer>
  </dialog>
</template>
