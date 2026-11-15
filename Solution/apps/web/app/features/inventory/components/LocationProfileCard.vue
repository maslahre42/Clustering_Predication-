<script setup lang="ts">
import type { LocationCluster } from '../domain/catalog';
defineProps<{
    cluster: LocationCluster;
}>();
</script>
<template>
  <UiCard class="location-profile">
    <p class="eyebrow">LOCATION PROFILE</p>
    <h2>Karlsruhe</h2>
    <p>Manually collected glass-bin history</p>
    <dl>
      <dt>Coordinates</dt>
      <dd>{{ cluster.latitude.toFixed(5) }}, {{ cluster.longitude.toFixed(5) }}</dd>
      <dt>Coordinate source</dt>
      <dd>{{ cluster.isSynthetic ? 'Synthetic test coordinates' : 'Imported coordinates' }}</dd>
      <dt>Known glass bins</dt>
      <dd>{{ cluster.bins.length }}</dd>
      <dt>Road access / capacity</dt>
      <dd>Not provided</dd>
    </dl>
    <ClientOnly>
      <BinMap :locations="[cluster]" :selected="cluster.locationId" />
      <template #fallback>
        <div class="map">Loading map…</div>
      </template>
    </ClientOnly>
  </UiCard>
</template>
