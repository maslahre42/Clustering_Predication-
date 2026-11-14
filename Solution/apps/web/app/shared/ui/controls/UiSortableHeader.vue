<script setup lang="ts">
import type { TableSortDirection } from '~/shared/domain/table';
defineProps<{
  label: string;
  active: boolean;
  direction: TableSortDirection;
}>();
defineEmits<{
  sort: [];
}>();
</script>
<template>
  <th :aria-sort="active ? (direction === 'asc' ? 'ascending' : 'descending') : 'none'">
    <button
      type="button"
      class="table-sort"
      :aria-label="`Sort by ${label}${active && direction === 'asc' ? ' descending' : ' ascending'}`"
      @click="$emit('sort')"
    >
      {{ label }} <span aria-hidden="true">{{ active ? (direction === 'asc' ? '↑' : '↓') : '↕' }}</span>
    </button>
  </th>
</template>
