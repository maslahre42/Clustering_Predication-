<script setup lang="ts">
const { asOf, error, loading, retry, clusters } = useWorkspaceData();
const { filteredClusters } = usePlanningFilters();
const { selectedBins } = useCollectionPlan();
</script>
<template>
  <div class="planning-view">
    <header class="section-title">
      <div>
        <p class="eyebrow">HEILBRONN OPERATIONS / GLASS COLLECTION</p>
        <h1>Route planner & collection map</h1>
        <p>Review historical readings, inspect locations, and build a collection plan.</p>
      </div>
      <div class="section-totals">
        <strong>{{ clusters.length }}</strong>
        <span>known locations</span>
        <strong>{{ selectedBins.length }}</strong>
        <span>selected bins</span>
      </div>
    </header>
    <PlanningFilters />
    <WorkspaceState v-if="error" state="error" title="Historical data unavailable" description="We could not load the database records. Check the API connection and retry." action="Retry connection" @action="retry" />
    <WorkspaceState v-else-if="loading" state="loading" title="Loading historical records" description="Fetching only observations on or before the selected planning date." />
    <div v-else class="planning-canvas">
      <LocationClusterList />
      <PlanningMapPanel />
    </div>
    <p class="view-footnote">{{ filteredClusters.length }} matching locations · Fill levels are historical measurements, not forecasts or current status.</p>
  </div>
</template>
