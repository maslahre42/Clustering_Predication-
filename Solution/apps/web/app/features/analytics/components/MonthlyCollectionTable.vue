<script setup lang="ts">
import { toRef } from 'vue';
import type { MonthlyAnalytics } from '~/shared/api/contracts/analytics';
import { GLASS_OPTIONS } from '~/shared/config/materials';
import { MONTHLY_COLUMNS } from '../config/tableColumns';
import { createMonthlyTable } from '../state/createMonthlyTable';

const props = defineProps<{ months: MonthlyAnalytics[] }>();
const { material, page, pages, rows, sortBy, sortDirection, sort } = createMonthlyTable(toRef(props, 'months'));
</script>
<template>
  <div>
    <div class="section-heading">
      <div>
        <h2>Monthly collection comparison</h2>
        <p>The last month may be partial at your selected cutoff. These are collection-event statistics, not network-wide daily fill estimates.</p>
      </div>
      <UiSelect v-model="material" label="Glass fraction" list-label="Glass fractions" :options="GLASS_OPTIONS" density="compact" />
    </div>
    <UiTable :table-attrs="{ 'aria-label': 'Monthly historical collection statistics' }" density="compact">
      <template #head>
        <tr>
          <UiSortableHeader
            v-for="column in MONTHLY_COLUMNS"
            :key="column.field"
            :label="column.label"
            :active="sortBy === column.field"
            :direction="sortDirection"
            @sort="sort(column.field)"
          />
        </tr>
      </template>
      <tr v-for="row in rows" :key="`${row.month}:${row.material}`">
        <td>{{ row.month }}</td>
        <td>
          <GlassFractionBadge :material="row.material" />
        </td>
        <td>{{ row.collections }}</td>
        <td>{{ row.overfullCount }}</td>
        <td>
          {{ row.meanNumericFill == null ? '—' : `${row.meanNumericFill.toFixed(1)}%` }}
          <small>n={{ row.numericReadings }}</small>
        </td>
      </tr>
      <template #empty>No monthly records at this cutoff.</template>
      <template #pagination>
        <UiPagination v-model="page" :pages="pages" />
      </template>
    </UiTable>
  </div>
</template>
