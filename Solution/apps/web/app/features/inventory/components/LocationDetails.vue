<script setup lang="ts">
import { useLocationHistory } from '~/features/history/composables/useHistoryQuery';
const { clusters, asOf } = useWorkspaceData();
const { inspectedLocation, view } = useWorkspaceNavigation();
const cluster = computed(() => clusters.value.find(c => c.locationId === inspectedLocation.value));
const { data: history, error, status, refresh } = useLocationHistory(inspectedLocation, asOf);
</script>
<template>
  <div class="page-body details-page">
    <header class="section-title">
      <div>
        <p class="eyebrow">LOCATIONS / BIN DETAILS</p>
        <h1>Location {{ inspectedLocation.slice(0, 8) }}</h1>
        <p class="mono">{{ inspectedLocation }}</p>
      </div>
      <UiButton label="Back to map" mode="outline" @click="view = 'planning'" />
    </header>
    <WorkspaceState v-if="!cluster" state="empty" title="No location records at this cutoff" description="Choose a location with recorded collections on or before the planning date." action="Back to planner" @action="view = 'planning'" />
    <template v-else>
      <div class="bin-detail-grid">
        <LocationProfileCard :cluster="cluster" />
        <BinFractionCard v-for="color in ['brown', 'green', 'white']" :key="color" :material="color" :bin="cluster.bins.find(b => b.material === color)" />
      </div>
      <UiCard class="chart-panel">
        <h2>Historical pre-emptying readings</h2>
        <p>Actual observations through {{ asOf }}. {{ history?.total && history.total > 200 ? 'Chart shows the latest 200 observations.' : '' }}</p>
        <WorkspaceState v-if="error" state="error" title="History unavailable" description="The location history could not be loaded." action="Retry" @action="refresh()" />
        <WorkspaceState v-else-if="status === 'pending'" state="loading" title="Loading readings" description="Applying the historical cutoff." />
        <HistoricalReadingsChart v-else :observations="history?.items ?? []" />
      </UiCard>
      <HistoryView :key="`${asOf}:${inspectedLocation}`" :as-of="asOf" :initial-location-id="inspectedLocation" />
    </template>
  </div>
</template>
