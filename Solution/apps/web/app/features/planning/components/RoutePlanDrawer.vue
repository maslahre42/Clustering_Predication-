<script setup lang="ts">
import { workspaceIcons } from '~/shared/ui/icons';
const { asOf } = useWorkspaceData();
const { view } = useWorkspaceNavigation();
const { filteredBins } = usePlanningFilters();
const { selectedBins, stops, distance, routeOrder, addDayCollections, clearPlan, removeStop, exportCsv } = useCollectionPlan();
const collapsed = ref(false);
const contentId = useId();
</script>
<template>
  <aside class="route-drawer">
    <header>
      <div>
        <strong>Active collection plan</strong>
        <small>{{ asOf }} · draft</small>
      </div>
      <UiIconButton
        class="route-drawer-toggle"
        :label="collapsed ? 'Expand collection plan' : 'Collapse collection plan'"
        :icon="collapsed ? workspaceIcons.chevronUp : workspaceIcons.chevronDown"
        :aria-expanded="!collapsed"
        :aria-controls="contentId"
        color="neutral"
        density="compact"
        @click="collapsed = !collapsed"
      />
    </header>
    <div v-show="!collapsed" :id="contentId">
      <div class="route-metrics">
        <div>
          <small>STOPS</small>
          <strong>{{ stops.length }}</strong>
        </div>
        <div>
          <small>BINS</small>
          <strong>{{ selectedBins.length }}</strong>
        </div>
        <div>
          <small>DISTANCE</small>
          <strong>
            {{ distance.toFixed(1) }}
            <small>km</small>
          </strong>
        </div>
      </div>
      <p class="drawer-caption">{{ routeOrder.length ? 'Manual order' : 'Nearest-neighbor order' }} · straight-line round trip</p>
      <ol class="drawer-stops">
        <li v-for="(stop, i) in stops" :key="stop.locationId">
          <span class="cluster-number">{{ i + 1 }}</span>
          <div>
            <strong>Location {{ stop.locationId.slice(0, 8) }}</strong>
            <small>{{ stop.bins.map(b => b.material).join(' · ') }}</small>
          </div>
          <UiButton label="Remove" mode="plain" density="compact" @click="removeStop(stop.locationId)" />
        </li>
      </ol>
      <p v-if="!stops.length" class="drawer-caption">Select bins from the location list to build a plan.</p>
      <div class="drawer-actions">
        <UiButton label="Review collection plan" :disabled="!stops.length" @click="view = 'manifest'" />
        <div>
          <UiButton label="Export CSV" mode="outline" :disabled="!stops.length" @click="exportCsv" />
          <UiButton label="Clear" mode="plain" :disabled="!stops.length" @click="clearPlan" />
        </div>
        <UiButton label="Add this day’s collections" mode="plain" density="compact" :disabled="!filteredBins.some(b => b.lastCollection === asOf)" @click="addDayCollections" />
      </div>
    </div>
  </aside>
</template>
