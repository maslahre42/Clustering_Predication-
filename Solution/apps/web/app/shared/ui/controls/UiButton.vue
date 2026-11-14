<script setup lang="ts">
defineProps<{
  label: string;
  mode?: 'default' | 'outline' | 'plain';
  color?: string;
  disabled?: boolean;
  loading?: boolean;
  density?: string;
  type?: 'button' | 'submit' | 'reset';
}>();
</script>
<template>
  <button
    :type="type ?? 'button'"
    :disabled="disabled || loading"
    :aria-busy="loading || undefined"
    :class="['ui-button', `ui-button--${mode ?? 'default'}`, { 'ui-button--danger': color === 'danger' }]"
  >
    <span v-if="loading" class="ui-spinner" aria-hidden="true" />{{ label }}
  </button>
</template>
