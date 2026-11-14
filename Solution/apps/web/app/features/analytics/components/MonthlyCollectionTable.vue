<script setup lang="ts">
import { toRef } from 'vue';
import type { MonthlyAnalytics } from '~/shared/api/contracts/analytics';
import { GLASS_OPTIONS } from '~/shared/config/materials';
import { MONTHLY_COLUMNS } from '../config/tableColumns';
import { createMonthlyTable } from '../state/createMonthlyTable';
import { monthCoverage } from '../domain/patterns';

const props = defineProps<{ months: MonthlyAnalytics[]; asOf: string; firstDate?: string | null }>();
const { material, page, pages, rows, sortBy, sortDirection, sort } = createMonthlyTable(toRef(props, 'months'));
</script>
<template>
  <div>
    <div class="section-heading">
      <div>
        <h2>Monthly collection comparison</h2>
        <p>Collections recorded through {{ asOf }} (the date selected at the top). Partial months show only the available period. Counts are bin emptyings; several bins can share one site visit.</p>
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
        <td>{{ row.month }}<small v-if="monthCoverage(row.month, asOf, firstDate)">{{ monthCoverage(row.month, asOf, firstDate) }}</small></td>
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
