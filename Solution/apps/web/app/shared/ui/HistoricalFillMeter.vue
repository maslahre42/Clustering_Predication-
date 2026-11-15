<script setup lang="ts">
import { computed } from 'vue';
import { historicalFillLabel, historicalFillState } from '~/shared/domain/fill';
import { workspaceIcons } from '~/shared/ui/icons';
const props = defineProps<{
    value: number | null;
    material: string;
    date?: string;
    overfull?: boolean;
}>();
const state = computed(() => historicalFillState(props.value, props.overfull));
</script>
<template>
  <div :class="['fraction-meter', `fraction-${material}`, `reading-${state}`]">
    <UiIcon class="fraction-bin-icon" :icon="workspaceIcons.bin" />
    <span class="fraction-material">{{ material }}</span>
    <strong>{{ state === 'unknown' ? 'Unknown' : historicalFillLabel(value, overfull) }}</strong>
    <small v-if="date">{{ date }}</small>
    <small v-else>No record by cutoff</small>
  </div>
</template>
