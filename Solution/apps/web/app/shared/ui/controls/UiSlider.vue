<script setup lang="ts">
import { useId } from 'vue';
defineProps<{
  modelValue: number;
  min: number;
  max: number;
  step: number;
  label: string;
  valueText?: string;
  density?: string;
}>();
defineEmits<{
  'update:modelValue': [value: number];
}>();
const id = useId();
</script>
<template>
  <div class="ui-field ui-slider">
    <label :for="id">{{ label }}</label>
    <input
      :id="id"
      type="range"
      :value="modelValue"
      :min="min"
      :max="max"
      :step="step"
      :aria-valuetext="valueText ?? `${modelValue}%`"
      @input="$emit('update:modelValue', Number(($event.target as HTMLInputElement).value))"
    />
  </div>
</template>
