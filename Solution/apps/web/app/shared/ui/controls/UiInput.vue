<script setup lang="ts">
import { useId } from 'vue';
defineProps<{
  modelValue?: string | null;
  label: string;
  type?: string;
  placeholder?: string;
  disabled?: boolean;
  density?: string;
}>();
defineEmits<{
  'update:modelValue': [value: string];
}>();
const id = useId();
</script>
<template>
  <div class="ui-field">
    <label :for="id">{{ label }}</label>
    <input
      :id="id"
      :type="type ?? 'text'"
      :value="modelValue ?? ''"
      :placeholder="placeholder"
      :disabled="disabled"
      @input="$emit('update:modelValue', ($event.target as HTMLInputElement).value)"
    />
  </div>
</template>
