<script setup lang="ts">
import { coordinateSourceLabel } from '~/shared/domain/coordinates';
import { mapBasemap } from '~/features/map/basemap';
const config = useRuntimeConfig();
const basemap = mapBasemap(config.public.maptilerApiKey);
const { healthRequest, snapshotRequest, ready, asOf, bins, clusters, retry, loading } = useWorkspaceData();
const healthy = computed(() => healthRequest.data.value?.status === 'healthy' && !healthRequest.error.value);
</script>
<template>
  <div class="page-body">
    <header class="section-title">
      <div>
        <p class="eyebrow">WORKSPACE / SYSTEM STATUS</p>
        <h1>Data connection & application state</h1>
        <p>Current API responses and available integrations.</p>
      </div>
      <UiButton label="Refresh connection" :loading="loading" @click="retry" />
    </header>
    <div class="status-grid">
      <UiCard>
        <header class="section-heading">
          <h2>Historical database</h2>
          <UiTag :label="healthy ? 'Connected' : 'Unavailable'" :color="healthy ? 'success' : 'danger'" />
        </header>
        <p>SQLite · read-only</p>
        <dl>
          <dt>API health</dt>
          <dd>{{ healthRequest.status.value === 'pending' ? 'Checking…' : healthy ? 'Required tables are accessible' : 'Could not verify the connection' }}</dd>
          <dt>Source</dt>
          <dd>Manually recorded pre-emptying percentages</dd>
          <dt>Planning cutoff</dt>
          <dd>{{ asOf }} (inclusive)</dd>
        </dl>
      </UiCard>
      <UiCard>
        <h2>Snapshot availability</h2>
        <dl>
          <dt>Snapshot</dt>
          <dd>{{ ready ? 'Loaded for selected date' : 'Not available' }}</dd>
          <dt>Known locations / bins</dt>
          <dd>{{ clusters.length }} / {{ bins.length }}</dd>
          <dt>Eligible observations</dt>
          <dd>{{ ready ? snapshotRequest.data.value?.observationCount : '—' }}</dd>
          <dt>Eligible date range</dt>
          <dd>{{ ready ? snapshotRequest.data.value?.firstDate ?? 'No records' : '—' }} → {{ ready ? snapshotRequest.data.value?.lastDate ?? 'No records' : '—' }}</dd>
        </dl>
      </UiCard>
      <UiCard>
        <h2>Routing & map</h2>
        <dl>
          <dt>Map data</dt>
          <dd>{{ basemap.provider }} · internet required</dd>
          <dt>Coordinates / depot</dt>
          <dd>{{ coordinateSourceLabel(bins) }}</dd>
          <dt>Stop ordering</dt>
          <dd>Nearest-neighbor or manual order</dd>
          <dt>Road routing / driving times</dt>
          <dd>Not connected</dd>
        </dl>
      </UiCard>
      <UiCard>
        <h2>Future integrations</h2>
        <dl>
          <dt>Forecast model</dt>
          <dd>Not connected</dd>
          <dt>Sensor telemetry</dt>
          <dd>Not part of the current data source</dd>
          <dt>Driver dispatch</dt>
          <dd>Not connected</dd>
          <dt>Plan storage</dt>
          <dd>Draft in memory; export CSV or print</dd>
        </dl>
      </UiCard>
    </div>
  </div>
</template>
