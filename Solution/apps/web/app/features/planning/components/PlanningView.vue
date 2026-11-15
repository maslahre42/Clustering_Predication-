<script setup lang="ts">
const { asOf, error, loading, retry, clusters } = useWorkspaceData();
const { filteredClusters, fillView, fillStateError, lastObservationDate } = usePlanningFilters();
const { selectedBins } = useCollectionPlan();
</script>
<template>
  <div class="planning-view">
    <header class="section-title">
      <div>
        <p class="eyebrow">KARLSRUHE OPERATIONS / GLASS COLLECTION</p>
        <h1>Route planner & collection map</h1>
        <p>Review fill after recorded emptyings, inspect locations, and build a collection plan.</p>
      </div>
      <div class="section-totals">
        <strong>{{ clusters.length }}</strong>
        <span>known locations</span>
        <strong>{{ selectedBins.length }}</strong>
        <span>selected bins</span>
      </div>
    </header>
    <PlanningFilters />
    <p v-if="fillView === 'estimate'" class="view-footnote">Fill after recorded emptyings on {{ asOf }}. Assuming complete emptying, recorded visits reset the model to 0%; later fill is estimated.<template v-if="lastObservationDate && asOf > lastObservationDate"> No collection records after {{ lastObservationDate }}; later fill is projected.</template></p>
    <UiInfoCard v-if="fillView === 'estimate' && fillStateError" headline="Selected-day estimates unavailable" color="warning"><p>Fill estimates are unknown. Retry or choose Last recorded before emptying to inspect the source readings.</p><UiButton label="Retry estimates" mode="outline" @click="retry" /></UiInfoCard>
    <WorkspaceState v-if="error" state="error" title="Historical data unavailable" description="We could not load the database records. Check the API connection and retry." action="Retry connection" @action="retry" />
    <WorkspaceState v-else-if="loading" state="loading" title="Loading historical records" description="Fetching only observations on or before the selected planning date." />
    <div v-else class="planning-canvas">
      <LocationClusterList />
      <PlanningMapPanel />
    </div>
    <p class="view-footnote">{{ filteredClusters.length }} matching locations · {{ fillView === 'estimate' ? 'Estimates, not live measurements. Only recorded visits reset bins; a date change or route proposal does not record a collection.' : 'Historical pre-emptying readings, not current fill.' }}</p>
  </div>
</template>
