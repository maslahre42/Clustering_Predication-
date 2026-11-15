<script setup lang="ts">
const workspace = createCollectionWorkspace()
const { asOf } = workspace
const { view, inspectedLocation } = workspace.navigation
</script>

<template>
  <div class="application-shell icon-sidebar">
    <WorkspaceSidebar />
    <div class="application-body">
      <WorkspaceHeader />
      <main id="workspace-content">
        <PlanningView v-if="view === 'planning'" />
        <div v-else-if="view === 'history'" class="page-body">
          <header class="section-title">
            <div>
              <p class="eyebrow">BIN INVENTORY & HISTORY</p>
              <h1>Your collection records.</h1>
              <p>Filter actual observations by glass color, location, and date.</p>
            </div>
          </header>
          <LazyHistoryView :key="asOf" :as-of="asOf" />
        </div>
        <LazyLocationDetails
          v-else-if="view === 'details'"
          :key="`${asOf}:${inspectedLocation}`"
        />
        <LazyCollectionManifest v-else-if="view === 'manifest'" />
        <LazyCollectionAnalyticsView v-else-if="view === 'analytics'" :key="asOf" />
        <LazyCollectionProposalView v-else-if="view === 'forecasts'" />
        <LazySystemStatus v-else />
      </main>
      <footer class="workspace-footer">
        <strong>Garbage Collector</strong>
      </footer>
    </div>
  </div>
</template>
