<script setup lang="ts">
import { ref, computed, watch } from 'vue';
const { fillView, fillStatePending, filteredClusters, search, material, minimumFill, sort, resetFilters } = usePlanningFilters();
const page = ref(1);
watch([fillView, search, material, minimumFill, sort], () => { page.value = 1; });
const shown = computed(() => filteredClusters.value.slice((page.value - 1) * 10, page.value * 10));
</script>
<template>
  <div class="cluster-list">
    <div class="cluster-list-heading">
      <strong>{{ filteredClusters.length }} locations</strong>
      <span>{{ fillView === 'estimate' ? 'After recorded emptyings' : 'Recorded before collection' }}</span>
    </div>
    <LocationClusterCard v-for="(cluster, i) in shown" :key="cluster.locationId" :cluster="cluster" :index="(page - 1) * 10 + i" />
    <WorkspaceState v-if="fillView === 'estimate' && fillStatePending" state="loading" title="Estimating fill after emptying" description="Applying recorded emptyings and estimating refill." />
    <WorkspaceState v-else-if="!filteredClusters.length" state="empty" title="No locations match" description="Try a lower fill threshold, another glass color, or a different planning date." action="Reset filters" @action="resetFilters" />
    <div v-if="filteredClusters.length" class="list-pagination">
      <UiPagination v-model="page" :pages="Math.max(1, Math.ceil(filteredClusters.length / 10))" auto-compact />
    </div>
  </div>
</template>
