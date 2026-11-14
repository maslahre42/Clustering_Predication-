<script setup lang="ts">
import { useId } from 'vue';
defineProps<{
  modelValue?: string;
  label: string;
  autosize?: {
    min: number;
    max: number;
  };
}>();
defineEmits<{
  'update:modelValue': [value: string];
}>();
const id = useId();
</script>
<template>
  <div class="ui-field ui-textarea">
    <label :for="id">{{ label }}</label>
    <textarea
      :id="id"
      :rows="autosize?.min ?? 3"
      :value="modelValue"
      @input="$emit('update:modelValue', ($event.target as HTMLTextAreaElement).value)"
    />
  </div>
</template>
