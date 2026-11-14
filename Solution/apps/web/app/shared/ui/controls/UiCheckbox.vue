<script setup lang="ts">
import { useId } from 'vue';
defineProps<{
  modelValue?: boolean;
  label: string;
  value?: string;
  indeterminate?: boolean;
  hideLabel?: boolean;
  disabled?: boolean;
  density?: string;
}>();
defineEmits<{
  'update:modelValue': [value: boolean];
}>();
const id = useId();
</script>
<template>
  <label class="ui-checkbox" :for="id">
    <input
      :id="id"
      type="checkbox"
      :checked="modelValue"
      :indeterminate="indeterminate"
      :aria-checked="indeterminate ? 'mixed' : modelValue"
      :disabled="disabled"
      @change="$emit('update:modelValue', ($event.target as HTMLInputElement).checked)"
    />
    <span :class="{ 'sr-only': hideLabel }">{{ label }}</span>
  </label>
</template>
