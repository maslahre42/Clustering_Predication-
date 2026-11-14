<script setup lang="ts">
defineProps<{
  modelValue?: string;
  options: readonly {
    value: string;
    label: string;
  }[];
  name: string;
  density?: string;
}>();
defineEmits<{
  'update:modelValue': [value: string];
}>();
</script>
<template>
  <div class="ui-segmented-control" role="group" aria-label="Glass fraction">
    <button
      v-for="option in options"
      :key="option.value"
      type="button"
      :aria-pressed="modelValue === option.value"
      :class="[`segment-${option.value || 'all'}`, { 'is-active': modelValue === option.value }]"
      @click="$emit('update:modelValue', option.value)"
    >
      {{ option.label }}
    </button>
  </div>
</template>
