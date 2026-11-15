<script setup lang="ts">
import { computed } from 'vue';
import { historicalFillState } from '~/shared/domain/fill';
import { workspaceIcons } from '~/shared/ui/icons';
import { planningFillLabel, type PlanningViewBin } from '../domain/fillView';
const props = defineProps<{ bin?: PlanningViewBin; material: string }>();
const state = computed(() => historicalFillState(props.bin?.viewFillPercent, props.bin?.viewIsOverfull));
</script>
<template>
  <HistoricalFillMeter v-if="bin?.fillView === 'recorded'" :material="material" :value="bin.lastFillPercent" :date="bin.lastCollection" :overfull="bin.lastIsOverfull" />
  <div v-else :class="['fraction-meter', `fraction-${material}`, `reading-${state}`]" :title="bin ? `After recorded emptying on ${bin.lastCollection}. ${bin.lower != null && bin.upper != null ? `10–90% model range: ${bin.lower.toFixed(1)}–${bin.upper.toFixed(1)}%.` : ''}` : 'No record by cutoff'">
    <UiIcon class="fraction-bin-icon" :icon="workspaceIcons.bin" /><span class="fraction-material">{{ material }}</span><strong>{{ planningFillLabel(bin) }}</strong><small>{{ bin ? `${bin.viewState === 'emptied' ? 'Emptied' : 'Estimate for'} ${bin.viewDate}` : 'No record by cutoff' }}</small>
  </div>
</template>
