<script setup lang="ts">
import { useId } from 'vue';
withDefaults(defineProps<{
  modelValue?: string | null;
  label: string;
  options: readonly {
    value: string;
    label: string;
  }[];
  listLabel?: string;
  disabled?: boolean;
  density?: string;
  allowEmpty?: boolean;
}>(), { allowEmpty: true });
defineEmits<{
  'update:modelValue': [value: string];
}>();
const id = useId();
</script>
<template>
  <div class="ui-field">
    <label :for="id">{{ label }}</label>
    <select
      :id="id"
      :value="modelValue ?? ''"
      :disabled="disabled"
      @change="$emit('update:modelValue', ($event.target as HTMLSelectElement).value)"
    >
      <option v-if="allowEmpty !== false && !options.some(option => option.value === '')" value="">
        All materials
      </option>
      <option v-for="option in options" :key="option.value" :value="option.value">
        {{ option.label }}
      </option>
    </select>
  </div>
</template>
