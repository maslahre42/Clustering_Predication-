<script setup lang="ts">
import { coordinateSourceLabel } from '~/shared/domain/coordinates';
const { asOf, clusters } = useWorkspaceData();
const { view } = useWorkspaceNavigation();
const { stops, clearPlan, routePoints, depot, collectionDate, acceptedProposal, editManually } = useCollectionPlan();
const printedAt = useState<string | null>('manifest-print-timestamp', () => null);
</script>
<template>
  <div class="page-body manifest-page">
    <header class="section-title">
      <div>
        <p class="eyebrow">COLLECTION PLANS / DRAFT</p>
        <h1>Collection plan manifest</h1>
        <p>Plan for {{ collectionDate }} · history through {{ asOf }} · depot start and return</p>
      </div>
      <UiButton label="Back to planner" mode="outline" @click="view = 'planning'" />
    </header>
    <p v-if="printedAt" class="manifest-print-stamp print-only">Historical cutoff: {{ asOf }} · Generated: {{ printedAt }}</p>
    <template v-if="acceptedProposal">
      <UiInfoCard headline="Accepted forecast-driven plan">
        <p>Collection date {{ collectionDate }}. Forecasts, operating settings, trucks and unloading loads are preserved. History remains through {{ asOf }}.</p>
      </UiInfoCard>
      <ProposalRouteMap :proposal="acceptedProposal" :locations="clusters" />
      <OperatingCosts :costs="acceptedProposal.costs" />
      <ProposalRoutesTable :proposal="acceptedProposal" />
      <ExportActions />
      <UiButton label="Convert to editable manual draft" mode="outline" @click="editManually" />
      <p>Manual editing removes the solver's truck/load assignments and requires a new feasibility check.</p>
    </template>
    <PlanMetrics v-else />
    <WorkspaceState v-if="!stops.length" state="empty" title="Your collection plan is empty" description="Choose individual bins in the route planner. Bins at the same location will become a single stop." action="Choose collection bins" @action="view = 'planning'" />
    <div v-else-if="!acceptedProposal" class="manifest-layout">
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
