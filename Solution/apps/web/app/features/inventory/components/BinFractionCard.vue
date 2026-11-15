<script setup lang="ts">
import { computed } from 'vue';
import { planningFillLabel } from '~/features/planning/domain/fillView';
import type { PlanningBin } from '~/features/inventory/types';
const props = defineProps<{
    bin?: PlanningBin;
    material: string;
}>();
const { viewBins, fillView } = usePlanningFilters();
const displayed = computed(() => viewBins.value.find(bin => bin.key === props.bin?.key));
const { selectedKeys, toggleBin } = useCollectionPlan();
</script>
<template>
  <UiCard :class="['bin-fraction-card', `fraction-${material}`]">
    <GlassFractionBadge :material="material" />
    <strong class="fraction-large">{{ planningFillLabel(displayed) }}</strong>
    <PlanningFillMeter :material="material" :bin="displayed" />
    <dl>
      <dt>Measurement</dt>
      <dd>{{ fillView === 'estimate' ? 'Selected-day estimate after emptying' : 'Before emptying' }}</dd>
      <dt>Last recorded before emptying</dt><dd>{{ bin?.lastIsOverfull ? 'Overfull' : bin?.lastFillPercent == null ? 'Unknown' : `${bin.lastFillPercent}%` }}</dd>
      <dt>Last collection</dt>
      <dd>{{ bin?.lastCollection ?? 'No record by cutoff' }}</dd>
      <dt>Known collections</dt>
      <dd>{{ bin?.collections ?? 0 }}</dd>
    </dl>
    <UiButton :label="bin && selectedKeys.includes(bin.key) ? 'Remove from plan' : 'Select for plan'" :disabled="!bin" :mode="bin && selectedKeys.includes(bin.key) ? 'outline' : 'default'" @click="bin && toggleBin(bin.key, !selectedKeys.includes(bin.key))" />
  </UiCard>
</template>
