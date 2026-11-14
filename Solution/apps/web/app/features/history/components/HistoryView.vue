<script setup lang="ts">
import { GLASS_OPTIONS } from '~/shared/config/materials';
import { useHistoryQuery } from '../composables/useHistoryQuery';
const props = defineProps<{
    asOf: string;
    initialLocationId?: string;
}>();
const { material, from, to, selected, page, locationSearch, sortBy, sortDirection, sort, reset, request } = useHistoryQuery(() => props.asOf, () => props.initialLocationId);
const { data: history, status, error, refresh } = request;
</script>
<template>
  <UiCard class="history-panel">
    <div class="section-heading">
      <div>
        <h2>Historical collection audit</h2>
        <p>Actual manually recorded readings through {{ asOf }}. All percentages are before emptying.</p>
      </div>
      <UiButton label="Reset filters" mode="outline" @click="reset" />
    </div>
    <div class="history-filters">
      <UiInput v-model="locationSearch" label="Search location UUID" placeholder="Full or partial UUID" />
      <UiSelect v-model="material" label="Glass fraction" list-label="Glass fractions" :options="GLASS_OPTIONS" density="compact" />
      <CollectionDatePicker v-model="from" label="From" :max="asOf" />
      <CollectionDatePicker v-model="to" label="To" :max="asOf" />
    </div>
    <p v-if="selected" class="mono">
      Location
      {{ selected }}
      <UiButton v-if="!initialLocationId" label="All locations" mode="plain" density="compact" @click="selected = ''" />
    </p>
    <WorkspaceState v-if="error" state="error" title="History unavailable" description="Check your date filters and API connection." action="Retry" @action="refresh()" />
    <WorkspaceState v-else-if="status === 'pending'" state="loading" title="Loading history" description="Only fetching records within the planning cutoff." />
    <HistoryTable v-else v-model:page="page" :history="history" :sort-by="sortBy" :sort-direction="sortDirection" @sort="sort" @select="selected = $event" />
  </UiCard>
</template>
