<script setup lang="ts">
defineProps<{
    label: string;
    value: number | string;
    caption: string;
    compact?: boolean;
}>();
</script>
<template>
  <UiCard>
    <small>{{ label }}</small>
    <strong :class="{ 'metric-date': compact }">{{ value }}</strong>
    <span>{{ caption }}</span>
  </UiCard>
</template>
