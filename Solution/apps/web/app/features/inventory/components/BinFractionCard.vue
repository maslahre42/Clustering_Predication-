<script setup lang="ts">
import { historicalFillLabel } from '~/shared/domain/fill';
import type { PlanningBin } from '~/features/inventory/types';
defineProps<{
    bin?: PlanningBin;
    material: string;
}>();
const { selectedKeys, toggleBin } = useCollectionPlan();
</script>
<template>
  <UiCard :class="['bin-fraction-card', `fraction-${material}`]">
    <GlassFractionBadge :material="material" />
    <strong class="fraction-large">{{ historicalFillLabel(bin?.lastFillPercent, bin?.lastIsOverfull) }}</strong>
    <HistoricalFillMeter :material="material" :value="bin?.lastFillPercent ?? null" :date="bin?.lastCollection" :overfull="bin?.lastIsOverfull" />
    <dl>
      <dt>Measurement</dt>
      <dd>Before emptying</dd>
      <dt>Last collection</dt>
      <dd>{{ bin?.lastCollection ?? 'No record by cutoff' }}</dd>
      <dt>Known collections</dt>
      <dd>{{ bin?.collections ?? 0 }}</dd>
    </dl>
    <UiButton :label="bin && selectedKeys.includes(bin.key) ? 'Remove from plan' : 'Select for plan'" :disabled="!bin" :mode="bin && selectedKeys.includes(bin.key) ? 'outline' : 'default'" @click="bin && toggleBin(bin.key, !selectedKeys.includes(bin.key))" />
  </UiCard>
</template>
