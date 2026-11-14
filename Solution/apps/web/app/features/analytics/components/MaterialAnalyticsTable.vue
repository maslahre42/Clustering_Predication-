<script setup lang="ts">
import { toRef } from 'vue';
import type { MaterialAnalytics } from '~/shared/api/contracts/analytics';
import { GLASS_OPTIONS } from '~/shared/config/materials';
import { MATERIAL_COLUMNS } from '../config/tableColumns';
import { createMaterialTable } from '../state/createMaterialTable';

const props = defineProps<{ materials: MaterialAnalytics[] }>();
const { material, rows, sortBy, sortDirection, sort } = createMaterialTable(toRef(props, 'materials'));
</script>
<template>
  <div>
    <div class="analytics-table-filter">
      <UiSelect v-model="material" label="Glass fraction" :options="GLASS_OPTIONS" density="compact" />
    </div>
    <UiTable :table-attrs="{ 'aria-label': 'Historical material collection statistics' }" density="compact">
      <template #head>
        <tr>
          <UiSortableHeader
            v-for="column in MATERIAL_COLUMNS"
            :key="column.field"
            :label="column.label"
            :active="sortBy === column.field"
            :direction="sortDirection"
            @sort="sort(column.field)"
          />
        </tr>
      </template>
      <tr v-for="row in rows" :key="row.material">
        <td>
          <GlassFractionBadge :material="row.material" />
        </td>
        <td>{{ row.collections }}</td>
        <td>
          {{ row.overfullCount }}
          <small>({{ row.collections ? (row.overfullCount / row.collections * 100).toFixed(1) : '0.0' }}%)</small>
        </td>
        <td>
          {{ row.meanNumericFill == null ? '—' : `${row.meanNumericFill.toFixed(1)}%` }}
          <small>n={{ row.numericReadings }}</small>
        </td>
        <td>
          {{ row.medianIntervalDays == null ? '—' : `${row.medianIntervalDays} days` }}
          <small>n={{ row.intervalCount }} gaps</small>
        </td>
        <td>{{ row.distribution.low0To30 }}</td>
        <td>{{ row.unknownCount }}</td>
      </tr>
      <template #empty>No records match this glass fraction.</template>
    </UiTable>
  </div>
</template>
