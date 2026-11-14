<script setup lang="ts">
import { workspaceIcons } from '~/shared/ui/icons';
defineProps<{
    material: string;
}>();
</script>
<template>
  <UiTag :label="`${material} glass`" :icon="workspaceIcons.recycling" :class="['fraction-badge', `fraction-${material}`]" density="compact" />
</template>
