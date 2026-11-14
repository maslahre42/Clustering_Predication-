<script setup lang="ts">
import type { LocationCluster } from '~/features/inventory/domain/catalog';
const props = defineProps<{
    cluster: LocationCluster;
    index: number;
}>();
const { clusters } = useWorkspaceData();
const { inspect } = useWorkspaceNavigation();
const { selectedKeys, toggleLocation, toggleBin } = useCollectionPlan();
const fullCluster = computed(() => clusters.value.find(c => c.locationId === props.cluster.locationId) ?? props.cluster);
const allSelected = computed(() => props.cluster.bins.every(b => selectedKeys.value.includes(b.key)));
const partlySelected = computed(() => !allSelected.value && props.cluster.bins.some(b => selectedKeys.value.includes(b.key)));
</script>
<template>
  <article :class="['cluster-card', { 'is-selected': allSelected || partlySelected }]">
    <header>
      <UiCheckbox :value="cluster.locationId" :model-value="allSelected" :indeterminate="partlySelected" :label="`Select visible bins at ${cluster.locationId}`" hide-label @update:model-value="toggleLocation(cluster.locationId, !!$event)" />
      <span class="cluster-number">{{ index + 1 }}</span>
      <h3 :title="cluster.locationId">Location {{ cluster.locationId.slice(0, 8) }}</h3>
    </header>
    <p class="cluster-id">{{ cluster.locationId }}</p>
    <div class="fraction-meters">
      <HistoricalFillMeter v-for="color in ['brown', 'green', 'white']" :key="color" :material="color" :value="fullCluster.bins.find(b => b.material === color)?.lastFillPercent ?? null" :overfull="fullCluster.bins.find(b => b.material === color)?.lastIsOverfull" :date="fullCluster.bins.find(b => b.material === color)?.lastCollection" />
    </div>
    <div class="bin-toggles">
      <UiCheckbox v-for="bin in cluster.bins" :key="bin.key" :value="bin.key" :label="bin.material" :model-value="selectedKeys.includes(bin.key)" density="compact" @update:model-value="toggleBin(bin.key, !!$event)" />
    </div>
    <footer>
      <small>{{ cluster.bins.length }} matching bins · pre-emptying readings</small>
      <UiButton label="Inspect details →" mode="plain" density="compact" @click="inspect(cluster.locationId)" />
    </footer>
  </article>
</template>
