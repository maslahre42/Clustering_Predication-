<script setup lang="ts">
import { HISTORY_PAGE_SIZE } from '~/shared/api/contracts/history';
import { historicalFillLabel } from '~/shared/domain/fill';
import type { HistoryPage, HistorySortField, SortDirection } from '~/shared/api/contracts/history';
defineProps<{
    history?: HistoryPage | null;
    loading?: boolean;
    sortBy: HistorySortField;
    sortDirection: SortDirection;
}>();
const page = defineModel<number>('page', { required: true });
defineEmits<{
    sort: [field: HistorySortField];
    select: [
        id: string
    ];
}>();
const columns: { field: HistorySortField; label: string }[] = [
  { field: 'date', label: 'Collection date' },
  { field: 'location', label: 'Location UUID' },
  { field: 'material', label: 'Glass fraction' },
  { field: 'fill', label: 'Fill before emptying' },
];
</script>
<template>
  <UiTable :table-attrs="{ 'aria-label': 'Historical pre-emptying observations' }" density="compact">
    <template #head>
      <tr>
        <UiSortableHeader
          v-for="column in columns"
          :key="column.field"
          :label="column.label"
          :active="sortBy === column.field"
          :direction="sortDirection"
          @sort="$emit('sort', column.field)"
        />
      </tr>
    </template>
    <tr v-for="(row, index) in history?.items" :key="`${row.locationId}:${row.material}:${row.date}:${index}`">
      <td class="mono">{{ row.date }}</td>
      <td>
        <UiButton :label="row.locationId.slice(0, 8)" :title="row.locationId" mode="plain" density="compact" @click="$emit('select', row.locationId)" />
      </td>
      <td>
        <GlassFractionBadge :material="row.material" />
      </td>
      <td class="numeric mono">{{ historicalFillLabel(row.fillLevelPercent, row.isOverfull) }}</td>
    </tr>
    <template #empty>No records match your filters and planning date.</template>
    <template #bottomLeft>{{ history?.total ?? 0 }} observations</template>
    <template #pagination>
      <UiPagination v-model="page" :pages="Math.max(1, Math.ceil((history?.total ?? 0) / HISTORY_PAGE_SIZE))" :disabled="loading" auto-compact />
    </template>
  </UiTable>
</template>
