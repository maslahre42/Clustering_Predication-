<script setup lang="ts">
import { useHistoricalAnalytics } from '../composables/useHistoricalAnalytics';
const { asOf } = useWorkspaceData();
const { data, error, status, refresh, ready } = useHistoricalAnalytics(asOf);
</script>
<template>
  <div class="page-body">
    <header class="section-title">
      <div>
        <p class="eyebrow">COLLECTION HISTORY / ANALYTICS</p>
        <h1>Understand past collections.</h1>
        <p>Based on actual pre-emptying observations through {{ asOf }}.</p>
      </div>
    </header>
    <WorkspaceState v-if="error" state="error" title="Analytics unavailable" description="Check the API connection and selected date." action="Retry" @action="refresh()" />
    <WorkspaceState v-else-if="status === 'pending'" state="loading" title="Calculating historical metrics" description="Later observations are excluded from every statistic." />
    <template v-else-if="ready && data">
      <AnalyticsSummaryCards :data="data" />
      <WorkspaceState v-if="!data.totalCollections" state="empty" title="No collections by this date" description="Choose a later planning date to see historical statistics." />
      <template v-else>
        <UiCard class="analytics-panel">
          <h2>Glass-stream comparison</h2>
          <p>Means use numeric readings only: overfull and unknown values are excluded from the mean, with their counts shown separately. Intervals use all successive recorded collection dates per bin, not changes in fill level.</p>
          <MaterialAnalyticsTable :materials="data.materials" />
        </UiCard>
        <UiCard class="analytics-panel">
          <MonthlyCollectionTable :months="data.months" />
        </UiCard>
        <FillDistributionPanel :materials="data.materials" />
      </template>
    </template>
  </div>
</template>
