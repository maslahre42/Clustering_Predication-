<script setup lang="ts">
defineProps<{
  label: string;
  icon: string;
  disabled?: boolean;
  color?: string;
  density?: string;
}>();
</script>
<template>
  <button
    type="button"
    class="ui-icon-button"
    :aria-label="label"
    :title="label"
    :disabled="disabled"
  >
    <UiIcon :icon="icon" />
  </button>
</template>
