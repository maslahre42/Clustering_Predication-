<script setup lang="ts">
import { coordinateSourceLabel } from '~/shared/domain/coordinates';
const { asOf } = useWorkspaceData();
const { view } = useWorkspaceNavigation();
const { stops, clearPlan, routePoints, depot } = useCollectionPlan();
const printedAt = useState<string | null>('manifest-print-timestamp', () => null);
</script>
<template>
  <div class="page-body manifest-page">
    <header class="section-title">
      <div>
        <p class="eyebrow">COLLECTION PLANS / DRAFT</p>
        <h1>Collection plan manifest</h1>
        <p>Plan for {{ asOf }} · source records through this date · depot start and return</p>
      </div>
      <UiButton label="Back to planner" mode="outline" @click="view = 'planning'" />
    </header>
    <p v-if="printedAt" class="manifest-print-stamp print-only">Historical cutoff: {{ asOf }} · Generated: {{ printedAt }}</p>
    <PlanMetrics />
    <WorkspaceState v-if="!stops.length" state="empty" title="Your collection plan is empty" description="Choose individual bins in the route planner. Bins at the same location will become a single stop." action="Choose collection bins" @action="view = 'planning'" />
    <div v-else class="manifest-layout">
      <div>
        <div class="section-heading">
          <h2>Grouped stop sequence</h2>
          <UiButton label="Clear draft" mode="plain" @click="clearPlan" />
        </div>
        <ManifestStopCard v-for="(stop, i) in stops" :key="stop.locationId" :stop="stop" :index="i" :total="stops.length" />
      </div>
      <aside class="manifest-side">
        <div class="surface">
          <h2>Route topology</h2>
          <ClientOnly>
            <BinMap :locations="stops" selected="" :route="routePoints" />
            <template #fallback>
              <div class="map">Loading map…</div>
            </template>
          </ClientOnly>
          <p>Dashed lines are straight connections, not driving directions. {{ depot.isSynthetic ? 'Synthetic' : 'Imported' }} depot: {{ depot.latitude }}, {{ depot.longitude }}.</p>
        </div>
        <ExportActions />
      </aside>
    </div>
    <footer v-if="stops.length" class="manifest-print-footer print-only">
      Draft collection plan · {{ coordinateSourceLabel(stops) }} · Straight-line preview, not driving directions.
    </footer>
  </div>
</template>
