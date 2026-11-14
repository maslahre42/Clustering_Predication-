<script setup lang="ts">
import { computed } from 'vue';
import { paginationItems } from '../../domain/pagination';
const props = defineProps<{
  modelValue: number;
  pages: number;
  disabled?: boolean;
  autoCompact?: boolean;
}>();
const emit = defineEmits<{
  'update:modelValue': [value: number];
}>();
const items = computed(() => paginationItems(props.modelValue, props.pages));
function go(page: number) { if (!props.disabled && page >= 1 && page <= props.pages)
  emit('update:modelValue', page); }
</script>
<template>
  <nav class="ui-pagination" aria-label="Pagination">
    <button type="button" aria-label="Previous page" :disabled="disabled || modelValue <= 1" @click="go(modelValue - 1)">
      ‹
    </button>
    <template v-for="(item, index) in items" :key="index">
      <span v-if="item === '…'" class="ui-page-gap">…</span>
      <button
        v-else
        type="button"
        :aria-label="`Page ${item}`"
        :aria-current="item === modelValue ? 'page' : undefined"
        :disabled="disabled"
        @click="go(item)"
      >
        {{ item }}
      </button>
    </template>
    <button type="button" aria-label="Next page" :disabled="disabled || modelValue >= pages" @click="go(modelValue + 1)">
      ›
    </button>
  </nav>
</template>
