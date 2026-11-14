<script setup lang="ts">
defineProps<{
  label: string;
  color?: string;
  icon?: string;
  density?: string;
}>();
</script>
<template>
  <span :class="['ui-tag', `ui-tag--${color ?? 'neutral'}`]">
    <UiIcon v-if="icon" :icon="icon" />{{ label }}
  </span>
</template>
