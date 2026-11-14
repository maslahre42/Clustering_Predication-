<script setup lang="ts">
import { historicalFillLabel } from '~/shared/domain/fill';
import type { LocationCluster } from '~/features/inventory/domain/catalog';
defineProps<{
    stop: LocationCluster;
    index: number;
    total: number;
}>();
const { inspect } = useWorkspaceNavigation();
const { moveStop, removeStop, notes } = useCollectionPlan();
const noteOpen = ref(false);
</script>
<template>
  <article class="manifest-stop">
    <header>
      <span class="cluster-number">{{ index + 1 }}</span>
      <div>
        <h3>Location {{ stop.locationId.slice(0, 8) }}</h3>
        <p class="mono">{{ stop.locationId }}</p>
      </div>
      <div class="stop-actions">
        <UiButton label="Move up" mode="plain" density="compact" :disabled="index === 0" @click="moveStop(stop.locationId, -1)" />
        <UiButton label="Move down" mode="plain" density="compact" :disabled="index === total - 1" @click="moveStop(stop.locationId, 1)" />
        <UiButton label="Remove" mode="plain" color="danger" density="compact" @click="removeStop(stop.locationId)" />
      </div>
    </header>
    <div class="manifest-fractions">
      <div v-for="bin in stop.bins" :key="bin.key">
        <GlassFractionBadge :material="bin.material" />
        <strong>{{ historicalFillLabel(bin.lastFillPercent, bin.lastIsOverfull) }}</strong>
        <small>recorded {{ bin.lastCollection }}</small>
      </div>
    </div>
    <div class="stop-meta">
      <span>GPS {{ stop.latitude.toFixed(5) }}, {{ stop.longitude.toFixed(5) }} · {{ stop.isSynthetic ? 'synthetic' : 'imported' }}</span>
      <UiButton label="Inspect history" mode="plain" density="compact" @click="inspect(stop.locationId)" />
      <UiButton :label="noteOpen ? 'Hide collector note' : 'Add / edit collector note'" mode="plain" density="compact" @click="noteOpen = !noteOpen" />
    </div>
    <UiTextarea v-if="noteOpen" v-model="notes[stop.locationId]" label="Collector note (draft, held in memory)" :autosize="{ min: 2, max: 5 }" />
    <p v-else-if="notes[stop.locationId]" class="collector-note">{{ notes[stop.locationId] }}</p>
    <p v-if="noteOpen && notes[stop.locationId]" class="collector-note print-only">{{ notes[stop.locationId] }}</p>
  </article>
</template>
