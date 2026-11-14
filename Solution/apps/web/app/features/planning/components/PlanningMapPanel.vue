<script setup lang="ts">
import { coordinateSourceLabel } from '~/shared/domain/coordinates';
import { mapBasemap } from '~/features/map/basemap';
const config = useRuntimeConfig();
const basemap = mapBasemap(config.public.maptilerApiKey);
const { mapLocations } = useWorkspaceData();
const { inspectedLocation, inspect } = useWorkspaceNavigation();
const { routePoints, depot } = useCollectionPlan();
</script>
<template>
  <div class="planning-map-panel">
    <div class="map-top-label">
      <span class="connection-dot connected" />
      <span>HEILBRONN</span>
      <span>WGS84 · {{ coordinateSourceLabel(mapLocations) }}</span>
    </div>
    <ClientOnly>
      <BinMap :locations="mapLocations" :selected="inspectedLocation" :route="routePoints" @select="inspect" />
      <template #fallback>
        <div class="map map-placeholder">Loading collection map…</div>
      </template>
    </ClientOnly>
    <RoutePlanDrawer />
    <div class="map-bottom-label">
      <span class="route-key" />
      Straight-line route preview
      <span>•</span>
      {{ depot.isSynthetic ? 'Synthetic' : 'Imported' }}
      depot ·
      {{ depot.name }}
      <span>•</span>
      {{ basemap.provider }}
    </div>
  </div>
</template>
